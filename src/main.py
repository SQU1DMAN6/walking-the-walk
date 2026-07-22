import math
import pygame

from engine import *

WIDTH = 800
HEIGHT = 600

def create_cube():
    return [
        Vec3(-1, -1, -1),
        Vec3( 1, -1, -1),
        Vec3( 1,  1, -1),
        Vec3(-1,  1, -1),
        Vec3(-1, -1,  1),
        Vec3( 1, -1,  1),
        Vec3( 1,  1,  1),
        Vec3(-1,  1,  1),
    ]

EDGES = [
    (0,1),(1,2),(2,3),(3,0),
    (4,5),(5,6),(6,7),(7,4),
    (0,4),(1,5),(2,6),(3,7)
]

pygame.init()

screen = pygame.display.set_mode((WIDTH , HEIGHT))

clock = pygame.time.Clock()

framebuffer = Framebuffer(WIDTH, HEIGHT)

renderer = Renderer(WIDTH, HEIGHT)

cube = create_cube()

angle = 0.0

while True:
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            break

    angle += dt

    framebuffer.clear((20, 20, 30))

    renderer.draw_wire_cube(
        framebuffer,
        cube,
        EDGES,
        angle
    )

    framebuffer.present(screen)

    pygame.display.flip()

pygame.quit()

