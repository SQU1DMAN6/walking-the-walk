import math
import pygame

from engine.framebuffer import Framebuffer
from engine.renderer import Renderer
from engine.mesh import create_prism
from engine.camera import Camera

WIDTH = 800
HEIGHT = 600

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))

pygame.event.set_grab(True)
pygame.mouse.set_visible(False)

clock = pygame.time.Clock()

framebuffer = Framebuffer(WIDTH, HEIGHT)

renderer = Renderer(WIDTH, HEIGHT)

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

    framebuffer.clear((20, 20, 30))

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

    for mesh in scene:
        renderer.render_mesh(camera, framebuffer, mesh)

    framebuffer.present(screen)

    pygame.display.flip()

pygame.quit()
