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
    def __init__(self,scale):
        self.scale=max(.9,scale)
        self.pixels=round(32*self.scale)

    def render(self,text,antialias,colour):
        source=text_surface(text,colour=colour,spacing=1)
        return pygame.transform.smoothscale(source,(max(1,round(source.get_width()*self.scale)),
                                                     max(1,round(source.get_height()*self.scale))))

    def size(self,text):
        from engine.bitmapfont import _WIDTH,_HEIGHT
        return round((len(text)*(_WIDTH+1)+1)*self.scale),round((_HEIGHT+4)*self.scale)


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
        scale=max(1.,min(1.25,height/900))
        self.font=BitmapFont(scale)
        self.title_font=BitmapFont(scale*1.2)
        self.logo_font=BitmapFont(scale*1.55)
        self.small_font=BitmapFont(scale*.9)
        self.slot_font=BitmapFont(scale*.9)
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

    def vitals_panel(self,surface,level):
        font=self.small_font
        line=font.size('A')[1]
        bar_width=font.size('Stamina 200/200')[0]
        rect=pygame.Rect(12,12,bar_width+24,2*(line+10)+12)
        self.panel(surface,rect)
        for i,(label,value,maximum,colour) in enumerate((
                ('Health',level.camera.health,level.camera.max_health,(116,201,142)),
                ('Stamina',level.camera.stamina,level.camera.max_stamina,(115,173,207)))):
            y=20+i*(line+10)
            self.text(surface,f'{label} {int(value)}/{int(maximum)}',22,y,font=font)
            pygame.draw.rect(surface,(42,57,47),(22,y+line-5,bar_width,8))
            pygame.draw.rect(surface,colour,(22,y+line-5,round(bar_width*max(0,value)/maximum),8))
        if level.health_flash_timer:
            colour=(104,240,147) if level.health_feedback=='heal' else (255,116,101)
            pygame.draw.rect(surface,colour,rect,3,border_radius=9)
        self.vitals_rect = rect
        return rect

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
        lines = self.lines(label,rect.width-16,font)
        if len(lines)>1:
            font = self.small_font
            lines = self.lines(label,rect.width-16,font)
        step = font.size('A')[1]
        y = rect.centery-len(lines)*step//2
        for line in lines:
            self.text(surface,line,rect.centerx,y,(233,240,225) if enabled else (176,185,178),font,True)
            y += step

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
        return pygame.Rect(panel.right-238, panel.y+14, 220, 48)

    @staticmethod
    def crafting_layout(width, height):
        panel = pygame.Rect((width-min(840, width-32))//2, (height-min(540, height-32))//2,
                            min(840, width-32), min(540, height-32))
        list_width = max(264, int(panel.width*.30))
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
        self.text(surface, 'CRAFTING TIME', panel.x+18, panel.y+20, (248, 221, 122), self.title_font, center=False)
        close = self.crafting_close_rect(width, height)
        self.button(surface, close, 'Close [C]')
        for i, (recipe_id, rect) in enumerate(zip(RECIPE_ORDER, rows)):
            self.button(surface, rect, RECIPES[recipe_id]['name'], i == level.selected_recipe)
        recipe_id = RECIPE_ORDER[level.selected_recipe]
        recipe = RECIPES[recipe_id]
        ready, reason = level.recipe_status(recipe_id)
        x, y = button.x, panel.y+89
        for item, qty in recipe['materials'].items():
            count = level.inventory.count(item)
            y = self.wrapped(surface, f'{ITEMS[item][0]}: {count} / {qty}', x, y, button.width,
                             (143, 223, 166) if count >= qty else (255, 172, 110))
            y += 8
        if self.small_font.size(reason)[0]>button.width:
            reason='Need materials' if reason.startswith('Need ') else 'Already owned' if reason.startswith('Already ') else reason
        self.wrapped(surface, reason, x, y+12, button.width,
                     (143, 223, 166) if ready else (248, 221, 122), self.small_font)
        self.button(surface, button, 'Craft [Enter]' if ready else 'Not ready', enabled=ready)
        self.text(surface, '[Up/Down] pick | [C] back', panel.centerx, panel.bottom-45,
                  font=self.small_font, center=True)
        guidance = level.action_coach()
        if guidance:
            expected = 0 if level.state == Stage.COMPASS else 1
            if width<1000 and guidance.kind in ('recipe','craft','close'):
                target={'recipe':rows[expected],'craft':button,'close':close}[guidance.kind]
                pygame.draw.rect(surface,(255,229,123),target,3,border_radius=8)
                return
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
        self.text(surface, '[Esc]: return to title', panel.centerx, panel.y+88,
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
            title_y=20 if height<600 else int(height*.12)
            self.text(surface, 'Walking the Walk', width//2, title_y, (248, 221, 122), self.logo_font, center=True)
            if height<600:
                author_y=title_y+self.logo_font.size('A')[1]+12
                self.panel(surface,pygame.Rect(8,author_y-4,width-16,self.font.size('A')[1]+4))
                self.text(surface,'Written by Quan Thai',16,author_y,font=self.font)
                self.text(surface,'Version 1.7',width-16-self.font.size('Version 1.7')[0],author_y,font=self.font)
            else:
                self.text(surface,'Written by Quan Thai',width//2,title_y+self.logo_font.size('A')[1]+12,font=self.font,center=True)
                self.text(surface,'Version 1.7',width//2,title_y+self.logo_font.size('A')[1]+56,font=self.font,center=True)
            for index, (label, button) in enumerate(zip(TITLE_BUTTONS, buttons)):
                self.button(surface, button, label, index == menu.selected)
            hint = 'First time playing? Start with Tutorial so you don\'t regret life'
            available = width-buttons[1].right-26
            if available>=210:
                rect = pygame.Rect(buttons[1].right+10,buttons[1].y,min(360,available),buttons[1].height)
                self.coach(surface,hint,buttons[1].midright,rect)
            else:
                self.wrapped(surface,hint,width//2,buttons[2].bottom+8,width-48,
                             (248,221,122),self.small_font,center=True)
            self.text(surface, 'Click / arrows + Enter | Esc: quit', width//2, height-self.small_font.size('A')[1]-6,
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
            self.button(surface, start, 'Start run', menu.config_row == 3)
            self.button(surface, back, 'Back to title')
            self.text(surface, '[Up/Down] row | [Left/Right] choose', width//2,
                      height-self.small_font.size('A')[1]-4, font=self.small_font, center=True)
        else:
            panel=pygame.Rect(16,16,width-32,back.top-28)
            self.panel(surface, panel)
            title, message = {
                Screen.ABOUT: ('ABOUT THIS GAME', ABOUT_TEXT),
                Screen.LOADING: ('HEADING INTO CS JUNGLE', 'Getting the forest ready. Hang tight.'),
            }[menu.screen]
            self.text(surface, title, width//2, panel.y+16, (248, 221, 122), self.title_font, center=True)
            self.wrapped(surface, menu.error or message, width//2, panel.y+76, panel.width-48, font=self.small_font, center=True)
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
    def hotbar_layout(width,height):
        pixels=max(29,round(32*.9*max(1.,min(1.25,height/900))))
        columns=10 if (width-8)//10-2>=round(120*pixels/32)+4 else 5
        rows=10//columns
        cell=(width-8)//columns
        cell_height=pixels*2+(12 if rows==2 else 32)
        top=height-12-rows*cell_height-(rows-1)*8
        left=(width-cell*columns)//2
        return [pygame.Rect(left+(i%columns)*cell,top+(i//columns)*(cell_height+8),cell-2,cell_height)
                for i in range(10)]

    def slot_label(self,name,width):
        return name

    def damage_indicator(self,surface,level,width,height):
        radius = max(48,min(110,round(height*.13)))
        cx,cy = width//2,height//2
        for hit in level.damage_feedback.hits:
            relative = level.damage_feedback.relative(hit,level.camera.yaw)
            alpha = round(245*min(1,hit.remaining/.35))
            if relative is None:
                if hit.source=='Poison':
                    rect=pygame.Rect(cx-80,cy-radius-34,160,30)
                    self.panel(surface,rect)
                    self.text(surface,'POISON',cx,rect.y+2,(232,151,249),self.small_font,True)
                continue
            angles = [relative+math.radians(-16+i*2) for i in range(17)]
            points = [(cx+math.sin(a)*r,cy-math.cos(a)*r) for r,seq in
                      ((radius+9,angles),(radius-2,reversed(angles))) for a in seq]
            pygame.draw.polygon(surface,(255,81,67,alpha),points)
            tip=(cx+math.sin(relative)*(radius+19),cy-math.cos(relative)*(radius+19))
            sides=[(cx+math.sin(relative+d)*(radius+7),cy-math.cos(relative+d)*(radius+7)) for d in (-.12,.12)]
            pygame.draw.polygon(surface,(255,215,190,alpha),[tip,*sides])

    def selected_text(self, level):
        item = level.inventory.selected_item
        if item is None:
            return 'Empty hand' if level.inventory.selected_slot == 9 else 'Empty slot'
        name = ITEMS[item][0]
        qty = level.inventory.slots[level.inventory.selected_slot][1]
        if item in ('food', 'water'):
            _, hint = level.use_status()
        elif item == 'spear':
            ready,hint=level.attack_status()
            if ready:hint='Left click free | RMB 60'
        elif item == 'compass':
            guidance = level.compass_guidance()
            angle, distance, _ = guidance
            turn = 'ahead' if abs(angle) < .25 else 'right' if angle > 0 else 'left'
            hint = f'Beacon {distance:.0f}m {turn}'
        else:
            hint = '[C]: crafting material'
        return f'{name} | {hint}' if item=='spear' else f'{name} x{qty} | {hint}'

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
        if rect.top<12 or rect.bottom>self.hotbar_layout(*surface.get_size())[0].top-8:return None
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

    @staticmethod
    def compact_attack_hint(prompt):
        if 'back away' in prompt.title.lower():return 'Back away!'
        text=prompt.text
        if text.startswith('Press ['):return 'Equip spear '+text.split(' ')[1]
        if text.startswith('Attack ready'):return text.replace('Attack ready','Ready')
        return {'Left click to attack':'Click to attack','Move closer to the dog':'Move closer',
                'Face the dog to attack':'Face the dog','A tree blocks the attack':'Tree in the way'}.get(text,text)

    def prompt_rect(self, level, width, height, bottom):
        prompt = level.world_prompt()
        if prompt is None:
            return None
        point = project(level.camera, prompt.position, width, height)
        if point is None:
            return None
        cells=self.hotbar_layout(width,height)
        if not getattr(level,'is_survival',False) and level.state==Stage.COMBAT and cells[0].y!=cells[5].y:
            rect=pygame.Rect(width-332,76,320,self.small_font.size('A')[1]+16)
            return prompt,rect,point
        text_width = max(self.small_font.size(prompt.title)[0], self.small_font.size(prompt.text)[0])+28
        w = min(width//2-40, 360, text_width)
        lines = self.lines(prompt.text, w-24, self.small_font)
        h = 22+self.small_font.size('A')[1]*(len(lines)+1)
        x = max(16, min(width-w-16, point[0]-w/2))
        y = max(126, min(bottom-h-10, point[1]-h-8))
        return prompt, pygame.Rect(x, y, w, h), point

    def controls_list(self,surface,rows,width,height,footer):
        surface.fill((5,15,13,245))
        self.panel(surface,(16,16,width-32,height-32))
        self.text(surface,'CONTROLS',width//2,30,(248,221,122),self.title_font,True)
        count=math.ceil(len(rows)/2)
        step=max(self.small_font.size('A')[1]+6,(height-190)//count)
        column=(width-64)//2
        short={'Left click: attack':'Click: attack','Compass: hold slot':'Compass: equip',
               'H / Esc: pause/back':'H/Esc: pause','R: retry results':'R: retry (end)'}
        for i,line in enumerate(rows):
            if self.small_font.size(line)[0]>column-16:line=short.get(line,line)
            self.text(surface,line,32+(i//count)*column,88+(i%count)*step,font=self.small_font)
        self.text(surface,footer,width//2,height-self.small_font.size('A')[1]-18,font=self.small_font,center=True)

    def controls_overlay(self,surface,width,height):
        rows=('WASD: move','Mouse: look','Shift: sprint','F: interact','1-9: slots','0: empty hand',
              'Hold E: use','C: crafting','Arrows: recipe','Enter: craft','Left click: attack','Right: power (60)',
              'Compass: hold slot','H: controls','Esc: pause/back','R: retry results','Ctrl+Q: quit')
        self.controls_list(surface,rows,width,height,'[H] / [Esc]: return')

    def slot_contents(self,surface,rect,index,slot,names,empty_labels=False):
        font=self.slot_font
        wide=rect.width>=90
        self.text(surface,f'[{index+1 if index<9 else 0}]',rect.x+5 if wide else rect.centerx,
                  rect.y+2,font=font,center=not wide)
        if not slot:
            if empty_labels:self.text(surface,self.slot_label('Hand' if index==9 else 'Empty',rect.width-8),
                                      rect.centerx,rect.y+font.pixels+(4 if rect.height<font.pixels*2+24 else 30),font=font,center=True)
            return
        item,quantity=slot
        show_count=quantity>1 or ITEMS[item][1]=='Material'
        compact=rect.height<font.pixels*2+24
        if not compact and (wide or not show_count):self.icon(surface,item,rect.centerx,rect.y+font.pixels+14)
        if show_count:
            count=str(quantity)
            self.text(surface,count,rect.right-font.size(count)[0]-5 if wide else rect.centerx,
                      rect.y+2 if wide else rect.y+font.pixels,font=font,center=not wide)
        self.text(surface,self.slot_label(names[item],rect.width-8),rect.centerx,
                  rect.y+font.pixels+(4 if compact else 30),font=font,center=True)

    def lesson_progress(self, level):
        key = (level.inventory, level.state, level.instruction[1], level.in_beacon_ring)
        if key != self._lesson_key:
            self._lesson_key, self._lesson_since = key, level.elapsed
        return 0.0 if level.in_beacon_ring else ease((level.elapsed-self._lesson_since-1.5)/.45)

    def lesson_fonts(self,progress):
        cells=self.hotbar_layout(*self._font_height)
        compact=cells[0].y!=cells[5].y
        return BitmapFont(self.font.scale*(1-.10*progress)),BitmapFont(self.title_font.scale*(1-(.20 if compact else .10)*progress))

    def lesson_body(self,level,compact,progress):
        if not compact or progress==0 or level.in_beacon_ring:return level.instruction[1]
        return {Stage.MOVEMENT:'Follow the path with [WASD]',Stage.LOOK:'Look around with the mouse',
                Stage.SUPPLIES:'Collect both supplies with [F]',Stage.CONSUME:'Select food/water; hold [E]',
                Stage.COMPASS:'Craft a compass in [C]',Stage.MATERIALS:'[F]: 2 sticks, 1 rock',
                Stage.SPEAR:'Craft a spear in [C]',Stage.COMBAT:'Hold spear; click to attack',
                Stage.BEACON:'Compass: follow the needle'}.get(level.state,level.instruction[1])

    def lesson_rect(self,level,width,height):
        progress=self.lesson_progress(level)
        font,title_font=self.lesson_fonts(progress)
        panel_width=round(min(width-32,900)*(1-.08*progress))
        cells=self.hotbar_layout(width,height)
        compact=cells[0].y!=cells[5].y
        if compact and not level.in_beacon_ring:
            first_font,first_title=self.lesson_fonts(0)
            full=self.lines(level.instruction[1],min(width-32,900)-32,first_font)
            initial_height=48+first_title.size('A')[1]+len(full)*(first_font.size('A')[1]+4)
            last_font,last_title=self.lesson_fonts(1)
            reminder=self.lines(self.lesson_body(level,True,1),round(min(width-32,900)*.92)-32,last_font)
            final_height=12+last_title.size('A')[1]+len(reminder)*(last_font.size('A')[1]+4)
            panel_height=round(initial_height+(final_height-initial_height)*progress)
            centre_top=height//2-initial_height//2
            lower_top=cells[0].top-36-final_height
        else:
            body=self.lines(level.instruction[1],panel_width-32,font)
            panel_height=24+title_font.size('A')[1]+len(body)*(font.size('A')[1]+4)
            centre_top=height//2-panel_height//2
            lower_top=cells[0].top-56-panel_height
        top=round(centre_top+(lower_top-centre_top)*progress)
        return pygame.Rect((width-panel_width)//2,top,panel_width,panel_height)

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
        title,instruction=level.instruction
        cells=self.hotbar_layout(*surface.get_size())
        compact=cells[0].y!=cells[5].y
        instruction=self.lesson_body(level,compact,progress)
        heading = 'BEACON REACHED' if level.in_beacon_ring else f'{min(int(level.state)+1, 10)}/10  {title}'
        heading = getattr(level, 'lesson_heading', heading)
        self.text(surface, heading, rect.centerx, rect.y+8, (255, 218, 169), title_font, center=True)
        self.wrapped(surface, instruction, rect.centerx, rect.y+16+title_font.size('A')[1], rect.width-32,
                     (247, 241, 229), font, center=True)

    def draw(self, level, width, height, fps, paused=False):
        self._fonts(height, width)
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        self.vitals_panel(overlay,level)
        layout=self.hotbar_layout(width,height)
        compact_combat=layout[0].y!=layout[5].y and level.state==Stage.COMBAT
        controls_width = max(140, self.small_font.size('[H] Controls')[0]+20)
        controls_height = self.small_font.size('A')[1]+self.slot_font.size('A')[1]+16
        self.panel(overlay, (width-controls_width-12, 12, controls_width, controls_height))
        self.text(overlay, '[H] Controls', width-self.small_font.size('[H] Controls')[0]-16, 16, font=self.small_font)
        if not compact_combat:
            self.text(overlay,f'{fps:.0f} FPS',width-self.slot_font.size(f'{fps:.0f} FPS')[0]-16,20+self.small_font.size('A')[1],font=self.slot_font)
        if level.dog and level.dog.state!='idle' and not compact_combat:
            rect = pygame.Rect(width-200, max(71, controls_height+20), 188, 65)
            self.panel(overlay, rect)
            self.text(overlay, 'Back away!' if level.dog.state == 'windup' else 'Hostile dog', rect.x+10, rect.y+8,
                      (255, 172, 110), self.small_font)
            pygame.draw.rect(overlay, (70, 44, 35), (rect.x+10, rect.y+43, 168, 8))
            pygame.draw.rect(overlay, (224, 119, 85), (rect.x+10, rect.y+43, int(168*level.dog.health/DOG_HEALTH), 8))

        names = {'food': 'Food', 'water': 'Water', 'metal_scrap': 'Metal', 'plastic_scrap': 'Plastic',
                 'stick': 'Stick', 'rock': 'Rock', 'compass': 'Compass', 'spear': 'Spear',
                 'axe': 'Axe', 'leaves': 'Leaves', 'bandage': 'Bandage'}
        cells = self.hotbar_layout(width, height)
        compact=cells[0].y!=cells[5].y
        for i,rect in enumerate(cells):
            self.panel(overlay,rect,i==level.inventory.selected_slot)
            slot=level.inventory.slots[i] if i<level.inventory.capacity else None
            self.slot_contents(overlay,rect,i,slot,names,True)

        panel_width = min(width-32, 1160)
        coaching = level.action_coach() if not paused else None
        slot_coaching = coaching is not None and coaching.kind in ('slot', 'use')
        selected = self.selected_text(level).split(' | ')[0] if slot_coaching else self.selected_text(level)
        selection_lines = self.lines(selected, panel_width-24, self.small_font)
        selection_height = len(selection_lines)*(self.small_font.size('A')[1]+2)+12
        selection_y = cells[0].top-selection_height-8
        if not compact:self.panel(overlay, ((width-panel_width)//2, selection_y, panel_width, selection_height))
        selection_center = int(width*.75 if coaching.slot < 5 else width*.25) if slot_coaching else width//2
        if not compact:self.wrapped(overlay, selected, selection_center, selection_y+6, panel_width//2-24 if slot_coaching else panel_width-24,
                                     (146,227,182),self.small_font,center=True)
        lesson = self.lesson_rect(level, width, height)
        lesson_visible = level.active and not (paused or level.help_open or level.crafting_open)
        if slot_coaching:
            cell = cells[coaching.slot]
            pygame.draw.rect(overlay, (255, 229, 123), cell, 3, border_radius=9)
            text_width = min(panel_width//2-12, self.small_font.size(coaching.text)[0]+20)
            x = max(16, min(width-text_width-16, cell.centerx-text_width//2))
            rect = pygame.Rect(x, selection_y, text_width, selection_height)
            if not compact:self.coach(overlay, coaching.text, (cell.centerx, cell.top-2), rect)
        if level.use_progress and compact:
            cell=cells[level.inventory.selected_slot]
            pygame.draw.rect(overlay,(124,218,182),(cell.x+4,cell.bottom-5,int((cell.width-8)*level.use_progress/USE_DURATION),4))
        if level.use_progress and not compact:
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
            if compact_combat:
                self.text(overlay,self.compact_attack_hint(prompt),rect.centerx,rect.y+4,
                          (217,241,221) if prompt.ready else (255,185,130),self.small_font,True)
                pygame.draw.rect(overlay,(224,119,85),(rect.x+10,rect.bottom-6,round((rect.width-20)*level.dog.health/DOG_HEALTH),4))
            else:
                self.text(overlay,prompt.title,rect.centerx,rect.y+6,(248,221,122),self.small_font,True)
                self.wrapped(overlay,prompt.text,rect.centerx,rect.y+10+self.small_font.size('A')[1],rect.width-24,
                             (217,241,221) if prompt.ready else (255,185,130),self.small_font,center=True)
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

    def effect_feedback(self, surface, level, width, height):
        effect = level.effects.latest('consumed')
        if effect and level.state != Stage.DEAD:
            from engine.effects import COLOURS
            colour = (*COLOURS[effect.detail], round(180*effect.opacity))
            pygame.draw.rect(surface, colour, (4, 4, width-8, height-8), 4, border_radius=12)
            pygame.draw.rect(surface, colour, self.vitals_rect.inflate(4, 4), 3, border_radius=8)
        effect = level.effects.latest('crafted')
        if effect:
            if level.crafting_open and getattr(level, 'recipes', RECIPE_ORDER)[level.selected_recipe] == effect.detail:
                _, _, button = self.crafting_layout(width, height)
                pygame.draw.rect(surface, (143, 239, 176, round(240*effect.opacity)), button, 3, border_radius=8)
            number = level.inventory.number_for(effect.detail)
            if number and not level.crafting_open:
                rect = self.hotbar_layout(width, height)[number-1]
                pygame.draw.rect(surface, (143, 239, 176, round(240*effect.opacity)), rect, 3, border_radius=8)
        death = level.effects.latest('player_died')
        if death:
            tint = pygame.Surface((width, height), pygame.SRCALPHA)
            tint.fill((45, 5, 8, round(155*death.progress)))
            surface.blit(tint, (0, 0))
            self.text(surface, 'YOU FELL', width//2, height//2, (255, 199, 183), self.title_font, True)
        elif level.effects.latest('beacon_activated'):
            self.text(surface, 'BEACON LINKED', width//2, height//2-50, (119, 255, 226), self.title_font, True)

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
