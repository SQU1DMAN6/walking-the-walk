import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor

import pygame
from OpenGL import GL as gl
from engine.camera import Camera
from engine.level1 import Level1, Stage
from engine.opengl_renderer import OpenGLRenderer, build_batches
from engine.ui import TutorialHUD
from engine.screenshot import save_png
from engine.input import PointerCapture
from engine.items import RECIPE_ORDER
from engine import models
from engine.menu import MenuFlow, Screen


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
    gl.glClearColor(*SKY_COLOUR, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    renderer.render_frame(camera, batches)
    for entity in level.entities.all():
        if entity.visible:
            for mesh in entity.meshes:

                mx, my, mz = mesh.position
                cy, sy = math.cos(entity.yaw), math.sin(entity.yaw)
                renderer.render_mesh_dynamic(camera, mesh, entity.x+mx*cy+mz*sy,
                                             entity.y+my, entity.z-mx*sy+mz*cy, entity.yaw)
    for marker in level.objective_markers():
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

    if level.state != Stage.BEACON:
        renderer.render_mesh_dynamic(camera, level.ring_mesh, *level.world.beacon)
    held = level.inventory.selected_item
    if held and level.active:
        # Held gear stays with you when you look around.
        hand_camera = Camera()
        hand_camera.y = hand_camera.z = 0
        hand_camera.pivot_offset = 0
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        thrust = .25 * math.sin(level.attack_anim_timer/.22*math.pi)
        if held == 'spear':
            meshes = level.weapon_meshes
        elif held == 'compass':
            relative, _, _ = level.compass_guidance()
            meshes = [*level.held_compass_meshes, models.pose_compass(level.compass_needle, relative)]
        else:
            meshes = level.held_props.get(held, ())
        for mesh in meshes:
            renderer.render_mesh_dynamic(hand_camera, mesh, 0, 0, thrust if held == 'spear' else 0)


class Application:
    def __init__(self, width, height, seed=42, smoke_test=False):
        self.width, self.height = width, height
        self.seed, self.smoke_test = seed, smoke_test
        self.menu = MenuFlow()
        self.hud = TutorialHUD()
        self.pointer = PointerCapture()
        self.level = self.renderer = None
        self.batches = []
        self.executor = self.loading_future = None
        self.loading_visible = False
        self.paused = False
        self.running = True

    def return_to_title(self):
        self.pointer.set_active(False)
        if self.level:
            self.level.cancel_use()
            self.level.camera.grab_active = False
        self.paused = False
        self.menu.back()

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_q and event.mod & pygame.KMOD_CTRL:
            self.running = False
        elif event.type == pygame.WINDOWRESIZED:
            self.width, self.height = max(1, event.x), max(1, event.y)
            gl.glViewport(0, 0, self.width, self.height)
            if self.renderer:
                self.renderer.width, self.renderer.height = self.width, self.height
                self.renderer.focal_length = self.width*.7
            self.pointer.set_active(False)
            if self.level:
                self.level.cancel_use()
        elif event.type == pygame.WINDOWFOCUSLOST and not self.smoke_test:
            if self.menu.screen == Screen.TUTORIAL:
                self.paused = True
                self.level.cancel_use()
            self.pointer.set_active(False)
        elif self.menu.screen != Screen.TUTORIAL:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and self.menu.screen == Screen.TITLE:
                    self.running = False
                else:
                    self.menu.key(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.menu.mouse(event.pos, self.width, self.height)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.menu.mouse(event.pos, self.width, self.height, clicked=True)
        elif event.type == pygame.KEYDOWN:
            level = self.level
            if event.key == pygame.K_ESCAPE:
                if level.crafting_open:
                    level.toggle_crafting()
                elif self.paused or not level.active:
                    self.return_to_title()
                else:
                    self.paused = True
                    self.pointer.set_active(False)
                    level.cancel_use()
            elif event.key == pygame.K_r and not level.active:
                level.reset()
                self.paused = False
            elif level.active and not self.paused:
                if event.key == pygame.K_c:
                    level.toggle_crafting()
                    self.pointer.set_active(False)
                elif level.crafting_open:
                    if event.key in (pygame.K_UP, pygame.K_DOWN):
                        offset = -1 if event.key == pygame.K_UP else 1
                        level.selected_recipe = (level.selected_recipe+offset) % len(RECIPE_ORDER)
                    elif event.key == pygame.K_RETURN:
                        level.craft()
                elif event.key == pygame.K_f:
                    level.handle_interaction()
                elif pygame.K_0 <= event.key <= pygame.K_9:
                    level.select_slot(event.key-pygame.K_0)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.paused:
                self.paused = False
            elif self.level.crafting_open:
                self.hud.handle_crafting_click(self.level, event.pos, self.width, self.height)
            elif self.pointer.active:
                self.level.handle_attack()

    def update(self, dt):
        self.menu.elapsed += dt
        if self.menu.screen == Screen.LOADING and self.loading_visible and not self.menu.error:
            if self.level:
                self.level.reset()
                self.menu.screen = Screen.TUTORIAL
            else:
                if self.loading_future is None:
                    if self.executor is None:
                        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='jungle')
                    # Build the forest off-thread; OpenGL stays on the window thread.
                    self.loading_future = self.executor.submit(Level1, Camera(), self.seed)
                if self.loading_future.done():
                    try:
                        level = self.loading_future.result()
                        self.renderer = OpenGLRenderer(self.width, self.height)
                        self.renderer.focal_length = self.width*.7
                        self.renderer.fog_color = (.18, .28, .22)
                        self.renderer.fog_near, self.renderer.fog_far = 24, 68
                        self.batches = build_batches(level.world.meshes)
                        self.level = level
                        self.menu.screen = Screen.TUTORIAL
                        print(json.dumps({'event': 'tutorial_ready', 'seed': self.seed,
                                          'validation': level.world.validation, 'batches': len(self.batches)}), flush=True)
                    except Exception as error:
                        if self.renderer:
                            self.renderer.close()
                            self.renderer = None
                        self.menu.error = "Couldn't load Tutorial. Head back and try again."
                        print(json.dumps({'event': 'load_error', 'error': str(error)}), flush=True)
                    self.loading_future = None
        level = self.level
        playing = self.menu.screen == Screen.TUTORIAL
        should_capture = playing and level.active and not self.paused and not level.crafting_open and not self.smoke_test
        self.pointer.set_active(should_capture)
        if level:
            level.camera.grab_active = should_capture
        if should_capture:
            level.camera.update(dt, self.pointer.delta())
            level.update_use(dt, pygame.key.get_pressed()[pygame.K_e])
            level.update(dt)
        elif playing and self.smoke_test and not self.paused and not level.crafting_open:
            level.update(dt)

    def render(self, fps=0):
        if self.menu.screen == Screen.TUTORIAL:
            render_scene(self.renderer, self.level, self.batches)
            self.hud.draw(self.level, self.width, self.height, fps, paused=self.paused)
        else:
            self.hud.draw_menu(self.menu, self.width, self.height)
            if self.menu.screen == Screen.LOADING:
                self.loading_visible = True

    def close(self):
        self.pointer.set_active(False)
        self.hud.close()
        if self.batches:
            gl.glDeleteBuffers(len(self.batches), [batch.vbo for batch in self.batches])
        if self.renderer:
            self.renderer.close()
        if self.executor:
            self.executor.shutdown(wait=True, cancel_futures=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Walking the Walk: CS Jungle')
    parser.add_argument('--windowed', action='store_true', help='Start in a window; fullscreen is the default')
    parser.add_argument('--seed', type=int, default=42)
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
            dt = min(clock.tick(60)/1000, .1)
            for event in pygame.event.get():
                app.handle_event(event)
            app.update(dt)
            app.render(clock.get_fps())
            error = gl.glGetError()
            if error != gl.GL_NO_ERROR:
                raise RuntimeError(f'OpenGL frame error: {error}')
            pygame.display.flip()
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
