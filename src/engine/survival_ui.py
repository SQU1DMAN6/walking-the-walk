import pygame

from engine.items import ITEMS, RECIPES, RUN_RECIPE_ORDER, USE_DURATION
from engine.ui import TutorialHUD, BitmapFont


CONTROLS = ('WASD: move','Mouse: look','Shift: sprint','F: use / chop','1-9: slots','0: empty hand',
            'Hold E: use','Left click: attack','Right: power (60)','C: crafting','Arrows: recipe','Enter: craft','Compass: hold slot',
            'H / Esc: pause/back','G: drop stack','R: retry results','Ctrl+Q: quit')


class SurvivalHUD(TutorialHUD):
    def prompt_rect(self,level,width,height,bottom):
        prompt = level.world_prompt()
        if prompt is None:return None
        if prompt and prompt.target_id==level.beacon_id:
            w = min(440,width-48)
            lines = self.lines(prompt.text,w-24,self.small_font)
            h = 22+self.small_font.size('A')[1]*(len(lines)+1)
            rect = pygame.Rect((width-w)//2,height//2-h//2,w,h)
            return prompt,rect,(width//2,height//2+h//2+12)
        if level.use_progress or level.damage_feedback.hits:return None
        return super().prompt_rect(level,width,height,bottom)

    @staticmethod
    def hotbar_layout(width, height):
        pixels=max(29,round(32*.9*max(1.,min(1.25,height/900))))
        return [rect.move(0,-pixels-4) for rect in TutorialHUD.hotbar_layout(width,height)]

    @staticmethod
    def crafting_layout(width, height):
        panel = pygame.Rect((width-min(840, width-32))//2, (height-min(540, height-32))//2,
                            min(840, width-32), min(540, height-32))
        list_width = max(264, int(panel.width*.30))
        rows = [pygame.Rect(panel.x+18, panel.y+82+i*62, list_width, 53) for i in range(4)]
        button = pygame.Rect(panel.x+list_width+42, panel.bottom-96, panel.width-list_width-62, 50)
        return panel, rows, button

    @staticmethod
    def crafting_close_rect(width, height):
        panel, _, _ = SurvivalHUD.crafting_layout(width, height)
        return pygame.Rect(panel.right-238, panel.y+14, 220, 48)

    def crafting_menu(self, surface, level, width, height, show_reason=True):
        surface.fill((5, 15, 13, 230))
        panel, rows, button = self.crafting_layout(width, height)
        self.panel(surface, panel)
        self.text(surface, 'CRAFTING', panel.x+18, panel.y+20, (248, 221, 122), self.title_font, False)
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
        if self.small_font.size(reason)[0]>button.width:
            reason='Need materials' if reason.startswith('Need ') else 'Already owned' if reason.startswith('Already ') else reason
        success = level.effects.latest('crafted')
        success = success and success.detail == recipe
        if success:reason = 'Crafted. Close [C]'
        if show_reason:self.wrapped(surface,reason,button.x,y+14,button.width,font=self.small_font)
        label = 'Crafted!' if success else 'Craft [Enter]' if ready else 'Not ready'
        self.button(surface, button, label, enabled=ready)
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
        self.text(surface,f'{level.config.difficulty} / {level.config.length}',width//2,72+self.small_font.size('A')[1],font=self.slot_font,center=True)
        column = (panel.width-48)//2
        tips = ('WASD: move','Mouse: look','Shift: sprint',
                'F: use | C: craft','Hold E: use','Left click: attack')
        for i,line in enumerate(tips):
            self.wrapped(surface,line,panel.x+16+(i//3)*(column+16),150+(i%3)*64,
                         column,font=self.small_font)
        for rect, label in zip(rows, ('Resume [H / Enter]' if level.active else 'New run [R]',
                                      'Controls', 'Main menu', 'Exit game')):
            self.button(surface, rect, label)

    def controls_overlay(self,surface,width,height):
        self.controls_list(surface,CONTROLS,width,height,'[H] / [Esc]: back to pause')

    def selected_text(self, level):
        item = level.inventory.selected_item
        if item is None:
            return 'Empty hand' if level.inventory.selected_slot == 9 else 'Empty slot'
        count = level.inventory.slots[level.inventory.selected_slot][1]
        if item in ('spear', 'axe'):
            ready,hint=level.attack_status()
            if ready:hint='Left click free | RMB 60'
        elif item in ('food', 'water', 'bandage'):
            hint = level.use_status()[1]
            cells=self.hotbar_layout(*self._font_height)
            if cells[0].y!=cells[5].y:hint={'food':'Hold [E]: eat','water':'Hold [E]: drink','bandage':'Hold [E]: heal'}[item]
        elif item == 'compass':
            angle, distance, _ = level.compass_guidance()
            hint = f'Beacon {distance:.0f}m '+('ahead' if abs(angle) < .25 else 'right' if angle > 0 else 'left')
        else:
            hint = '[C] crafting'
        return f'{ITEMS[item][0]} | {hint}' if item in ('spear','axe') else f'{ITEMS[item][0]} x{count} | {hint}'

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
        vitals=self.vitals_panel(overlay,level)
        nearest = level.dog
        visible_threat = (nearest and nearest.visible and nearest.health>0 and nearest.state not in ('idle','patrol','concealed','dormant')
                          and nearest.distance_to(level.camera.x,level.camera.z)<(38 if nearest.kind=='boss' else 12)
                          and level.world.vision_clear((level.camera.x,level.camera.y,level.camera.z),
                                                       (nearest.x,nearest.y+.8,nearest.z)))
        if visible_threat:
            threat_width=max(220,self.small_font.size('Venom Runner')[0]+24)
            rect=pygame.Rect(width-threat_width-12,12,threat_width,16+2*(self.small_font.size('A')[1]+4))
            self.panel(overlay,rect)
            name={'spider':'Spider','dog':'Dog','viper':'Venom Runner','boss':'Demon Thing'}[nearest.kind]
            self.text(overlay,name,rect.x+10,20,font=self.small_font)
            self.text(overlay,f'{nearest.health}/{nearest.max_health} HP',rect.x+10,24+self.small_font.size('A')[1],font=self.small_font)
            if nearest.kind=='boss':
                label={'slam':'Red ring: get out','cleave':'Claw: break reach','recover':'Recovery: strike!'}.get(nearest.state,'Watch its windup')
                cue_y=28+2*self.small_font.size('A')[1]
                cue_height=len(self.lines(label,rect.width-20,self.slot_font))*(self.slot_font.size('A')[1]+4)
                rect.height=cue_y+cue_height-rect.y+8
                self.panel(overlay,rect)
                self.text(overlay,name,rect.x+10,20,font=self.small_font)
                self.text(overlay,f'{nearest.health}/{nearest.max_health} HP',rect.x+10,24+self.small_font.size('A')[1],font=self.small_font)
                self.wrapped(overlay,label,rect.x+10,cue_y,rect.width-20,font=self.slot_font)
        info_bottom=max(vitals.bottom,rect.bottom if visible_threat else vitals.bottom)
        cells = self.hotbar_layout(width, height)
        compact=cells[0].y!=cells[5].y
        names = {'food':'Food', 'water':'Water', 'metal_scrap':'Metal', 'plastic_scrap':'Plastic',
                 'stick':'Stick', 'rock':'Stone', 'compass':'Compass', 'spear':'Spear', 'axe':'Axe', 'leaves':'Leaves', 'bandage':'Bandage'}
        self.draw_hotbar(overlay,level,width,height,names)
        selected = self.selected_text(level)
        y = cells[0].top-16-len(self.lines(selected, width-56, self.small_font))*(self.small_font.size('A')[1]+4)
        self.panel(overlay, (16, y, width-32, cells[0].top-y-8))
        self.wrapped(overlay, selected, width//2, y+4, width-56, font=self.small_font, center=True)
        if level.use_progress:
            pygame.draw.rect(overlay, (124, 218, 182), (22, cells[0].top-13, int((width-44)*level.use_progress/USE_DURATION), 4))
        if level.beacon_commit>0:
            self.text(overlay,'Linking beacon... stay close',width//2,height//2+45,
                      (131,230,211),self.small_font,True)
        hint = 'Press [H] to pause or show controls'
        hint_font = self.small_font
        self.panel(overlay, (width-hint_font.size(hint)[0]-24, height-hint_font.size('A')[1]-8, hint_font.size(hint)[0]+16, hint_font.size('A')[1]+4))
        self.text(overlay, hint, width-16-hint_font.size(hint)[0], height-hint_font.size('A')[1]-6, font=hint_font)
        timer=f'{level.elapsed:.1f}s'
        if hint_font.size(hint)[0]+hint_font.size(timer)[0]+48<=width:
            self.text(overlay,timer,12,height-hint_font.size('A')[1]-6,font=hint_font)
        else:
            self.text(overlay,timer,12,vitals.bottom+4,font=hint_font)
            info_bottom=max(info_bottom,vitals.bottom+hint_font.size('A')[1]+8)
        if not visible_threat and not level.poison.active and level.notification_timer<=0:
            self.wrapped(overlay,level.objective_text,vitals.right+16,18,width-vitals.right-28,font=self.small_font)
        if level.poison.active:
            rect=pygame.Rect(12,info_bottom+8,min(640,width-24),self.small_font.size('A')[1]+18)
            self.panel(overlay,rect)
            pygame.draw.rect(overlay,(201,107,228),rect,2,border_radius=8)
            self.text(overlay,'POISONED | Drink water [E] to cure',22,rect.y+8,(231,176,247),self.small_font)
            info_bottom=rect.bottom
        if level.active and level.notification_timer>0 and not (compact and (level.poison.active or (visible_threat and nearest.kind=='boss'))):
            toast_width=min(760,width-32)
            lines=self.lines(level.notification,toast_width-20,self.small_font)
            toast_height=12+len(lines)*(self.small_font.size('A')[1]+4)
            toast=pygame.Rect((width-toast_width)//2,info_bottom+10,toast_width,toast_height)
            self.panel(overlay,toast)
            self.wrapped(overlay,level.notification,width//2,toast.y+6,toast_width-20,font=self.small_font,center=True)
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
        if level.active and not (paused or level.crafting_open or level.help_open):
            self.damage_indicator(overlay,level,width,height)
        if level.crafting_open:
            self.crafting_menu(overlay, level, width, height)
        self.effect_feedback(overlay, level, width, height)
        if paused or (not level.active and not level.transition_pending):
            self.overlay_menu(overlay, level, width, height, paused)
        if level.help_open:
            self.controls_overlay(overlay, width, height)
        self.present(overlay)
