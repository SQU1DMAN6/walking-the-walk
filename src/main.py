"""Walking The Walk, Level 1."""
import math
import sys

import pygame
from screeninfo import get_monitors

from engine.bitmapfont import text_surface
from engine.framebuffer import Framebuffer
from engine.renderer import Renderer
from engine.opengl_renderer import OpenGLRenderer
from engine.camera import Camera
from engine.mesh import Mesh
from engine.markers import (
    create_target_ring,
    create_arrow,
)
from engine.level1 import Level1, STATE_COMBAT
from engine.ui import (
    surface_to_texture, draw_hud, draw_notification,
    draw_death_screen, draw_completion_screen, begin_2d, end_2d
)

fs_w = 1400
fs_h = 1050

for m in get_monitors():
    if m.is_primary:
        print(f"Width: {m.width}, Height: {m.height}")
        fs_w = m.width
        fs_h = m.height
        break

WIDTH = 1400
HEIGHT = 1050

pygame.init()
pygame.display.set_caption("Walking The Walk")

use_opengl = True
is_fullscreen = False

flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE if use_opengl else pygame.RESIZABLE
screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

pygame.event.set_grab(True)
pygame.mouse.set_visible(False)
pygame.mouse.set_pos(WIDTH // 2, HEIGHT // 2)

clock = pygame.time.Clock()

camera = Camera()
renderer = OpenGLRenderer(WIDTH, HEIGHT) if use_opengl else Renderer(WIDTH, HEIGHT)
framebuffer = Framebuffer(WIDTH, HEIGHT) if not use_opengl else None

# Initialize Level 1
level = Level1(camera)
fps_display = 0
fps_accumulator = 0.0
fps_frame_count = 0

# Game loop
running = True
while running:
    dt = clock.tick(60) / 1000.0

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if pygame.event.get_grab():
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                else:
                    running = False

            if event.key == pygame.K_q and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                running = False

            if event.key == pygame.K_r and level.state == 6:  # STATE_DEATH
                level.reset()

            if event.key == pygame.K_f and pygame.event.get_grab() and not level.level_complete:
                level.handle_interaction()

        if event.type == pygame.MOUSEBUTTONDOWN and pygame.event.get_grab():
            if event.button == 1 and not level.level_complete:
                level.handle_attack()

    # Update camera
    camera.window_center = (WIDTH, HEIGHT)
    camera.grab_active = pygame.event.get_grab()

    # Track movement for tutorial
    prev_x, prev_z = camera.x, camera.z
    camera.update(dt)
    dx = camera.x - prev_x
    dz = camera.z - prev_z
    level.movement_distance += math.sqrt(dx * dx + dz * dz)
    level.look_rotation_total += abs(camera.yaw)

    # Update level
    level.update(dt)

    # Render
    if use_opengl:
        import OpenGL.GL as gl
        gl.glClearColor(90/255, 160/255, 205/255, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        # Render terrain
        if level.terrain_mesh:
            renderer.render_mesh_dynamic(camera, level.terrain_mesh, 0, 0, 0)

        # Render world meshes (trees, bushes, rocks, grass)
        for mesh in level.world_meshes:
            renderer.render_mesh_dynamic(camera, mesh, mesh.position[0], mesh.position[1], mesh.position[2])

        # Render objective marker: compact semi-transparent ground ring around the target
        obj_pos = level.get_objective_position()
        if obj_pos is not None:
            ring = create_target_ring(radius=1.4, thickness=0.14, colour=(255, 200, 50))
            renderer.render_mesh_dynamic(camera, ring, obj_pos[0], obj_pos[1], obj_pos[2])

            # If the objective is a living emu, skip the arrow (emu is the target itself)
            if level.state != STATE_COMBAT or level.emu is None or not level.emu_alive:
                # Floating arrow in front of the player pointing toward the objective
                dx = obj_pos[0] - camera.x
                dz = obj_pos[2] - camera.z
                if dx != 0.0 or dz != 0.0:
                    dist = math.sqrt(dx*dx + dz*dz)
                    angle = math.atan2(dx, dz)  # yaw to face the objective
                    # Position arrow ~2.3 units in front of the player, at eye height
                    ax = camera.x + math.sin(camera.yaw) * 2.3
                    az = camera.z + math.cos(camera.yaw) * 2.3
                    ay = camera.y - camera.eye_height + 1.2
                    stem, head = create_arrow()
                    # Rotate the arrow so its +Z axis points toward the objective
                    renderer.render_mesh_dynamic(camera, stem, ax, ay, az, yaw=angle)
                    renderer.render_mesh_dynamic(camera, head, ax, ay, az, yaw=angle)

        # Render emu using billboard sprite
        if level.emu is not None and level.emu_alive:
            surf, ex, ey, ez, w, h = level.emu.billboard(camera.x, camera.z)
            if surf is not None:
                renderer.render_billboard(camera, surf, ex, ey, ez, w, h)

        # Render branch and spear objects in the world (level 1 tutorials props)
        if level.branch_mesh is not None:
            renderer.render_mesh_dynamic(camera, level.branch_mesh,
                                         level.branch_mesh.position[0],
                                         level.branch_mesh.position[1],
                                         level.branch_mesh.position[2])
        if level.spear_meshes is not None:
            renderer.render_mesh_dynamic(camera, level.spear_meshes,
                                         level.spear_meshes.position[0],
                                         level.spear_meshes.position[1],
                                         level.spear_meshes.position[2])

    # Draw UI
    if use_opengl:
        import OpenGL.GL as gl
        fps_accumulator += clock.get_time()
        fps_frame_count += 1
        if fps_accumulator >= 500.0:
            fps_display = int(fps_frame_count * 1000.0 / fps_accumulator)
            fps_accumulator = 0.0
            fps_frame_count = 0

        draw_hud(gl, level, WIDTH, HEIGHT, text_surface, fps_display)
        draw_notification(gl, level, WIDTH, HEIGHT, text_surface)
        draw_death_screen(gl, level, WIDTH, HEIGHT, text_surface)
        draw_completion_screen(gl, level, WIDTH, HEIGHT, text_surface)

    pygame.display.flip()

pygame.quit()
sys.exit()
