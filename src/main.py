import argparse
import copy
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor

import pygame
from OpenGL import GL as gl
from engine.camera import Camera
from engine.level1 import Stage
from engine.tutorial import TutorialRun as Level1
from engine.opengl_renderer import OpenGLRenderer, build_batches, upload_batches
from engine.ui import TutorialHUD
from engine.screenshot import save_png
from engine.input import PointerCapture
from engine.items import RECIPE_ORDER,SPEAR_ANIMATION
from engine import models
from engine.menu import MenuFlow, Screen
from engine.survival import SurvivalRun
from engine.survival_ui import SurvivalHUD
from engine.workshop_ui import ExpandedTutorialHUD
from engine.run_config import RunSeeds


SKY_COLOUR = (.36, .65, .88)


def create_display(args):
    flags = pygame.OPENGL | pygame.DOUBLEBUF
    if args.windowed:
        size = max(640, args.width), max(480, args.height)
        flags |= pygame.RESIZABLE
    else:
        size = pygame.display.get_desktop_sizes()[0]
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode(size, flags)
    return screen.get_size()


def render_scene(renderer, level, batches):
    camera = level.camera
    death = level.effects.latest('player_died')
    if death or level.state == Stage.DEAD:
        camera = copy.copy(camera)
        from engine.animation import ease
        collapse = ease(death.progress) if death else 1.
        camera.y -= .85*collapse
        camera.pitch += .35*collapse
    gl.glClearColor(*SKY_COLOUR, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    renderer.render_frame(camera, batches)
    instances = []
    for entity in level.entities.all():
        distance = entity.distance_to(camera.x,camera.z)
        if entity.visible and (not hasattr(level.world,'chunks') or
                               (distance < 58 and renderer.visible(camera,entity.x,entity.y,entity.z,2))):
            for mesh in entity.render_meshes:

                mx, my, mz = mesh.position
                cy, sy = math.cos(entity.yaw), math.sin(entity.yaw)
                instances.append((mesh,entity.x+mx*cy+mz*sy,entity.y+my,entity.z-mx*sy+mz*cy,entity.yaw))
    renderer.render_models(camera,instances)
    renderer.render_models(camera, level.tree_falls.instances())
    level.effects.draw(renderer, camera)
    prompt = level.world_prompt()
    for marker in level.objective_markers():
        if prompt and marker.target_id == prompt.target_id and marker.style == 'arrow':
            continue
        pos = marker.position(level.entities, level.elapsed)
        if pos is None:
            continue
        if marker.style == 'ring':
            renderer.render_mesh_dynamic(camera, level.ring_mesh, *pos)
        else:


            gl.glDisable(gl.GL_DEPTH_TEST)
            for mesh in level.arrow_meshes:
                renderer.render_mesh_dynamic(camera, mesh, *pos)
            gl.glEnable(gl.GL_DEPTH_TEST)

    if level.state != Stage.BEACON and not getattr(level, 'is_workshop', False):
        renderer.render_mesh_dynamic(camera, level.ring_mesh, *level.world.beacon)
    held = level.inventory.selected_item
    if held and level.active:
        # Held gear stays with you when you look around.
        hand_camera = Camera()
        hand_camera.y = hand_camera.z = 0
        hand_camera.pivot_offset = 0
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        if held == 'spear':
            meshes = models.pose_spear(level.weapon_meshes,level.attack_anim_timer*SPEAR_ANIMATION/level.attack_anim_duration)
        elif held == 'axe':
            meshes = models.pose_axe(level.axe_meshes,level.attack_anim_timer*.45/level.attack_anim_duration)
        elif held == 'compass':
            relative, _, _ = level.compass_guidance()
            meshes = [*level.held_compass_meshes, models.pose_compass(level.compass_needle, relative)]
        else:
            meshes = level.held_props.get(held, ())
        renderer.render_models(hand_camera,[(m,*m.position,0) for m in meshes])


class Application:
    def __init__(self, width, height, seed=None, smoke_test=False):
        self.width, self.height = width, height
        self.seed,self.smoke_test = seed if seed is not None else 42,smoke_test
        self.run_seeds = RunSeeds(seed)
        self.tutorial_seed = self.seed
        self.menu = MenuFlow()
        self.hud = TutorialHUD()
        self.pointer = PointerCapture()
        self.level = self.renderer = None
        self.batches = []
        self.chunk_batches = {}
        self.upload_times = []
        self.executor = self.loading_future = None
        self.loading_visible = False
        self.loading_signature = None
        self.render_revision = 0
        self.paused = False
        self.running = True
        self.just_started = False

    def return_to_title(self):
        self.pointer.set_active(False)
        if self.level:
            self.level.cancel_use()
            self.level.camera.grab_active = False
        self.paused = False
        if self.level and getattr(self.level, 'is_survival', False):
            self.release_world()
        self.menu.back()

    def release_world(self):
        if self.level and hasattr(self.level.world,'close'):
            self.level.world.close()
        for _,batches in self.chunk_batches.values():
            if batches:
                gl.glDeleteBuffers(len(batches),[b.vbo for b in batches])
        self.chunk_batches.clear()
        if self.batches:
            gl.glDeleteBuffers(len(self.batches), [batch.vbo for batch in self.batches])
        if self.renderer:
            self.renderer.close()
        self.level, self.renderer, self.batches = None, None, []

    def configure_next_run(self):
        self.return_to_title()
        self.menu.activate(0)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_q and event.mod & pygame.KMOD_CTRL:
            self.running = False
        elif event.type == pygame.WINDOWRESIZED:
            self.width, self.height = max(640, event.x), max(480, event.y)
            if (self.width, self.height) != (event.x, event.y):
                self.pointer.window.size = self.width, self.height
            gl.glViewport(0, 0, self.width, self.height)
            if self.renderer:
                self.renderer.width, self.renderer.height = self.width, self.height
                self.renderer.focal_length = self.width*.7
            self.pointer.set_active(False)
            if self.level:
                self.level.cancel_use()
        elif event.type == pygame.WINDOWFOCUSLOST and not self.smoke_test:
            if self.menu.screen in (Screen.TUTORIAL, Screen.RUN):
                self.paused = True
                self.level.cancel_use()
            self.pointer.set_active(False)
        elif self.menu.screen not in (Screen.TUTORIAL, Screen.RUN):
            previous = self.menu.screen
            if self.menu.screen == Screen.TITLE and not self.hud._intro_finished:
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    # Skip the intro. Hidden buttons don't get a side quest.
                    self.hud._intro_finished = True
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and self.menu.screen == Screen.TITLE:
                    self.running = False
                else:
                    self.menu.key(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.hud.mouse_pos = event.pos
                self.menu.mouse(event.pos, self.width, self.height)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                buttons, back = self.menu.layout(self.width, self.height)
                for rect in (*buttons, back):
                    if rect.collidepoint(event.pos):
                        self.hud.press_button(rect)
                self.menu.mouse(event.pos, self.width, self.height, clicked=True)
            cached_tutorial = self.level and not self.menu.run_requested and not getattr(self.level, 'is_survival', False)
            if self.menu.screen == Screen.LOADING and previous != Screen.LOADING and not cached_tutorial:
                self.loading_visible = False
            if previous==Screen.LOADING and self.menu.screen!=Screen.LOADING and self.loading_future:
                abandoned = self.loading_future
                if not abandoned.cancel():
                    def discard(future):
                        try:
                            loaded = future.result()
                            if hasattr(loaded.world,'close'):loaded.world.close()
                        except Exception:pass
                    abandoned.add_done_callback(discard)
                self.loading_future = None
        elif event.type == pygame.KEYDOWN:
            level = self.level
            if not level.active and event.key == pygame.K_h:
                return
            if event.key == pygame.K_h:
                if getattr(level, 'is_survival', False):
                    if level.help_open:
                        level.help_open = False
                    else:
                        self.paused = not self.paused
                        level.crafting_open = False
                else:
                    level.help_open = not level.help_open
                level.cancel_use()
                self.pointer.set_active(False)
            elif event.key == pygame.K_ESCAPE:
                if level.help_open:
                    level.help_open = False
                elif level.crafting_open:
                    level.toggle_crafting()
                elif self.paused or not level.active:
                    self.return_to_title()
                else:
                    self.paused = True
                    self.pointer.set_active(False)
                    level.cancel_use()
            elif level.help_open:
                return
            elif event.key == pygame.K_RETURN and self.paused and level.active:
                self.paused = False
            elif event.key == pygame.K_r and not level.active:
                if getattr(level, 'is_survival', False):
                    self.configure_next_run()
                else:
                    level.reset()
                self.paused = False
            elif level.active and not self.paused:
                if event.key == pygame.K_c:
                    level.toggle_crafting()
                    self.pointer.set_active(False)
                elif level.crafting_open:
                    if event.key in (pygame.K_UP, pygame.K_DOWN):
                        offset = -1 if event.key == pygame.K_UP else 1
                        level.selected_recipe = (level.selected_recipe+offset) % len(getattr(level, 'recipes', RECIPE_ORDER))
                    elif event.key == pygame.K_RETURN:
                        level.craft()
                elif event.key == pygame.K_f:
                    level.handle_interaction()
                elif event.key == pygame.K_g and getattr(level, 'is_survival', False):
                    level.drop_selected()
                elif pygame.K_0 <= event.key <= pygame.K_9:
                    level.select_slot(event.key-pygame.K_0)
        elif event.type == pygame.MOUSEMOTION:
            self.hud.mouse_pos = event.pos
        elif event.type==pygame.MOUSEBUTTONDOWN and event.button in (1,3):
            if event.button==3:
                if (self.level.active and not self.paused and not self.level.help_open
                        and not self.level.crafting_open and self.pointer.active):
                    self.level.handle_attack(heavy=True)
                return
            if self.level.help_open:
                return
            if self.paused or not self.level.active:
                action = self.hud.handle_overlay_click(self.level, event.pos, self.width, self.height, self.paused)
                if action == 'resume':
                    self.paused = False
                elif action == 'restart':
                    if getattr(self.level, 'is_survival', False):
                        self.configure_next_run()
                    else:
                        self.level.reset()
                    self.paused = False
                elif action == 'controls':
                    self.level.help_open = True
                elif action == 'title':
                    self.return_to_title()
                elif action == 'quit':
                    self.running = False
            elif self.level.crafting_open:
                self.hud.handle_crafting_click(self.level, event.pos, self.width, self.height)
            elif self.pointer.active:
                self.level.handle_attack()

    def update(self, dt):
        was_loading = self.menu.screen==Screen.LOADING
        self.just_started = False
        self.menu.elapsed += dt
        if self.menu.screen == Screen.LOADING and self.loading_visible and not self.menu.error:
            if self.level and not self.menu.run_requested and not getattr(self.level, 'is_survival', False):
                self.level.reset()
                self.menu.screen = Screen.TUTORIAL
            else:
                signature = (self.menu.run_requested, self.seed, self.menu.config)
                if self.loading_future is not None and self.loading_signature != signature:
                    self.loading_future.cancel()
                    self.loading_future = None
                if self.loading_future is None:
                    if self.level:
                        self.release_world()
                    if self.executor is None:
                        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='jungle')
                    # Build the forest off-thread; OpenGL stays on the window thread.
                    self.seed = self.run_seeds.next() if self.menu.run_requested else self.tutorial_seed
                    self.loading_signature = (self.menu.run_requested,self.seed,self.menu.config)
                    print(json.dumps(dict(event='generation_requested',seed=self.seed,
                                          configuration=self.menu.config.__dict__,fixed_seed=self.run_seeds.override is not None)),flush=True)
                    self.loading_future = (self.executor.submit(SurvivalRun, Camera(), self.seed, self.menu.config)
                                           if self.menu.run_requested else self.executor.submit(Level1, Camera(), self.seed))
                if self.loading_future.done():
                    level = None
                    try:
                        level = self.loading_future.result()
                        self.renderer = OpenGLRenderer(self.width, self.height)
                        self.renderer.focal_length = self.width*.7
                        is_run = getattr(level,'is_survival',False)
                        self.renderer.fog_color = SKY_COLOUR if hasattr(level.world,'chunks') else (.18,.28,.22)
                        self.renderer.fog_near,self.renderer.fog_far = (28,60) if hasattr(level.world,'chunks') else (24,68)
                        if hasattr(level.world,'chunks'):
                            self.sync_chunks(level,initial=True)
                        else:
                            self.batches = build_batches(level.world.meshes)
                        self.level = level
                        is_run = getattr(level, 'is_survival', False)
                        self.hud.close()
                        self.hud = SurvivalHUD() if is_run else ExpandedTutorialHUD()
                        self.hud._intro_finished = True
                        self.menu.screen = Screen.RUN if is_run else Screen.TUTORIAL
                        self.render_revision = getattr(level.world, 'render_revision', 0)
                        print(json.dumps({'event': 'run_ready' if is_run else 'tutorial_ready', 'seed': self.seed,
                                          'validation': level.world.validation,
                                          'batches': len(self.batches)+sum(len(bs) for _,bs in self.chunk_batches.values()),
                                          'loaded_chunks':len(self.chunk_batches)}), flush=True)
                    except Exception as error:
                        self.release_world()
                        if level and hasattr(level.world,'close'):
                            level.world.close()
                        self.menu.error = "Couldn't load the jungle. Head back and try again."
                        print(json.dumps({'event': 'load_error', 'error': str(error)}), flush=True)
                    self.loading_future = None
        level = self.level
        playing = self.menu.screen in (Screen.TUTORIAL, Screen.RUN)
        should_capture = playing and level.active and not self.paused and not level.crafting_open and not level.help_open and not self.smoke_test
        self.pointer.set_active(should_capture)
        if level:
            level.camera.grab_active = should_capture
        if was_loading and playing:
            self.just_started = True
            return
        if should_capture:
            steps = max(1,math.ceil(dt/(1/60)))
            delta = self.pointer.delta()
            held = pygame.key.get_pressed()[pygame.K_e]
            for i in range(steps):
                if not level.active:break
                level.camera.update(dt/steps,delta if i==0 else (0,0))
                level.update_use(dt/steps,held)
                level.update(dt/steps)
        elif playing and not self.paused and not level.crafting_open and not level.help_open:
            steps = max(1,math.ceil(dt/(1/60)))
            for _ in range(steps):level.update(dt/steps)

    def render(self, fps=0):
        if self.menu.screen in (Screen.TUTORIAL, Screen.RUN):
            revision = getattr(self.level.world, 'render_revision', 0)
            if hasattr(self.level.world,'chunks'):
                self.sync_chunks(self.level)
                visible = []
                for key,(_,batches) in self.chunk_batches.items():
                    x,z = (key[0]+.5)*32,(key[1]+.5)*32
                    if self.renderer.visible(self.level.camera,x,self.level.world.height(x,z)+3,z,25):
                        visible.extend(batches)
                self.render_revision = revision
                render_scene(self.renderer,self.level,visible)
            elif revision != self.render_revision:
                old = self.batches
                self.batches = build_batches(self.level.world.meshes)
                if old:
                    gl.glDeleteBuffers(len(old), [batch.vbo for batch in old])
                self.render_revision = revision
            if not hasattr(self.level.world,'chunks'):
                render_scene(self.renderer, self.level, self.batches)
            self.hud.draw(self.level, self.width, self.height, fps, paused=self.paused)
        else:
            self.hud.draw_menu(self.menu, self.width, self.height)
            if self.menu.screen == Screen.LOADING:
                self.loading_visible = True

    def sync_chunks(self,level,initial=False):
        chunks = level.world.chunks
        for key in self.chunk_batches.keys()-chunks.keys():
            _,old = self.chunk_batches.pop(key)
            gl.glDeleteBuffers(len(old),[b.vbo for b in old])
        pending = [chunk for key,chunk in chunks.items()
                   if key not in self.chunk_batches or self.chunk_batches[key][0] != chunk.revision]
        pending.sort(key=lambda c:math.hypot((c.key[0]+.5)*32-level.camera.x,(c.key[1]+.5)*32-level.camera.z))
        for chunk in pending[:len(pending) if initial else 1]:
            started = time.perf_counter()
            batches = upload_batches(chunk.packed)
            old = self.chunk_batches.get(chunk.key)
            self.chunk_batches[chunk.key] = chunk.revision,batches
            if old:
                gl.glDeleteBuffers(len(old[1]),[b.vbo for b in old[1]])
            self.upload_times.append((time.perf_counter()-started)*1000)
            self.upload_times = self.upload_times[-128:]

    def close(self):
        self.pointer.set_active(False)
        self.hud.close()
        if self.executor:
            self.executor.shutdown(wait=True, cancel_futures=True)
        if self.loading_future and not self.loading_future.cancelled() and self.loading_future.done():
            try:
                loaded = self.loading_future.result()
                if loaded is not self.level and hasattr(loaded.world,'close'):
                    loaded.world.close()
            except Exception:
                pass
        self.release_world()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Walking the Walk: CS Jungle')
    parser.add_argument('--windowed', action='store_true', help='Start in a window; fullscreen is the default')
    parser.add_argument('--seed',type=int,default=None,help='Developer override: reproduce this seed; ordinary runs use fresh seeds')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=800)
    parser.add_argument('--smoke-test', action='store_true', help='Log frame health while an external timeout handles the stop')
    parser.add_argument('--screenshot', help='Save one rendered frame to this PNG path')
    args = parser.parse_args(argv)
    pygame.display.init()
    pygame.display.set_caption('Walking the Walk - CS Jungle')
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_COMPATIBILITY)
    width, height = create_display(args)
    app = Application(width, height, args.seed, args.smoke_test)
    clock = pygame.time.Clock()
    frames, last_report = 0, time.monotonic()
    try:
        app.render()
        if args.screenshot:
            gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
            data = gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
            save_png(args.screenshot, width, height, data)
        pygame.display.flip()
        print(json.dumps({'event': 'ready', 'screen': app.menu.screen.value, 'seed': args.seed,
                          'fullscreen': not args.windowed, 'size': [width, height],
                          'opengl': gl.glGetString(gl.GL_VERSION).decode()}), flush=True)
        while app.running:
            dt = min(clock.tick(60)/1000, .25)
            for event in pygame.event.get():
                app.handle_event(event)
            app.update(dt)
            app.render(clock.get_fps())
            error = gl.glGetError()
            if error != gl.GL_NO_ERROR:
                raise RuntimeError(f'OpenGL frame error: {error}')
            pygame.display.flip()
            if app.just_started:
                clock.tick()
            frames += 1
            now = time.monotonic()
            if args.smoke_test and now-last_report >= 1:
                print(json.dumps({'event': 'frame_health', 'frames': frames, 'fps': round(clock.get_fps(), 1),
                                  'gl_error': 0, 'screen': app.menu.screen.value,
                                  'stage': app.level.state.name if app.level else None}), flush=True)
                last_report = now
    finally:
        app.close()
        pygame.quit()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
