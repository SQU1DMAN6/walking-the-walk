import pygame

from engine.items import ITEMS, RECIPES, RUN_RECIPE_ORDER, USE_DURATION
from engine.ui import TutorialHUD, BitmapFont


CONTROLS = ('W/A/S/D: move', 'Mouse: look', 'Shift: sprint', 'F: collect / read / chop with axe',
            '1-9: select inventory slot', '0: empty hand', 'Hold E: food / water / bandage',
            'Left click: swing held weapon', 'C: open / close crafting', 'Up/Down + Enter: choose / craft',
            'Compass: hold its numbered slot', 'H / Esc: pause or return', 'G: drop selected stack')


class SurvivalHUD(TutorialHUD):
    @staticmethod
    def hotbar_layout(width, height):
        return [rect.move(0, -24) for rect in TutorialHUD.hotbar_layout(width, height)]

    @staticmethod
    def crafting_layout(width, height):
        panel = pygame.Rect((width-min(880, width-32))//2, (height-min(570, height-32))//2,
                            min(880, width-32), min(570, height-32))
        list_width = max(165, int(panel.width*.30))
        rows = [pygame.Rect(panel.x+18, panel.y+82+i*62, list_width, 53) for i in range(4)]
        button = pygame.Rect(panel.x+list_width+42, panel.bottom-96, panel.width-list_width-62, 50)
        return panel, rows, button

    @staticmethod
    def crafting_close_rect(width, height):
        panel, _, _ = SurvivalHUD.crafting_layout(width, height)
        return pygame.Rect(panel.right-134, panel.y+14, 116, 44)

    def crafting_menu(self, surface, level, width, height):
        surface.fill((5, 15, 13, 230))
        panel, rows, button = self.crafting_layout(width, height)
        self.panel(surface, panel)
        self.text(surface, 'CRAFTING', panel.centerx, panel.y+20, (248, 221, 122), self.title_font, True)
        self.button(surface, self.crafting_close_rect(width, height), 'Close [C]')
        for i, (recipe, rect) in enumerate(zip(RUN_RECIPE_ORDER, rows)):
            self.button(surface, rect, ITEMS[recipe][0], i == level.selected_recipe)
        recipe = RUN_RECIPE_ORDER[level.selected_recipe]
        ready, reason = level.recipe_status(recipe)
        y = panel.y+90
        for item, count in RECIPES[recipe]['materials'].items():
            y = self.wrapped(surface, f'{ITEMS[item][0]}: {level.inventory.count(item)} / {count}',
                             button.x, y, button.width, (143, 223, 166) if level.inventory.has(item, count) else (255, 174, 110))
            y += 10
        self.wrapped(surface, reason, button.x, y+14, button.width, font=self.small_font)
        self.button(surface, button, 'Craft [Enter]' if ready else 'Not ready', enabled=ready)
        self.text(surface, '[Up/Down] choose | [C]/[Esc] back', panel.centerx, panel.bottom-30,
                  font=self.small_font, center=True)

    @staticmethod
    def overlay_layout(width, height):
        panel = pygame.Rect(16, 16, width-32, height-32)
        button_width = (panel.width-48)//2
        rows = [pygame.Rect(panel.x+16+(i%2)*(button_width+16), panel.bottom-128+(i//2)*58,
                            button_width, 48) for i in range(4)]
        return panel, rows

    def handle_overlay_click(self, level, position, width, height, paused=False):
        _, rows = self.overlay_layout(width, height)
        for i, rect in enumerate(rows):
            if rect.collidepoint(position):
                self.press_button(rect)
                return (('resume' if level.active else 'restart'), 'controls', 'title', 'quit')[i]
        return None

    def overlay_menu(self, surface, level, width, height, paused):
        surface.fill((5, 15, 13, 240))
        panel, rows = self.overlay_layout(width, height)
        self.panel(surface, panel)
        heading = 'PAUSED' if level.active else 'RUN COMPLETE' if level.level_complete else 'GAME OVER'
        self.text(surface, heading, width//2, 32, (248, 221, 122), self.title_font, True)
        self.text(surface, f'Time {level.elapsed:.1f}s | Defeated {level.stats["defeated"]} | Trees {level.stats["trees"]}',
                  width//2, 68, font=self.small_font, center=True)
        column = (panel.width-48)//2
        per_column = (len(CONTROLS)+1)//2
        step = max(28, self.small_font.size('A')[1]+5)
        for i, line in enumerate(CONTROLS):
            self.wrapped(surface, line, panel.x+16+(i//per_column)*(column+16), 108+(i%per_column)*step,
                         column, font=self.small_font)
        for rect, label in zip(rows, ('Resume [H / Enter]' if level.active else 'New run [R]',
                                      'Controls', 'Return to main menu', 'Exit game')):
            self.button(surface, rect, label)

    def controls_overlay(self, surface, width, height):
        surface.fill((5, 15, 13, 245))
        self.panel(surface, (16, 16, width-32, height-32))
        self.text(surface, 'CONTROLS', width//2, 32, (248, 221, 122), self.title_font, True)
        for i, line in enumerate(CONTROLS):
            self.text(surface, line, 40, 82+i*min(self.small_font.size('A')[1]+8, (height-150)//len(CONTROLS)), font=self.small_font)
        self.text(surface, '[H] / [Esc]: back to pause menu', width//2, height-45, font=self.small_font, center=True)

    def selected_text(self, level):
        item = level.inventory.selected_item
        if item is None:
            return 'Empty hand' if level.inventory.selected_slot == 9 else 'Empty slot'
        count = level.inventory.slots[level.inventory.selected_slot][1]
        if item in ('spear', 'axe'):
            hint = level.attack_status()[1]
        elif item in ('food', 'water', 'bandage'):
            hint = level.use_status()[1]
        elif item == 'compass':
            angle, distance, _ = level.compass_guidance()
            hint = f'Beacon {distance:.0f}m '+('ahead' if abs(angle) < .25 else 'right' if angle > 0 else 'left')
        else:
            hint = '[C] crafting'
        return f'{ITEMS[item][0]} x{count} | {ITEMS[item][1]} | {hint}'

    @staticmethod
    def icon(surface, item, x, y):
        if item == 'axe':
            pygame.draw.line(surface, (170, 124, 67), (x-7, y+14), (x+7, y-14), 4)
            pygame.draw.polygon(surface, (190, 202, 195), [(x-9, y-15), (x+11, y-13), (x+6, y-2), (x-12, y-4)])
        elif item == 'leaves':
            pygame.draw.ellipse(surface, (117, 193, 92), (x-13, y-10, 26, 20))
            pygame.draw.line(surface, (215, 232, 159), (x-10, y+6), (x+10, y-7), 2)
        elif item == 'bandage':
            pygame.draw.rect(surface, (228, 222, 195), (x-13, y-9, 26, 18), border_radius=3)
            pygame.draw.rect(surface, (126, 158, 106), (x-4, y-9, 8, 18))
        else:
            TutorialHUD.icon(surface, item, x, y)

    def draw(self, level, width, height, fps, paused=False):
        self._fonts(height, width)
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        self.panel(overlay, (12, 12, 220, 104))
        for i, (name, value, maximum, colour) in enumerate((
                ('Health', level.camera.health, level.camera.max_health, (116, 201, 142)),
                ('Stamina', level.camera.stamina, level.camera.max_stamina, (115, 173, 207)))):
            y = 20+i*46
            text = f'{name} {int(value)}/{int(maximum)}'
            font = BitmapFont(self.small_font.scale*min(1, 198/self.small_font.size(text)[0]))
            self.text(overlay, text, 22, y, font=font)
            pygame.draw.rect(overlay, (42, 57, 47), (22, y+27, 198, 8))
            pygame.draw.rect(overlay, colour, (22, y+27, round(198*max(0, value)/maximum), 8))
        if level.health_flash_timer:
            pygame.draw.rect(overlay, (120, 239, 156) if level.health_feedback == 'heal' else (255, 116, 101),
                             (12, 12, 220, 104), 3, border_radius=9)
        nearest = level.dog
        if nearest and nearest.state != 'idle' and nearest.distance_to(level.camera.x, level.camera.z) < 12:
            rect = pygame.Rect(width-200, 12, 188, 75)
            self.panel(overlay, rect)
            self.text(overlay, 'Giant spider' if nearest.kind == 'spider' else 'Hostile dog', rect.x+10, 22, font=self.small_font)
            self.text(overlay, f'{nearest.health}/{nearest.max_health} health', rect.x+10, 48, font=self.small_font)
        cells = self.hotbar_layout(width, height)
        names = {'food':'Food', 'water':'Water', 'metal_scrap':'Metal', 'plastic_scrap':'Plastic',
                 'stick':'Stick', 'rock':'Stone', 'compass':'Compass', 'spear':'Spear', 'axe':'Axe', 'leaves':'Leaves', 'bandage':'Bandage'}
        for i, rect in enumerate(cells):
            self.panel(overlay, rect, level.inventory.selected_slot == i)
            self.text(overlay, f'[{i+1 if i < 9 else 0}]', rect.x+5, rect.y+2, font=self.slot_font)
            slot = level.inventory.slots[i] if i < 9 else None
            if slot:
                item, count = slot
                self.icon(overlay, item, rect.centerx, rect.y+34)
                self.text(overlay, names[item], rect.centerx, rect.y+52, font=self.slot_font, center=True)
                if count > 1 or ITEMS[item][1] == 'Material':
                    self.text(overlay, str(count), rect.right-20, rect.y+2, font=self.slot_font)
        selected = self.selected_text(level)
        y = cells[0].top-16-len(self.lines(selected, width-56, self.small_font))*(self.small_font.size('A')[1]+4)
        self.panel(overlay, (16, y, width-32, cells[0].top-y-8))
        self.wrapped(overlay, selected, width//2, y+4, width-56, font=self.small_font, center=True)
        if level.use_progress:
            pygame.draw.rect(overlay, (124, 218, 182), (22, cells[0].top-13, int((width-44)*level.use_progress/USE_DURATION), 4))
        hint = 'Press [H] to pause or show controls'
        hint_font = BitmapFont(self.small_font.scale*min(1, 18/self.small_font.size('A')[1]))
        self.panel(overlay, (width-hint_font.size(hint)[0]-24, height-31, hint_font.size(hint)[0]+16, 26))
        self.text(overlay, hint, width-16-hint_font.size(hint)[0], height-27, font=hint_font)
        self.text(overlay, f'{level.elapsed:.1f}s', 12, height-27, font=hint_font)
        if level.notification_timer > 0:
            toast_width = min(440, max(168, width-480))
            lines = self.lines(level.notification, toast_width-20, self.small_font)
            toast_height = 12+len(lines)*(self.small_font.size('A')[1]+4)
            self.panel(overlay, ((width-toast_width)//2, 12, toast_width, toast_height))
            self.wrapped(overlay, level.notification, width//2, 18, toast_width-20, font=self.small_font, center=True)
        if level.active and not paused and not level.crafting_open and not level.help_open:
            prompt_info = self.prompt_rect(level, width, height, y)
            if prompt_info:
                prompt, rect, point = prompt_info
                pygame.draw.line(overlay, (224, 215, 165), rect.midbottom, point, 1)
                self.panel(overlay, rect)
                self.text(overlay, prompt.title, rect.centerx, rect.y+6, (248, 221, 122), self.small_font, True)
                self.wrapped(overlay, prompt.text, rect.centerx, rect.y+10+self.small_font.size('A')[1], rect.width-24,
                             font=self.small_font, center=True)
            pygame.draw.line(overlay, (241, 236, 211), (width//2-5, height//2), (width//2+5, height//2))
            pygame.draw.line(overlay, (241, 236, 211), (width//2, height//2-5), (width//2, height//2+5))
        if level.crafting_open:
            self.crafting_menu(overlay, level, width, height)
        if paused or not level.active:
            self.overlay_menu(overlay, level, width, height, paused)
        if level.help_open:
            self.controls_overlay(overlay, width, height)
        self.present(overlay)
