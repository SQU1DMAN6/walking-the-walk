"""UI drawing functions for Walking the Walk."""
import pygame


def surface_to_texture(surface, tex_id):
    """Convert pygame surface to OpenGL texture."""
    import OpenGL.GL as gl
    data = pygame.image.tostring(
        pygame.transform.flip(surface, False, True), "RGBA", False)
    if tex_id is None:
        tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                    surface.get_width(), surface.get_height(), 0,
                    gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex_id


def draw_quad(gl, x, y, w, h, col, a=0.85):
    """Draw a colored quad."""
    gl.glColor4f(col[0] / 255.0, col[1] / 255.0, col[2] / 255.0, a)
    gl.glBegin(gl.GL_QUADS)
    gl.glVertex2f(x, y)
    gl.glVertex2f(x + w, y)
    gl.glVertex2f(x + w, y + h)
    gl.glVertex2f(x, y + h)
    gl.glEnd()


def draw_text_line(gl, surface, texid, x, y):
    """Draw a text surface as a textured quad."""
    import OpenGL.GL as gl
    gl.glEnable(gl.GL_TEXTURE_2D)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texid)
    gl.glColor4f(1.0, 1.0, 1.0, 1.0)
    w = surface.get_width()
    h = surface.get_height()
    gl.glBegin(gl.GL_QUADS)
    gl.glTexCoord2f(0, 1); gl.glVertex2f(x, y)
    gl.glTexCoord2f(1, 1); gl.glVertex2f(x + w, y)
    gl.glTexCoord2f(1, 0); gl.glVertex2f(x + w, y + h)
    gl.glTexCoord2f(0, 0); gl.glVertex2f(x, y + h)
    gl.glEnd()
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    gl.glDisable(gl.GL_TEXTURE_2D)


def begin_2d(gl, width, height):
    """Begin 2D drawing mode."""
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glPushMatrix()
    gl.glLoadIdentity()
    gl.glOrtho(0, width, height, 0, -1, 1)
    gl.glMatrixMode(gl.GL_MODELVIEW)
    gl.glPushMatrix()
    gl.glLoadIdentity()
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)


def end_2d(gl):
    """End 2D drawing mode."""
    gl.glPopMatrix()
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glPopMatrix()
    gl.glMatrixMode(gl.GL_MODELVIEW)
    gl.glEnable(gl.GL_DEPTH_TEST)


def draw_hud(gl, level, width, height, font_func, fps):
    """Draw the HUD with health/stamina bars."""
    begin_2d(gl, width, height)
    
    BW, BH = 260.0, 20.0
    BX, BY = 30.0, 28.0
    
    hf = max(0.0, min(1.0, level.player_health / 100.0))
    sf = max(0.0, min(1.0, level.player_stamina / 100.0))
    hcol = (120, 200, 90) if hf > 0.5 else (230, 120, 60) if hf > 0.25 else (225, 45, 45)
    scol = (110, 170, 220)
    
    draw_quad(gl, BX - 3, BY - 3, BW + 6, BH + 6, (0, 0, 0), 0.6)
    draw_quad(gl, BX, BY, BW, BH, (40, 40, 40), 0.9)
    draw_quad(gl, BX, BY, BW * hf, BH, hcol)
    sy = BY + BH + 10
    draw_quad(gl, BX - 3, sy - 3, BW + 6, BH + 6, (0, 0, 0), 0.6)
    draw_quad(gl, BX, sy, BW, BH, (40, 40, 40), 0.9)
    draw_quad(gl, BX, sy, BW * sf, BH, scol)
    
    if hf < 0.3:
        draw_quad(gl, 0, 0, width, height, (0.85, 0.03, 0.03), 0.4)
    
    end_2d(gl)
    
    draw_tutorial_prompts(gl, level, width, height, font_func)
    draw_interaction_prompt(gl, level, width, height, font_func)


