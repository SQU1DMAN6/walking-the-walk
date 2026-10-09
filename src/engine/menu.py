from enum import Enum
import pygame


class Screen(Enum):
    TITLE = 'title'
    PLAY = 'play'
    ABOUT = 'about'
    LOADING = 'loading'
    TUTORIAL = 'tutorial'


TITLE_BUTTONS = ('Play', 'Tutorial', 'About This Game')
ABOUT_TEXT = "Walking the Walk is a game for a Digital Technology CAT, written by Quan Thai from THE 9D, using a framebuffer 3D renderer (custom QT-made rendering engine) and pure FtR energy. I hope you enjoy."


class MenuFlow:
    def __init__(self):
        self.screen = Screen.TITLE
        self.selected = 0
        self.elapsed = 0.0
        self.error = None

    def activate(self, index):
        if self.screen != Screen.TITLE or not 0 <= index < len(TITLE_BUTTONS):
            return
        self.selected = index
        self.screen = (Screen.PLAY, Screen.LOADING, Screen.ABOUT)[index]
        self.error = None

    def back(self):
        self.screen = Screen.TITLE
        self.error = None

    def key(self, key):
        if self.screen == Screen.TITLE:
            if key in (pygame.K_UP, pygame.K_DOWN):
                self.selected = (self.selected + (-1 if key == pygame.K_UP else 1)) % len(TITLE_BUTTONS)
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.activate(self.selected)
        elif key == pygame.K_ESCAPE:
            self.back()

    @staticmethod
    def layout(width, height):
        button_width = min(420, width-64)
        button_height = max(48, min(66, height//11))
        top = int(height*.43)
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
        elif clicked and back.collidepoint(position):
            self.back()
