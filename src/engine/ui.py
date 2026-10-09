import math
import pygame
from engine.bitmapfont import text_surface
from engine.items import ITEMS, RECIPES, RECIPE_ORDER, DOG_HEALTH, USE_DURATION
from engine.menu import Screen, TITLE_BUTTONS, ABOUT_TEXT


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
        self._fonts(800)

    def _fonts(self, height):
        if self._font_height == height:
            return
        self._font_height = height
        scale = max(.72, min(1.15, height/900))
        self.font = BitmapFont(scale)
        self.title_font = BitmapFont(scale*1.2)
        self.logo_font = BitmapFont(scale*1.8)
        self.small_font = BitmapFont(scale*.75)
        self.slot_font = BitmapFont(max(.46, scale*.58))
        self._text_cache.clear()

    def text(self, surface, text, x, y, colour=(231, 239, 225), font=None, center=False):
        font = font or self.font
        key = (text, colour, id(font))
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

    @staticmethod
    def crafting_layout(width, height):
        panel = pygame.Rect((width-min(880, width-32))//2, (height-min(570, height-32))//2,
                            min(880, width-32), min(570, height-32))
        list_width = max(165, int(panel.width*.30))
        rows = [pygame.Rect(panel.x+18, panel.y+87+i*83, list_width, 72) for i in range(len(RECIPE_ORDER))]
        button = pygame.Rect(panel.x+list_width+42, panel.bottom-115, panel.width-list_width-62, 51)
        return panel, rows, button

    def handle_crafting_click(self, level, position, width, height):
        _, rows, button = self.crafting_layout(width, height)
        for i, row in enumerate(rows):
            if row.collidepoint(position):
                level.selected_recipe = i
                return True
        if button.collidepoint(position):
            return level.craft()
        return False

    def crafting_menu(self, surface, level, width, height):
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((5, 15, 13, 210))
        surface.blit(shade, (0, 0))
        panel, rows, button = self.crafting_layout(width, height)
        self.panel(surface, panel)
        self.text(surface, 'CRAFTING TIME', panel.centerx, panel.y+20, (248, 221, 122), self.title_font, center=True)
        for i, (recipe_id, rect) in enumerate(zip(RECIPE_ORDER, rows)):
            self.panel(surface, rect, i == level.selected_recipe)
            self.wrapped(surface, RECIPES[recipe_id]['name'], rect.x+12, rect.y+15, rect.width-24)
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
        pygame.draw.rect(surface, (59, 105, 71) if ready else (56, 63, 58), button, border_radius=7)
        self.text(surface, 'CRAFT / ENTER' if ready else 'NOT READY', button.centerx, button.y+10,
                  font=self.font, center=True)
        self.text(surface, 'Up/Down: Select    Enter: craft    C or Esc to go back.', panel.centerx, panel.bottom-45,
                  font=self.small_font, center=True)

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

        progress = max(0.0, min(1.0, progress))
        progress = progress * progress * (3.0 - 2.0 * progress)

        surface = pygame.Surface((width, height))
        surface.fill((0, 0, 0))

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

        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        self.present(surface)
        return True

    def draw_menu(self, menu, width, height):
        from OpenGL import GL as gl
        self._fonts(height)

        if not self._intro_finished:
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
            self.text(surface, 'Version 0', width//2, int(height*.16)+self.logo_font.size('A')[1]+50,
                      font=self.font, center=True)
            for index, (label, button) in enumerate(zip(TITLE_BUTTONS, buttons)):
                self.panel(surface, button, index == menu.selected)
                self.text(surface, label, button.centerx, button.centery-self.font.size('A')[1]//2,
                          center=True)
            self.text(surface, 'Click or Up/Down + Enter. Ctrl+Q or Esc to quit.', width//2, height-42,
                      font=self.small_font, center=True)
        else:
            panel = pygame.Rect(24, int(height*.18), width-48, int(height*.52))
            self.panel(surface, panel)
            title, message = {
                Screen.PLAY: ('PLAY', "The main gameplay loop isn't done yet. Tutorial is ready to go."),
                Screen.ABOUT: ('ABOUT THIS GAME', ABOUT_TEXT),
                Screen.LOADING: ('HEADING INTO CS JUNGLE', 'Getting the forest ready. Hang tight.'),
            }[menu.screen]
            self.text(surface, title, width//2, panel.y+30, (248, 221, 122), self.title_font, center=True)
            self.wrapped(surface, menu.error or message, width//2, panel.y+95, panel.width-48, center=True)
            if menu.screen == Screen.LOADING and not menu.error:
                for index in range(12):
                    angle = index*math.tau/12+menu.elapsed*4
                    colour = tuple(int(value*(.3+.7*index/11)) for value in (248, 221, 122))
                    pygame.draw.circle(surface, colour,
                        (int(width/2+24*math.cos(angle)), int(panel.bottom-55+24*math.sin(angle))), 4)
            self.panel(surface, back, True)
            self.text(surface, 'Back to title', back.centerx, back.centery-self.font.size('A')[1]//2, center=True)
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

    def draw(self, level, width, height, fps, paused=False):
        self._fonts(height)
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        self.text(overlay, f'{fps:.0f} FPS', width-100, 16, font=self.small_font)
        for i, (label, value, maximum, colour) in enumerate([
                ('HP', level.camera.health, level.camera.max_health, (116, 201, 142)),
                ('ENERGY', level.camera.stamina, level.camera.max_stamina, (115, 173, 207))]):
            y = 20+i*45
            self.text(overlay, f'{label} {int(value)}/{int(maximum)}', 20, y, font=self.small_font)
            pygame.draw.rect(overlay, (24, 40, 32), (20, y+27, 210, 9), border_radius=3)
            pygame.draw.rect(overlay, colour, (20, y+27, int(210*max(0, min(1, value/maximum))), 9), border_radius=3)

        bar_width = min(width-32, 1000)
        cell_width = bar_width//10
        bar_left, bar_y = (width-cell_width*10)//2, height-86
        names = {'food': 'Food', 'water': 'Water', 'metal_scrap': 'Metal', 'plastic_scrap': 'Plastic',
                 'stick': 'Stick', 'rock': 'Rock', 'compass': 'Compass', 'spear': 'Spear'}
        for i in range(10):
            rect = pygame.Rect(bar_left+i*cell_width, bar_y, cell_width-4, 74)
            self.panel(overlay, rect, i == level.inventory.selected_slot)
            self.text(overlay, str(i+1) if i < 9 else '0', rect.x+7, rect.y+3, font=self.slot_font)
            slot = level.inventory.slots[i] if i < level.inventory.capacity else None
            if slot:
                item, qty = slot
                self.icon(overlay, item, rect.centerx, rect.y+34)
                self.text(overlay, names[item], rect.centerx, rect.y+53, font=self.slot_font, center=True)
                if qty > 1:
                    self.text(overlay, str(qty), rect.right-22, rect.y+3, font=self.slot_font)
            elif i == 9:
                self.text(overlay, 'Hand', rect.centerx, rect.y+53, font=self.slot_font, center=True)

        title, instruction = level.instruction
        panel_width = min(width-32, 1000)
        body_lines = self.lines(instruction, panel_width-40)
        line_height = self.font.size('A')[1]+4
        hint = level.interaction_prompt
        item = level.inventory.selected_item
        if item in ('food', 'water'):
            hint = 'Hold E to use. Snack break.'
        guidance = level.compass_guidance()
        if guidance:
            angle, distance, _ = guidance
            turn = 'ahead' if abs(angle) < .25 else 'right' if angle > 0 else 'left'
            hint = f'Beacon {distance:.0f}m / {turn}. Keep to the path.'
        panel_height = 22+self.title_font.size('A')[1]+len(body_lines)*line_height+(line_height+8 if hint else 0)+12
        panel_y = bar_y-panel_height-10
        self.panel(overlay, ((width-panel_width)//2, panel_y, panel_width, panel_height))
        self.text(overlay, f'{min(int(level.state)+1, 10)}/10  {title}', width//2, panel_y+12,
                  (248, 221, 122), self.title_font, center=True)
        y = panel_y+20+self.title_font.size('A')[1]
        for line in body_lines:
            self.text(overlay, line, width//2, y, center=True)
            y += line_height
        if hint:
            self.text(overlay, hint, width//2, y+4, (124, 218, 182), self.small_font, center=True)
        if level.use_progress:
            pygame.draw.rect(overlay, (124, 218, 182), ((width-panel_width)//2+12, panel_y+panel_height-8,
                                                      int((panel_width-24)*level.use_progress/USE_DURATION), 4))
        if level.notification_timer > 0 and level.notification and not level.crafting_open:
            self.wrapped(overlay, level.notification, width//2, 164, width-64,
                         (248, 221, 122), self.small_font, center=True)
        if level.dog and level.dog.state != 'idle':
            self.text(overlay, 'UNCHILL DOG', width-210, 66,
                      (255, 172, 110), self.small_font)
            pygame.draw.rect(overlay, (200, 113, 75), (width-210, 99, int(188*level.dog.health/DOG_HEALTH), 9))
        if level.active and not level.crafting_open:
            pygame.draw.line(overlay, (241, 236, 211), (width//2-5, height//2), (width//2+5, height//2))
            pygame.draw.line(overlay, (241, 236, 211), (width//2, height//2-5), (width//2, height//2+5))
        if level.crafting_open:
            self.crafting_menu(overlay, level, width, height)
        if paused or not level.active:
            shade = pygame.Surface((width, height), pygame.SRCALPHA)
            shade.fill((5, 15, 13, 220))
            overlay.blit(shade, (0, 0))
            title = 'PAUSED. TAKE A BREATHER.' if paused and level.active else level.instruction[0]
            subtitle = 'Click to hop back in. Esc: title. Ctrl+Q: quit.' if level.active else level.instruction[1]+' Esc: title.'
            self.text(overlay, title, width//2, height//2-65, (248, 221, 122), self.title_font, center=True)
            self.wrapped(overlay, subtitle, width//2, height//2, width-40, center=True)
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