def draw_tutorial_prompts(gl, level, width, height, font_func):
    """Draw tutorial instruction prompts."""
    prompts = []
    
    if level.state == 0:
        prompts.append("W A S D  MOVE")
    elif level.state == 1:
        prompts.append("MOVE YOUR MOUSE TO LOOK")
    elif level.state == 2:
        prompts.append("F  INTERACT")
    elif level.state == 3:
        prompts.append("F  PICK UP SPEAR")
    elif level.state == 4:
        prompts.append("LEFT CLICK  ATTACK")
    elif level.state == 5:
        prompts.append("REACH THE CLEARING")
    
    if not prompts:
        return
    
    begin_2d(gl, width, height)
    y_offset = height - 120
    for prompt in prompts:
        font_surf = font_func(prompt, colour=(255, 255, 200), spacing=2)
        bx = (width - font_surf.get_width()) // 2 - 20
        bw = font_surf.get_width() + 40
        bh = font_surf.get_height() + 20
        draw_quad(gl, bx, y_offset, bw, bh, (0, 0, 0), 0.7)
        texid = surface_to_texture(font_surf, None)
        draw_text_line(gl, font_surf, texid, bx + 20, y_offset + 10)
        y_offset -= 50
    end_2d(gl)


def draw_interaction_prompt(gl, level, width, height, font_func):
    """Draw the interaction prompt."""
    if level.interaction_prompt is None:
        return
    
    font_surf = font_func(level.interaction_prompt, colour=(230, 220, 170), spacing=1)
    bx = (width - font_surf.get_width()) // 2 - 18
    by = height - 110
    bw = font_surf.get_width() + 36
    bh = font_surf.get_height() + 16
    
    begin_2d(gl, width, height)
    draw_quad(gl, bx, by, bw, bh, (0, 0, 0), 0.55)
    texid = surface_to_texture(font_surf, None)
    draw_text_line(gl, font_surf, texid, bx + 18, by + 8)
    end_2d(gl)


def draw_notification(gl, level, width, height, font_func):
    """Draw notification message."""
    if level.notification is None or level.notification_timer <= 0:
        return
    
    font_surf = font_func(level.notification, colour=(240, 240, 180), spacing=2)
    bx = (width - font_surf.get_width()) // 2 - 20
    by = 60
    bw = font_surf.get_width() + 40
    bh = font_surf.get_height() + 20
    
    begin_2d(gl, width, height)
    draw_quad(gl, bx, by, bw, bh, (0, 0, 0), 0.6)
    texid = surface_to_texture(font_surf, None)
    draw_text_line(gl, font_surf, texid, bx + 20, by + 10)
    end_2d(gl)


def draw_death_screen(gl, level, width, height, font_func):
    """Draw death screen."""
    if level.state != 6:
        return
    
    begin_2d(gl, width, height)
    draw_quad(gl, 0, 0, width, height, (0, 0, 0), 0.8)
    
    title_surf = font_func("YOU DIED", colour=(255, 80, 80), spacing=3)
    tx = (width - title_surf.get_width()) // 2
    ty = height // 3
    texid = surface_to_texture(title_surf, None)
    draw_text_line(gl, title_surf, texid, tx, ty)
    
    restart_surf = font_func("Press R to restart", colour=(200, 200, 200), spacing=2)
    rx = (width - restart_surf.get_width()) // 2
    ry = height // 2
    restex = surface_to_texture(restart_surf, None)
    draw_text_line(gl, restart_surf, restex, rx, ry)
    end_2d(gl)


def draw_completion_screen(gl, level, width, height, font_func):
    """Draw level completion screen."""
    if not level.level_complete:
        return
    
    begin_2d(gl, width, height)
    draw_quad(gl, 0, 0, width, height, (0, 0, 0), 0.85)
    
    title_surf = font_func("LEVEL 1 COMPLETE", colour=(100, 255, 100), spacing=3)
    tx = (width - title_surf.get_width()) // 2
    ty = height // 4
    texid = surface_to_texture(title_surf, None)
    draw_text_line(gl, title_surf, texid, tx, ty)
    
    lines = [
        "You survived the first walk.",
        "",
        "Branch collected: %s" % ("YES" if level.branch_collected else "NO"),
        "Emu defeated: %s" % ("YES" if not level.emu_alive else "NO"),
    ]
    for i, line in enumerate(lines):
        line_surf = font_func(line, colour=(200, 200, 180), spacing=2)
        lx = (width - line_surf.get_width()) // 2
        ly = height // 2 + i * 30
        linetex = surface_to_texture(line_surf, None)
        draw_text_line(gl, line_surf, linetex, lx, ly)
    
    end_2d(gl)