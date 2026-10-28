from enum import Enum
import pygame
from engine.run_config import RunConfig, DIFFICULTIES, LENGTHS


class Screen(Enum):
    TITLE = 'title'
    PLAY = 'play'
    ABOUT = 'about'
    LOADING = 'loading'
    TUTORIAL = 'tutorial'
    RUN = 'run'


TITLE_BUTTONS = ('Play', 'Tutorial', 'About This Game')
ABOUT_TEXT = "Walking the Walk is a game for a Digital Technology CAT, written by Quan Thai from THE 9D, using a framebuffer 3D renderer (custom QT-made rendering engine) and pure FtR energy. I hope you enjoy."


class MenuFlow:
    def __init__(self):
        self.screen = Screen.TITLE
        self.selected = 0
        self.elapsed = 0.0
        self.error = None
        self.config = RunConfig()
        self.config_row = 0
        self.run_requested = False

    def activate(self, index):
        if self.screen != Screen.TITLE or not 0 <= index < len(TITLE_BUTTONS):
            return
        self.selected = index
        self.screen = (Screen.PLAY, Screen.LOADING, Screen.ABOUT)[index]
        self.error = None
        if index == 1:
            self.run_requested = False

    def back(self):
        self.screen = Screen.TITLE
        self.error = None

    def key(self, key):
        if self.screen == Screen.TITLE:
            if key in (pygame.K_UP, pygame.K_DOWN):
                self.selected = (self.selected + (-1 if key == pygame.K_UP else 1)) % len(TITLE_BUTTONS)
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.activate(self.selected)
        elif self.screen == Screen.PLAY and key != pygame.K_ESCAPE:
            if key in (pygame.K_UP, pygame.K_DOWN):
                self.config_row = (self.config_row+(-1 if key == pygame.K_UP else 1)) % 3
            elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):
                if self.config_row == 2:
                    if key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.start_run()
                else:
                    choices = list(DIFFICULTIES if self.config_row == 0 else LENGTHS)
                    current = self.config.difficulty if self.config_row == 0 else self.config.length
                    self.choose(self.config_row, choices[(choices.index(current)+(-1 if key == pygame.K_LEFT else 1)) % 3])
        elif key == pygame.K_ESCAPE:
            self.back()

    def choose(self, row, choice):
        self.config = RunConfig(choice if row == 0 else self.config.difficulty,
                                choice if row == 1 else self.config.length)

    def start_run(self):
        self.run_requested = True
        self.screen, self.error = Screen.LOADING, None

    @staticmethod
    def config_layout(width, height):
        cell = min(240, (width-88)//3)
        left = (width-(cell*3+24))//2
        groups = [[pygame.Rect(left+i*(cell+12), int(height*ratio), cell, 48) for i in range(3)]
                  for ratio in (.31, .49)]
        start = pygame.Rect((width-min(420, width-64))//2, height-154, min(420, width-64), 50)
        return groups, start

    @staticmethod
    def layout(width, height):
        button_width = min(420, width-64)
        button_height = max(48, min(66, height//11))
        top = int(height*.43) if height>=600 else 136+round((height-480)*.3)
        buttons = [pygame.Rect((width-button_width)//2, top+i*(button_height+14),
                               button_width, button_height) for i in range(3)]
        back = pygame.Rect((width-button_width)//2, height-button_height-40, button_width, button_height)
        return buttons, back

    def mouse(self, position, width, height, clicked=False):
        buttons, back = self.layout(width, height)
        if self.screen == Screen.TITLE:
            for index, button in enumerate(buttons):
                if button.collidepoint(position):
                    self.selected = index
                    if clicked:
                        self.activate(index)
                    return
        elif clicked:
            if back.collidepoint(position):
                self.back()
            elif self.screen == Screen.PLAY:
                groups, start = self.config_layout(width, height)
                for row, (options, rects) in enumerate(zip((DIFFICULTIES, LENGTHS), groups)):
                    for choice, rect in zip(options, rects):
                        if rect.collidepoint(position):
                            self.config_row = row
                            self.choose(row, choice)
                if start.collidepoint(position):
                    self.start_run()
