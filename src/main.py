import math
import pygame

from engine.framebuffer import Framebuffer
from engine.renderer import Renderer
from engine.opengl_renderer import OpenGLRenderer
from engine.mesh import create_prism
from engine.camera import Camera

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

angle = 0.0

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

    scene = [
        create_prism(
            2, 2, 2,
            (220, 80, 80),
            (0, 0, 8)
        ),
        create_prism(
            1, 4, 1,
            (80, 220, 80),
            (5, 0, 12)
        ),
        create_prism(
            4, 1, 2,
            (80, 80, 220),
            (-5, 0, 15)
        ),
    ]

    if use_opengl:
        import OpenGL.GL as gl
        gl.glViewport(0, 0, WIDTH, HEIGHT)
        gl.glClearColor(20/255, 20/255, 30/255, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        for mesh in scene:
            renderer.render_mesh(camera, None, mesh)
    else:
        framebuffer.clear((20, 20, 30))
        for mesh in scene:
            renderer.render_mesh(camera, framebuffer, mesh)
        framebuffer.present(screen)

    pygame.display.flip()

pygame.quit()
