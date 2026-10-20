import math
import pygame
from engine.bitmapfont import text_surface
from engine.items import ITEMS, RECIPES, RECIPE_ORDER, DOG_HEALTH, USE_DURATION
from engine.menu import Screen, TITLE_BUTTONS, ABOUT_TEXT
from engine.prompts import project
from engine.level1 import Stage
from engine.animation import ease
from engine.run_config import DIFFICULTIES, LENGTHS


class BitmapFont:
    def __init__(self, scale):
        self.scale = scale

    def render(self, text, antialias, colour):
        source = text_surface(text, colour=colour, spacing=1)
        return pygame.transform.smoothscale(source, (max(1, round(source.get_width()*self.scale)),
                                                     max(1, round(source.get_height()*self.scale))))

    def size(self, text):
        from engine.bitmapfont import _WIDTH, _HEIGHT
        return round((len(text)*(_WIDTH+1)+1)*self.scale), round((_HEIGHT+4)*self.scale)


class TutorialHUD:
    def __init__(self):
        self.texture = None
        self._font_height = None
        self._text_cache = {}
        self._intro_start = None
        self._intro_finished = False
        self.mouse_pos = None
        self._pressed_rect = None
        self._pressed_until = 0
        self._lesson_key = None
        self._lesson_since = 0.0
        self._fonts(800)

    def _fonts(self, height, width=1280):
        if self._font_height == (width, height):
            return
        self._font_height = width, height
        scale = max(.58, min(1.15, height/900, width/1100))
        self.font = BitmapFont(scale)
        self.title_font = BitmapFont(scale*1.2)
        self.logo_font = BitmapFont(scale*1.8)
        self.small_font = BitmapFont(scale*.78)
        self.slot_font = BitmapFont(max(.40, scale*.60))
        self._text_cache.clear()

    def text(self, surface, text, x, y, colour=(231, 239, 225), font=None, center=False):
        font = font or self.font
        key = (text, colour, font.scale)
        rendered = self._text_cache.get(key)
        if rendered is None:
            rendered = font.render(text, True, colour)
            if len(self._text_cache) > 256:
                self._text_cache.clear()
            self._text_cache[key] = rendered
        surface.blit(rendered, (x-rendered.get_width()//2 if center else x, y))

    @staticmethod
    def panel(surface, rect, selected=False):
        pygame.draw.rect(surface, (12, 25, 21, 228), rect, border_radius=9)
        pygame.draw.rect(surface, (248, 221, 122) if selected else (91, 130, 105, 180), rect, 2 if selected else 1, border_radius=9)

    def press_button(self, rect):
        self._pressed_rect = tuple(rect)
        self._pressed_until = pygame.time.get_ticks()+180

    def button(self, surface, rect, label, selected=False, enabled=True):
        hovered = self.mouse_pos is not None and rect.collidepoint(self.mouse_pos)
        pressed = self._pressed_rect == tuple(rect) and pygame.time.get_ticks() < self._pressed_until
        colour = (56, 63, 58) if not enabled else (48, 91, 66) if hovered else (22, 47, 37)
        if pressed:
            colour = (100, 91, 49)
        pygame.draw.rect(surface, colour, rect, border_radius=8)
        pygame.draw.rect(surface, (248, 221, 122) if selected or pressed else (126, 169, 139), rect, 2 if selected or hovered or pressed else 1, border_radius=8)
        font = self.font
        if font.size(label)[0] > rect.width-20:
            font = BitmapFont(font.scale*(rect.width-20)/font.size(label)[0])
        self.text(surface, label, rect.centerx, rect.centery-font.size('A')[1]//2,
                  (233, 240, 225) if enabled else (176, 185, 178), font, center=True)

    def lines(self, text, width, font=None):
        font = font or self.font
        lines, line = [], ''
        for word in text.split():
            candidate = (line + ' ' + word).strip()
            if font.size(candidate)[0] > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        return [*lines, line]

    def wrapped(self, surface, text, x, y, width, colour=(218, 228, 207), font=None, center=False):
        font = font or self.font
        step = font.size('A')[1]+4
        for line in self.lines(text, width, font):
            self.text(surface, line, x, y, colour, font, center)
            y += step
        return y

    def coach(self, surface, text, target, rect):
        rect = rect.copy()
        rect.height = max(rect.height, len(self.lines(text, rect.width-16, self.small_font))*(self.small_font.size('A')[1]+4)+10)
        pygame.draw.line(surface, (255, 229, 123), rect.midbottom, target, 2)
        dx, dy = target[0]-rect.centerx, target[1]-rect.bottom
        length = max(1, math.hypot(dx, dy))
        ux, uy = dx/length, dy/length
        pygame.draw.polygon(surface, (255, 229, 123), [target,
            (target[0]-ux*10-uy*5, target[1]-uy*10+ux*5),
            (target[0]-ux*10+uy*5, target[1]-uy*10-ux*5)])
        self.panel(surface, rect, True)
        self.wrapped(surface, text, rect.centerx, rect.y+5, rect.width-16,
                     (255, 235, 155), self.small_font, center=True)

    @staticmethod
    def crafting_close_rect(width, height):
        panel, _, _ = TutorialHUD.crafting_layout(width, height)
        return pygame.Rect(panel.right-134, panel.y+14, 116, 44)

    @staticmethod
    def crafting_layout(width, height):
        panel = pygame.Rect((width-min(880, width-32))//2, (height-min(570, height-32))//2,
                            min(880, width-32), min(570, height-32))
        list_width = max(165, int(panel.width*.30))
        rows = [pygame.Rect(panel.x+18, panel.y+87+i*83, list_width, 72) for i in range(len(RECIPE_ORDER))]
        button = pygame.Rect(panel.x+list_width+42, panel.bottom-115, panel.width-list_width-62, 51)
        return panel, rows, button

    def handle_crafting_click(self, level, position, width, height):
        close = self.crafting_close_rect(width, height)
        if close.collidepoint(position):
            self.press_button(close)
            return level.toggle_crafting()
        _, rows, button = self.crafting_layout(width, height)
        for i, row in enumerate(rows):
            if row.collidepoint(position):
                self.press_button(row)
                level.selected_recipe = i
                return True
        if button.collidepoint(position):
            self.press_button(button)
            return level.craft()
        return False

    def crafting_menu(self, surface, level, width, height):
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((5, 15, 13, 210))
        surface.blit(shade, (0, 0))
        panel, rows, button = self.crafting_layout(width, height)
        self.panel(surface, panel)
        self.text(surface, 'CRAFTING TIME', panel.centerx, panel.y+20, (248, 221, 122), self.title_font, center=True)
        close = self.crafting_close_rect(width, height)
        self.button(surface, close, 'Close [C]')
        for i, (recipe_id, rect) in enumerate(zip(RECIPE_ORDER, rows)):
            self.button(surface, rect, RECIPES[recipe_id]['name'], i == level.selected_recipe)
        recipe_id = RECIPE_ORDER[level.selected_recipe]
        recipe = RECIPES[recipe_id]
        ready, reason = level.recipe_status(recipe_id)
        x, y = button.x, panel.y+89
        y += self.font.size('A')[1]+16
        for item, qty in recipe['materials'].items():
            count = level.inventory.count(item)
            y = self.wrapped(surface, f'{ITEMS[item][0]}: {count} / {qty}', x, y, button.width,
                             (143, 223, 166) if count >= qty else (255, 172, 110))
            y += 8
        self.wrapped(surface, reason, x, y+12, button.width,
                     (143, 223, 166) if ready else (248, 221, 122), self.small_font)
        self.button(surface, button, 'Press [Enter] to craft' if ready else 'Not ready', enabled=ready)
        self.text(surface, '[Up/Down] choose | [Enter] craft | [C]/[Esc] back', panel.centerx, panel.bottom-45,
                  font=self.small_font, center=True)
        guidance = level.action_coach()
        if guidance:
            expected = 0 if level.state == Stage.COMPASS else 1
            if guidance.kind == 'recipe':
                target = rows[expected].midbottom
                rect = pygame.Rect(rows[expected].x, rows[-1].bottom+15, rows[expected].width, 56)
            elif guidance.kind == 'craft':
                target = button.midtop
                rect = pygame.Rect(button.x, button.y-56, button.width, 42)
            elif guidance.kind == 'close':
                target = close.midbottom
                rect = pygame.Rect(close.x-80, rows[-1].bottom+15, close.width+80, 56)
            else:
                target = (button.centerx, panel.y+125)
                rect = pygame.Rect(button.x, button.y-56, button.width, 42)
            self.coach(surface, guidance.text, target, rect)

    @staticmethod
    def overlay_layout(width, height):
        panel = pygame.Rect((width-min(680, width-32))//2, (height-min(370, height-32))//2,
                            min(680, width-32), min(370, height-32))
        rows = [pygame.Rect(panel.x+32, panel.y+140+i*62, panel.width-64, 48) for i in range(3)]
        return panel, rows

    def handle_overlay_click(self, level, position, width, height, paused=False):
        _, rows = self.overlay_layout(width, height)
        for index, rect in enumerate(rows):
            if rect.collidepoint(position):
                self.press_button(rect)
                return (('resume' if paused and level.active else 'restart'), 'title', 'quit')[index]
        return None

    def overlay_menu(self, surface, level, width, height, paused):
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((5, 15, 13, 218))
        surface.blit(shade, (0, 0))
        panel, rows = self.overlay_layout(width, height)
        self.panel(surface, panel)
        title = 'PAUSED' if paused and level.active else level.instruction[0]
        self.text(surface, title, panel.centerx, panel.y+24, (248, 221, 122), self.title_font, center=True)
        self.text(surface, 'Choose below. [Esc] returns to the title.', panel.centerx, panel.y+88,
                  font=self.small_font, center=True)
        first = 'Resume [Enter]' if paused and level.active else 'Restart [R]'
        for rect, label in zip(rows, (first, 'Title screen [Esc]', 'Quit')):
            self.button(surface, rect, label)

    def _draw_publisher_intro(self, width, height):
        from OpenGL import GL as gl
        now = pygame.time.get_ticks() / 1000.0
        if self._intro_start is None:
            self._intro_start = now

        elapsed = now - self._intro_start
        duration = 3.2

        if elapsed >= duration:
            self._intro_finished = True
            return False

        if elapsed < 0.8:
            progress = elapsed / 0.8
        elif elapsed < 2.4:
            progress = 1.0
        else:
            progress = (duration - elapsed) / 0.8

        progress = max(.18, min(1.0, progress))
        progress = progress * progress * (3.0 - 2.0 * progress)

        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill((12, 25, 21))

        gold = tuple(round(c * progress) for c in (248, 221, 122))
        white = tuple(round(c * progress) for c in (231, 239, 225))

        self.text(
            surface, "The FtR Project",
            width // 2, height // 2 - 40,
            gold, self.logo_font, center=True
        )
        self.text(
            surface, "PRESENTS...",
            width // 2, height // 2 + 20,
            white, self.font, center=True
        )
        self.text(surface, 'Press any key or click to continue', width//2, height-65,
                  font=self.small_font, center=True)

        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        self.present(surface)
        return True

    def draw_menu(self, menu, width, height):
        from OpenGL import GL as gl
        self._fonts(height, width)

        if menu.screen == Screen.TITLE and not self._intro_finished:
            if self._draw_publisher_intro(width, height):
                return

        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill((92, 165, 224))
        pygame.draw.circle(surface, (210, 228, 201), (int(width*.82), int(height*.19)), max(24, height//15))
        for layer, colour in enumerate(((55, 103, 85), (28, 66, 52), (17, 44, 35))):
            base = int(height*(.51+layer*.13))
            pygame.draw.rect(surface, colour, (0, base, width, height-base))
            for index, x in enumerate(range(-50, width+80, 75-layer*9)):
                tree_height = int(height*(.12+layer*.03))+(index*37 % 65)
                pygame.draw.rect(surface, colour, (x-4, base-tree_height//2, 8, tree_height))
                pygame.draw.polygon(surface, colour, [(x-49, base-12), (x, base-tree_height), (x+49, base-12)])
        pygame.draw.polygon(surface, (113, 109, 69), [(int(width*.48), int(height*.54)),
            (int(width*.56), int(height*.54)), (int(width*.43), int(height*.76)),
            (int(width*.66), height), (int(width*.17), height), (int(width*.35), int(height*.75))])
        buttons, back = menu.layout(width, height)
        if menu.screen == Screen.TITLE:
            self.text(surface, 'Walking the Walk', width//2, int(height*.16), (248, 221, 122), self.logo_font, center=True)
            self.text(surface, 'Written by Quan Thai', width//2, int(height*.16)+self.logo_font.size('A')[1]+18,
                      font=self.font, center=True)
            self.text(surface, 'Version 1', width//2, int(height*.16)+self.logo_font.size('A')[1]+50,
                      font=self.font, center=True)
            for index, (label, button) in enumerate(zip(TITLE_BUTTONS, buttons)):
                self.button(surface, button, label, index == menu.selected)
            rect = pygame.Rect(buttons[1].right+10, buttons[1].y, min(180, width-buttons[1].right-26), buttons[1].height)
            if rect.width >= 140:
                self.coach(surface, 'Start with Tutorial', buttons[1].midright, rect)
            else:
                self.text(surface, 'Start here: Tutorial', width//2, buttons[2].bottom+12,
                          (248, 221, 122), self.small_font, center=True)
            self.text(surface, 'Click a button | [Up/Down] choose | [Enter] open | [Esc] quit', width//2, height-42,
                      font=self.small_font, center=True)
        elif menu.screen == Screen.PLAY:
            self.text(surface, 'CONFIGURE YOUR RUN', width//2, 35, (248, 221, 122), self.title_font, True)
            groups, start = menu.config_layout(width, height)
            for row, (heading, options, rects, selected) in enumerate(zip(
                    ('Difficulty', 'World length'), (DIFFICULTIES, LENGTHS), groups,
                    (menu.config.difficulty, menu.config.length))):
                self.text(surface, heading, width//2, rects[0].top-31, font=self.font, center=True)
                for choice, rect in zip(options, rects):
                    self.button(surface, rect, choice, choice == selected)
            self.button(surface, start, 'Start run [Enter]', menu.config_row == 2)
            self.button(surface, back, 'Back to title [Esc]')
            self.text(surface, '[Up/Down] row | [Left/Right] choose', width//2,
                      height-self.small_font.size('A')[1]-6, font=self.small_font, center=True)
        else:
            panel = pygame.Rect(24, int(height*.18), width-48, int(height*.52))
            self.panel(surface, panel)
            title, message = {
                Screen.ABOUT: ('ABOUT THIS GAME', ABOUT_TEXT),
                Screen.LOADING: ('HEADING INTO CS JUNGLE', 'Getting the forest ready. Hang tight.'),
            }[menu.screen]
            self.text(surface, title, width//2, panel.y+30, (248, 221, 122), self.title_font, center=True)
            self.wrapped(surface, menu.error or message, width//2, panel.y+95, panel.width-48, font=self.small_font, center=True)
            if menu.screen == Screen.LOADING and not menu.error:
                for index in range(12):
                    angle = index*math.tau/12+menu.elapsed*4
                    colour = tuple(int(value*(.3+.7*index/11)) for value in (248, 221, 122))
                    pygame.draw.circle(surface, colour,
                        (int(width/2+24*math.cos(angle)), int(panel.bottom-55+24*math.sin(angle))), 4)
            self.button(surface, back, 'Back to title [Esc]', True)
        gl.glClearColor(.36, .65, .88, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        self.present(surface)

    @staticmethod
    def icon(surface, item, x, y):
        ink = (220, 227, 210)
        if item in ('food', 'water'):
            rect = (x-8, y-12, 16, 26)
            pygame.draw.rect(surface, (138, 195, 217) if item == 'water' else (168, 180, 184), rect, border_radius=4)
            if item == 'water':
                pygame.draw.rect(surface, (81, 117, 202), (x-5, y-17, 10, 7))
            else:
                pygame.draw.ellipse(surface, ink, (x-8, y-14, 16, 6))
        elif item == 'compass':
            pygame.draw.circle(surface, (192, 161, 90), (x, y), 15)
            pygame.draw.circle(surface, (235, 225, 189), (x, y), 11)
            pygame.draw.polygon(surface, (235, 46, 54), [(x, y-9), (x-4, y+5), (x+4, y+5)])
        elif item in ('stick', 'spear'):
            pygame.draw.line(surface, (175, 127, 73), (x-10, y+12), (x+9, y-12), 4)
            if item == 'spear':
                pygame.draw.polygon(surface, ink, [(x+12, y-16), (x+2, y-10), (x+9, y-5)])
            else:
                pygame.draw.line(surface, (175, 127, 73), (x, y), (x+10, y+3), 3)
        elif item == 'rock':
            pygame.draw.polygon(surface, (162, 170, 157), [(x-13, y+7), (x-8, y-9), (x+6, y-13), (x+13, y+8), (x, y+13)])
        else:
            pygame.draw.rect(surface, (162, 179, 186) if item == 'metal_scrap' else (111, 184, 209),
                             (x-11, y-8, 23, 17), border_radius=2)

    @staticmethod
    def hotbar_layout(width, height):
        cell = min(width-32, 1160)//10
        left, top = (width-cell*10)//2, height-84
        return [pygame.Rect(left+i*cell, top, cell-4, 72) for i in range(10)]

    def selected_text(self, level):
        item = level.inventory.selected_item
        if item is None:
            return 'Empty hand' if level.inventory.selected_slot == 9 else 'Empty slot'
        name = ITEMS[item][0]
        qty = level.inventory.slots[level.inventory.selected_slot][1]
        if item in ('food', 'water'):
            _, hint = level.use_status()
        elif item == 'spear':
            _, hint = level.attack_status()
        elif item == 'compass':
            guidance = level.compass_guidance()
            angle, distance, _ = guidance
            turn = 'ahead' if abs(angle) < .25 else 'right' if angle > 0 else 'left'
            hint = f'Beacon {distance:.0f}m {turn}'
        else:
            hint = '[C]: crafting material'
        return f'{name} x{qty} | {hint}'

    def direction_panel(self, surface, guidance, lesson=None):
        font = self.small_font
        title = self.lines(guidance.name, 146, font)
        detail = self.lines(f'{guidance.remaining} left | {guidance.distance:.0f}m', 146, font)
        rect = pygame.Rect(12, 126, 210, 22+(len(title)+len(detail))*(font.size('A')[1]+4))
        if lesson and rect.colliderect(lesson):
            if lesson.top-rect.height >= 117:
                rect.bottom = lesson.top
            else:
                rect.top = lesson.bottom+12
        self.panel(surface, rect)
        colour = (255, 164, 104) if guidance.danger else (255, 229, 123)
        cx, cy = rect.x+26, rect.centery
        ca, sa = math.cos(guidance.relative), math.sin(guidance.relative)
        points = [(0, -18), (-10, 0), (-4, 0), (-4, 18), (4, 18), (4, 0), (10, 0)]
        pygame.draw.polygon(surface, colour, [(cx+x*ca-y*sa, cy+x*sa+y*ca) for x, y in points])
        y = rect.y+10
        for line in title+detail:
            self.text(surface, line, rect.x+56, y, colour, font)
            y += font.size('A')[1]+4
        return rect

    def prompt_rect(self, level, width, height, bottom):
        prompt = level.world_prompt()
        if prompt is None:
            return None
        point = project(level.camera, prompt.position, width, height)
        if point is None:
            return None
        text_width = max(self.small_font.size(prompt.title)[0], self.small_font.size(prompt.text)[0])+28
        w = min(width//2-40, 360, text_width)
        lines = self.lines(prompt.text, w-24, self.small_font)
        h = 22+self.small_font.size('A')[1]*(len(lines)+1)
        x = max(16, min(width-w-16, point[0]-w/2))
        y = max(126, min(bottom-h-10, point[1]-h-8))
        return prompt, pygame.Rect(x, y, w, h), point

    def controls_overlay(self, surface, width, height):
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((5, 15, 13, 224))
        surface.blit(shade, (0, 0))
        panel = pygame.Rect(16, 16, width-32, height-32)
        self.panel(surface, panel)
        self.text(surface, 'CONTROLS', width//2, 30, (248, 221, 122), self.title_font, center=True)
        rows = [('W, A, S, D', 'Move'), ('Mouse', 'Look around'), ('Shift', 'Sprint; stop to recover stamina'),
                ('F', 'Pick up / interact'), ('1-9', 'Select inventory slot'), ('0', 'Empty hand'),
                ('Hold E', 'Use selected food / water'), ('C', 'Open / close crafting'),
                ('Up/Down, Enter', 'Choose / craft in the menu'), ('Left click', 'Attack with equipped spear'),
                ('H', 'Open / close these controls'), ('Esc', 'Pause / back'), ('R', 'Restart after death / completion')]
        font = self.small_font
        step = min(font.size('A')[1]+10, (height-135)//len(rows))
        x = max(32, (width-min(width-64, 840))//2)
        for index, (key, action) in enumerate(rows):
            self.text(surface, key, x, 85+index*step, (248, 221, 122), font)
            self.text(surface, action, x+int((width-64)*.30), 85+index*step, font=font)
        self.text(surface, '[H] or [Esc] to return', width//2, height-56, font=font, center=True)

    def lesson_progress(self, level):
        key = (level.inventory, level.state, level.instruction[1], level.in_beacon_ring)
        if key != self._lesson_key:
            self._lesson_key, self._lesson_since = key, level.elapsed
        return 0.0 if level.in_beacon_ring else ease((level.elapsed-self._lesson_since-1.5)/.45)

    def lesson_fonts(self, progress):
        return BitmapFont(self.font.scale*(1-.10*progress)), BitmapFont(self.title_font.scale*(1-.10*progress))

    def lesson_rect(self, level, width, height):
        progress = self.lesson_progress(level)
        font, title_font = self.lesson_fonts(progress)
        panel_width = round(min(width-32, 900)*(1-.08*progress))
        body = self.lines(level.instruction[1], panel_width-32, font)
        panel_height = 24+title_font.size('A')[1]+len(body)*(font.size('A')[1]+4)
        centre_top = height//2-panel_height//2
        lower_top = self.hotbar_layout(width, height)[0].top-56-panel_height
        top = round(centre_top+(lower_top-centre_top)*progress)
        return pygame.Rect((width-panel_width)//2, top, panel_width, panel_height)

    @staticmethod
    def lesson_colours(elapsed):
        # Keep the attention nudge on chill mode.
        pulse = .5+.5*math.cos(math.tau*elapsed/2.4)
        return (round(30+12*pulse), 23, 23, 236), (round(174+64*pulse), round(83+27*pulse), 90, 255)

    def lesson_panel(self, surface, level, rect):
        progress = self.lesson_progress(level)
        font, title_font = self.lesson_fonts(progress)
        background, border = self.lesson_colours(level.elapsed)
        background = tuple(round(a+(b-a)*progress) for a, b in zip(background, (42, 36, 15, 236)))
        border = tuple(round(a+(b-a)*progress) for a, b in zip(border, (248, 221, 122, 255)))
        pygame.draw.rect(surface, background, rect, border_radius=9)
        pygame.draw.rect(surface, border, rect, 3, border_radius=9)
        title, instruction = level.instruction
        heading = 'BEACON REACHED' if level.in_beacon_ring else f'{min(int(level.state)+1, 10)}/10  {title}'
        self.text(surface, heading, rect.centerx, rect.y+8, (255, 218, 169), title_font, center=True)
        self.wrapped(surface, instruction, rect.centerx, rect.y+16+title_font.size('A')[1], rect.width-32,
                     (247, 241, 229), font, center=True)

    def draw(self, level, width, height, fps, paused=False):
        self._fonts(height, width)
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        self.panel(overlay, (12, 12, 220, 105))
        for i, (label, value, maximum, colour) in enumerate([
                ('Health', level.camera.health, level.camera.max_health, (116, 201, 142)),
                ('Stamina', level.camera.stamina, level.camera.max_stamina, (115, 173, 207))]):
            y = 20+i*47
            text = f'{label} {int(value)}/{int(maximum)}'
            font = BitmapFont(self.small_font.scale*min(1, 198/self.small_font.size(text)[0]))
            self.text(overlay, text, 22, y, font=font)
            pygame.draw.rect(overlay, (42, 57, 47), (22, y+27, 198, 9), border_radius=3)
            pygame.draw.rect(overlay, colour, (22, y+27, int(198*max(0, min(1, value/maximum))), 9), border_radius=3)
        if level.health_flash_timer:
            colour = (104, 240, 147) if level.health_feedback == 'heal' else (255, 116, 101)
            pygame.draw.rect(overlay, colour, (12, 12, 220, 105), 3, border_radius=9)
        controls_width = max(140, self.small_font.size('[H] Controls')[0]+20)
        controls_height = self.small_font.size('A')[1]+self.slot_font.size('A')[1]+16
        self.panel(overlay, (width-controls_width-12, 12, controls_width, controls_height))
        self.text(overlay, '[H] Controls', width-self.small_font.size('[H] Controls')[0]-16, 16, font=self.small_font)
        self.text(overlay, f'{fps:.0f} FPS', width-100, 20+self.small_font.size('A')[1], font=self.slot_font)
        if level.dog and level.dog.state != 'idle':
            rect = pygame.Rect(width-200, max(71, controls_height+20), 188, 65)
            self.panel(overlay, rect)
            self.text(overlay, 'Back away!' if level.dog.state == 'windup' else 'Hostile dog', rect.x+10, rect.y+8,
                      (255, 172, 110), self.small_font)
            pygame.draw.rect(overlay, (70, 44, 35), (rect.x+10, rect.y+43, 168, 8))
            pygame.draw.rect(overlay, (224, 119, 85), (rect.x+10, rect.y+43, int(168*level.dog.health/DOG_HEALTH), 8))

        names = {'food': 'Food', 'water': 'Water', 'metal_scrap': 'Metal', 'plastic_scrap': 'Plastic',
                 'stick': 'Stick', 'rock': 'Rock', 'compass': 'Compass', 'spear': 'Spear'}
        cells = self.hotbar_layout(width, height)
        for i, rect in enumerate(cells):
            self.panel(overlay, rect, i == level.inventory.selected_slot)
            self.text(overlay, f'[{i+1 if i < 9 else 0}]', rect.x+5, rect.y+2, font=self.slot_font)
            slot = level.inventory.slots[i] if i < level.inventory.capacity else None
            if slot:
                item, qty = slot
                self.icon(overlay, item, rect.centerx, rect.y+34)
                self.text(overlay, names[item], rect.centerx, rect.y+52, font=self.slot_font, center=True)
                if qty > 1:
                    self.text(overlay, str(qty), rect.right-22, rect.y+2, font=self.slot_font)
            else:
                self.text(overlay, 'Hand' if i == 9 else 'Empty', rect.centerx, rect.y+52, font=self.slot_font, center=True)

        panel_width = min(width-32, 1160)
        coaching = level.action_coach() if not paused else None
        slot_coaching = coaching is not None and coaching.kind in ('slot', 'use')
        selected = self.selected_text(level).split(' | ')[0] if slot_coaching else self.selected_text(level)
        selection_lines = self.lines(selected, panel_width-24, self.small_font)
        selection_height = len(selection_lines)*(self.small_font.size('A')[1]+2)+12
        selection_y = cells[0].top-selection_height-8
        self.panel(overlay, ((width-panel_width)//2, selection_y, panel_width, selection_height))
        selection_center = int(width*.75 if coaching.slot < 5 else width*.25) if slot_coaching else width//2
        self.wrapped(overlay, selected, selection_center, selection_y+6, panel_width//2-24 if slot_coaching else panel_width-24,
                     (146, 227, 182), self.small_font, center=True)
        lesson = self.lesson_rect(level, width, height)
        lesson_visible = level.active and not (paused or level.help_open or level.crafting_open)
        if slot_coaching:
            cell = cells[coaching.slot]
            pygame.draw.rect(overlay, (255, 229, 123), cell, 3, border_radius=9)
            text_width = min(panel_width//2-12, self.small_font.size(coaching.text)[0]+20)
            x = max(16, min(width-text_width-16, cell.centerx-text_width//2))
            rect = pygame.Rect(x, selection_y, text_width, selection_height)
            self.coach(overlay, coaching.text, (cell.centerx, cell.top-2), rect)
        if level.use_progress:
            pygame.draw.rect(overlay, (38, 59, 45), ((width-panel_width)//2+10, selection_y+selection_height-7, panel_width-20, 5))
            pygame.draw.rect(overlay, (124, 218, 182), ((width-panel_width)//2+10, selection_y+selection_height-7,
                            int((panel_width-20)*level.use_progress/USE_DURATION), 5))

        direction = None if paused else level.objective_direction()
        direction_rect = self.direction_panel(overlay, direction, lesson if lesson_visible else None) if direction else None
        prompt_info = None if not lesson_visible or level.in_beacon_ring else self.prompt_rect(level, width, height, lesson.top)
        if prompt_info:
            prompt, rect, point = prompt_info
            if rect.colliderect(lesson):
                rect.top = lesson.bottom+10
            aim = pygame.Rect(width//2-12, height//2-12, 24, 24)
            if rect.colliderect(aim):
                rect.left = width//2+18
            if direction_rect and rect.colliderect(direction_rect):
                rect.x = min(width-rect.width-16, direction_rect.right+10)
            pygame.draw.line(overlay, (224, 215, 165), rect.midbottom, point, 1)
            self.panel(overlay, rect)
            self.text(overlay, prompt.title, rect.centerx, rect.y+6, (248, 221, 122), self.small_font, center=True)
            self.wrapped(overlay, prompt.text, rect.centerx, rect.y+10+self.small_font.size('A')[1], rect.width-24,
                         (217, 241, 221) if prompt.ready else (255, 185, 130), self.small_font, center=True)
        if (level.notification_timer > 0 and level.notification or level.objective_flash_timer) and not level.crafting_open:
            toast_width = min(440, max(168, width-480))
            lines = self.lines(level.notification, toast_width-20, self.small_font) if level.notification_timer else []
            if level.objective_flash_timer:
                lines.append('Objective complete')
            h = 12+len(lines)*(self.small_font.size('A')[1]+2)
            rect = pygame.Rect((width-toast_width)//2, 14, toast_width, h)
            self.panel(overlay, rect)
            for index, line in enumerate(lines):
                self.text(overlay, line, rect.centerx, rect.y+6+index*(self.small_font.size('A')[1]+2),
                          (248, 221, 122), self.small_font, center=True)
        if lesson_visible:
            self.lesson_panel(overlay, level, lesson)
        if lesson_visible and not lesson.collidepoint(width//2, height//2):
            pygame.draw.line(overlay, (241, 236, 211), (width//2-5, height//2), (width//2+5, height//2))
            pygame.draw.line(overlay, (241, 236, 211), (width//2, height//2-5), (width//2, height//2+5))
        if level.crafting_open:
            self.crafting_menu(overlay, level, width, height)
        if paused or not level.active:
            self.overlay_menu(overlay, level, width, height, paused)
        if level.help_open:
            self.controls_overlay(overlay, width, height)
        self.present(overlay)

    def present(self, surface):
        from OpenGL import GL as gl
        width, height = surface.get_size()
        data = pygame.image.tobytes(surface, 'RGBA', True)
        if self.texture is None:
            self.texture = gl.glGenTextures(1)
        gl.glUseProgram(0)
        gl.glBindVertexArray(0)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glOrtho(0, width, height, 0, -1, 1)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glColor4f(1, 1, 1, 1)
        gl.glBegin(gl.GL_QUADS)
        for u, v, x, y in [(0, 1, 0, 0), (1, 1, width, 0), (1, 0, width, height), (0, 0, 0, height)]:
            gl.glTexCoord2f(u, v)
            gl.glVertex2f(x, y)
        gl.glEnd()
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glEnable(gl.GL_DEPTH_TEST)

    def close(self):
        if self.texture is not None:
            from OpenGL import GL as gl
            gl.glDeleteTextures([self.texture])
            self.texture = None
