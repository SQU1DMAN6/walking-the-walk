import pygame
from pygame._sdl2 import Window


class PointerCapture:
    def __init__(self):
        self.window = Window.from_display_module()
        self.active = False
        self._settling_frames = 0

    def set_active(self, active):
        if active == self.active:
            return
        pygame.event.set_grab(active)
        pygame.mouse.set_visible(not active)
        self.window.relative_mouse = active
        pygame.mouse.get_rel()
        self.active = active
        self._settling_frames = 2 if active else 0

    def delta(self):
        # Ghost motion after capture changes doesn't get a vote.
        motion = pygame.mouse.get_rel()

        if not self.active or self._settling_frames:
            self._settling_frames = max(0, self._settling_frames-1)
            return 0, 0
        return motion
