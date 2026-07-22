# `python main.py` or `python -m main`

import pygame

from engine import *

def main():
    WIDTH = 800
    HEIGHT = 600

    EDGES: list[tuple[int, int]] = [
        (0,1), (1,2), (2,3), (3,0),
        (4,5), (5,6), (6,7), (7,4),
        (0,4), (1,5), (2,6), (3,7)
    ]
    CUBE: list[Vec3] = [
        Vec3(-1, -1, -1),
        Vec3( 1, -1, -1),
        Vec3( 1,  1, -1),
        Vec3(-1,  1, -1),
        Vec3(-1, -1,  1),
        Vec3( 1, -1,  1),
        Vec3( 1,  1,  1),
        Vec3(-1,  1,  1),
    ]

    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    buf = Framebuffer(WIDTH, HEIGHT)
    renderer = Renderer(WIDTH, HEIGHT)

    angle = 0.0
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

            dt = clock.tick(60) / 1000.0
            angle += dt

            buf.clear((20, 20, 30))

            renderer.draw_wire_cube(
                buf,
                CUBE,
                EDGES,
                angle
            )

            buf.present(screen)

            pygame.display.flip()

    finally:
        pygame.quit() # idk, does pygame do this automatically?

if __name__ == '__main__':
    main()

