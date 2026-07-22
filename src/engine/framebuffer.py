import pygame

class Framebuffer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.surface = pygame.Surface(
            (width, height)
        )

    def clear(self, colour):
        self.surface.fill(colour)

    def set_pixel(self, x, y, colour):
        if (
            0 <= x < self.width and
            0 <= y < self.height
        ):
            self.surface.set_at(
                (x, y),
                colour
            )

    def present(self, screen):
        screen.blit(
            self.surface,
            (0, 0)
        )

