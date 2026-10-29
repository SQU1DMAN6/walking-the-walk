import pygame

from engine.animation import ease
from engine.survival_ui import SurvivalHUD
from engine.ui import TutorialHUD
from engine.tutorial import Lesson
from engine.items import USE_DURATION
from engine.prompts import hovering_rect


class ExpandedTutorialHUD(SurvivalHUD):
    overlay_layout = staticmethod(TutorialHUD.overlay_layout)
    handle_overlay_click = TutorialHUD.handle_overlay_click
    hotbar_layout = staticmethod(TutorialHUD.hotbar_layout)

    def draw(self, level, width, height, fps, paused=False):
        self._fonts(height, width)
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        vitals = self.vitals_panel(overlay, level)
        text_width = self.small_font.size('[H] Controls')[0]
        controls = pygame.Rect(width-text_width-28, 12, text_width+16, self.small_font.size('A')[1]+16)
        self.panel(overlay, controls)
        self.text(overlay, '[H] Controls', controls.x+8, controls.y+8, font=self.small_font)
        cells = self.hotbar_layout(width, height)
        names = {'food':'Food','water':'Water','metal_scrap':'Metal','plastic_scrap':'Plastic',
                 'compass':'Compass','spear':'Spear','stick':'Stick','rock':'Rock','axe':'Axe','leaves':'Leaves','bandage':'Bandage'}
        for i, rect in enumerate(cells):
            self.panel(overlay, rect, i == level.inventory.selected_slot)
            self.slot_contents(overlay, rect, i, level.inventory.slots[i] if i < 9 else None, names, True)
        coach = level.action_coach()
        if coach and coach.slot is not None:
            pygame.draw.rect(overlay, (255, 229, 123), cells[coach.slot], 3, border_radius=8)
        if level.use_progress and level.inventory.selected_slot < 9:
            rect = cells[level.inventory.selected_slot]
            pygame.draw.rect(overlay, (124, 218, 182), (rect.x+4, rect.bottom-6,
                             round((rect.width-8)*level.use_progress/USE_DURATION), 4))
        playing = level.active and not (paused or level.crafting_open or level.help_open)
        if playing:
            lesson = self.lesson_rect(level, width, height)
            prompt = level.world_prompt()
            prompt_drawn=False
            if prompt and not level.in_beacon_ring:
                label=prompt.text
                target=level.entities.get(prompt.target_id)
                title=prompt.title if target and target.kind in ('tree','dog') else None
                w=min(width-32,max(self.small_font.size(title or '')[0],self.small_font.size(label)[0])+24)
                lines=self.lines(label,w-24,self.small_font)
                line_height=self.small_font.size('A')[1]+3
                h=14+(len(lines)+bool(title))*line_height
                placement=hovering_rect(level.camera,prompt.position,(w,h),(width,height),cells[0].top)
                if placement:
                    rect,point=placement
                    if not any(rect.colliderect(block) for block in (lesson,vitals,controls)):
                        self.panel(overlay,rect)
                        if title:self.text(overlay,title,rect.centerx,rect.y+5,(248,221,122),self.small_font,True)
                        self.wrapped(overlay,label,rect.centerx,rect.y+7+bool(title)*line_height,w-24,font=self.small_font,center=True)
                        pygame.draw.line(overlay,(224,215,165),rect.midbottom,point,1)
                        prompt_drawn=True
            guidance = level.objective_direction()
            if guidance and not level.in_beacon_ring and not (prompt_drawn and guidance.target_id==prompt.target_id):
                self.direction_panel(overlay,guidance,lesson)
            dog = level.dog
            if dog:
                rect = pygame.Rect(width-192,controls.bottom+10,180,54)
                self.panel(overlay,rect)
                self.text(overlay,f'Dog {dog.health} HP',rect.centerx,rect.y+5,(255,185,130),self.small_font,True)
                pygame.draw.rect(overlay,(224,119,85),(rect.x+10,rect.bottom-9,round(160*dog.health/dog.max_health),5))
            self.lesson_panel(overlay, level, lesson)
            if not lesson.collidepoint(width//2, height//2):
                pygame.draw.line(overlay, (241, 236, 211), (width//2-5, height//2), (width//2+5, height//2))
                pygame.draw.line(overlay, (241, 236, 211), (width//2, height//2-5), (width//2, height//2+5))
            self.damage_indicator(overlay, level, width, height)
        gap = controls.left-vitals.right-24
        if level.active and gap >= 320 and level.notification_timer > 0 and not level.crafting_open:
            lines = self.lines(level.notification, gap-20, self.small_font)
            rect = pygame.Rect(vitals.right+12, 12, gap, 12+len(lines)*(self.small_font.size('A')[1]+4))
            self.panel(overlay, rect)
            self.wrapped(overlay, level.notification, rect.centerx, rect.y+6, rect.width-20,
                         (248, 221, 122), self.small_font, True)
        if level.crafting_open:self.crafting_menu(overlay, level, width, height)
        self.effect_feedback(overlay, level, width, height)
        if paused or (not level.active and not level.transition_pending):
            self.overlay_menu(overlay, level, width, height, paused)
        if level.help_open:self.controls_overlay(overlay, width, height)
        self.present(overlay)

    def lesson_progress(self, level):
        key = level.inventory, level.lesson
        if key != self._lesson_key:
            self._lesson_key, self._lesson_since = key, level.elapsed
        return 0. if level.in_beacon_ring else ease((level.elapsed-self._lesson_since-1.5)/.45)

    def lesson_body(self, level, compact, progress):
        if level.in_beacon_ring:return 'Press [F] to finish the tutorial.'
        if not compact:return level.instruction[1]
        if level.lesson == Lesson.TREE and level.tree_falls.live:return 'Tree falling away. Leaves soon.'
        if level.lesson in (Lesson.TREE,Lesson.USE,Lesson.BANDAGE):return level.instruction[1]
        return {
            Lesson.MOVEMENT:'Use [WASD] to follow the path.',
            Lesson.LOOK:'Move the mouse to look around.',
            Lesson.SUPPLIES:'Press [F] to collect supplies.',
            Lesson.CONSUME:'Select food or water. Hold [E].',
            Lesson.COMPASS:'Open [C] and craft a compass.',
            Lesson.MATERIALS:'Press [F] to collect materials.',
            Lesson.SPEAR:'Open [C] and craft a spear.',
            Lesson.COMBAT:'Equip your spear. Click to attack.',
            Lesson.AXE_MATERIALS:'Press [F] to collect materials.',
            Lesson.AXE:'Open [C] and craft an axe.',
            Lesson.INJURY:'Health set to 85 for practice.',
            Lesson.BEACON:'Hold the compass. Follow its needle.',
        }.get(level.lesson,level.instruction[1])

    def lesson_rect(self, level, width, height):
        progress = self.lesson_progress(level)
        font, title = self.lesson_fonts(progress)
        w = round(min(width-32, 900)*(1-.08*progress))
        cells = self.hotbar_layout(width, height)
        compact = cells[0].y != cells[5].y
        body = self.lesson_body(level, compact, progress)
        h = 24+title.size('A')[1]+len(self.lines(body, w-32, font))*(font.size('A')[1]+4)
        if height < 600:
            initial_font, initial_title = self.lesson_fonts(0)
            initial_body = self.lesson_body(level, compact, 0)
            initial_height = 24+initial_title.size('A')[1]+len(self.lines(initial_body, min(width-32, 900)-32, initial_font))*(initial_font.size('A')[1]+4)
            final_font, _ = self.lesson_fonts(1)
            final_body=self.lesson_body(level,compact,1)
            final_height=len(self.lines(final_body,round(min(width-32,900)*.92)-24,final_font))*(final_font.size('A')[1]+4)+12
            h = round(initial_height+(final_height-initial_height)*progress)
            central = height//2-initial_height//2
            settled = cells[0].top-final_height-12
        else:
            central = height//2-h//2
            settled = cells[0].top-h-12
        return pygame.Rect((width-w)//2, round(central+(settled-central)*progress), w, h)

    def lesson_panel(self, surface, level, rect):
        progress = self.lesson_progress(level)
        if surface.get_height() >= 600 or progress == 0:
            return super().lesson_panel(surface, level, rect)
        font, _ = self.lesson_fonts(progress)
        background, border = self.lesson_colours(level.elapsed)
        background = tuple(round(a+(b-a)*progress) for a, b in zip(background, (42, 36, 15, 236)))
        border = tuple(round(a+(b-a)*progress) for a, b in zip(border, (248, 221, 122, 255)))
        pygame.draw.rect(surface, background, rect, border_radius=9)
        pygame.draw.rect(surface, border, rect, 3, border_radius=9)
        body = self.lesson_body(level, True, progress)
        line_count=len(self.lines(body,rect.width-24,font))
        self.wrapped(surface, body, rect.centerx, rect.centery-line_count*(font.size('A')[1]+4)//2, rect.width-24,
                     (247, 241, 229), font, True)

    def crafting_menu(self, surface, level, width, height):
        super().crafting_menu(surface, level, width, height)
        coach = level.action_coach()
        if coach is None:return
        _, rows, button = self.crafting_layout(width, height)
        if coach.kind == 'close':target = self.crafting_close_rect(width, height)
        elif coach.kind == 'recipe':
            target = rows[level.recipes.index(level.expected_recipe)]
        else:target = button
        pygame.draw.rect(surface, (255, 229, 123), target, 3, border_radius=8)

    def overlay_menu(self, surface, level, width, height, paused):
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((5, 15, 13, 218));surface.blit(shade, (0, 0))
        panel, rows = self.overlay_layout(width, height)
        self.panel(surface, panel)
        title = 'PAUSED' if paused and level.active else level.instruction[0]
        self.text(surface, title, panel.centerx, panel.y+24, (248, 221, 122), self.title_font, True)
        self.text(surface, f'Time {level.elapsed:.1f}s | [Esc]: title', panel.centerx, panel.y+88,
                  font=self.small_font, center=True)
        for rect, label in zip(rows, ('Resume [Enter]' if paused and level.active else 'Restart [R]',
                                      'Title screen [Esc]', 'Quit')):
            self.button(surface, rect, label)

    def controls_overlay(self, surface, width, height):
        rows = ('WASD: move', 'Mouse: look', 'Shift: sprint', 'F: collect/chop',
                '1-9: slots', '0: empty hand', 'Hold E: use', 'C: crafting',
                'Arrows: recipe', 'Enter: craft', 'Click: attack', 'Right: power (60)',
                'H: controls', 'Esc: pause/back', 'R: replay (end)', 'Ctrl+Q: quit')
        rows = (*rows[:12], 'Compass: equip', *rows[12:])
        self.controls_list(surface, rows, width, height, '[H] / [Esc]: return')



WorkshopHUD = ExpandedTutorialHUD
