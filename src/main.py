import math
import pygame

from engine.framebuffer import Framebuffer
from engine.renderer import Renderer
from engine.opengl_renderer import OpenGLRenderer
from engine.mesh import create_prism, create_pyramid, create_ground
from engine.camera import Camera
from engine.worldgen import generate_world, get_terrain_height

WIDTH = 800
HEIGHT = 600

pygame.init()

use_opengl = True

if use_opengl:
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
else:
    screen = pygame.display.set_mode((WIDTH, HEIGHT))

pygame.event.set_grab(True)
pygame.mouse.set_visible(False)

clock = pygame.time.Clock()

renderer = OpenGLRenderer(WIDTH, HEIGHT) if use_opengl else Renderer(WIDTH, HEIGHT)

camera = Camera()

# Generate the procedural world once
WORLD_SEED = 42
world_meshes = generate_world(seed=WORLD_SEED, terrain_size=100, terrain_segments=30)

running = True

while running:
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if (
            event.type == pygame.KEYDOWN
            and
            event.key == pygame.K_ESCAPE
        ):
            running = False

    camera.update(dt)

    # Terrain-following collision: keep camera at terrain height + eye level
    terrain_y = get_terrain_height(camera.x, camera.z, WORLD_SEED, 1.5)
    eye_height = 1.6
    if camera.y < terrain_y + eye_height:
        camera.y = terrain_y + eye_height

    if use_opengl:
        import OpenGL.GL as gl
        gl.glViewport(0, 0, WIDTH, HEIGHT)

        gl.glClearColor(90/255, 160/255, 205/255, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        for mesh in world_meshes:
            renderer.render_mesh(camera, None, mesh)
    else:
        framebuffer.clear((180, 120, 80))
        for mesh in world_meshes:
            renderer.render_mesh(camera, framebuffer, mesh)
        framebuffer.present(screen)

    pygame.display.flip()

pygame.quit()
