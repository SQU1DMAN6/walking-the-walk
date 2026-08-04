"""Walking The Walk — First-person outback exploration."""
import math
import sys

import pygame

from engine.bitmapfont import text_surface
from engine.framebuffer import Framebuffer
from engine.renderer import Renderer
from engine.opengl_renderer import OpenGLRenderer
from engine.camera import Camera
from engine.worldgen import get_terrain_height
from engine.chunk import ChunkManager
from engine.emu import Emu

WIDTH = 1400
HEIGHT = 1050

pygame.init()
pygame.display.set_caption("Walking The Walk")

use_opengl = True
is_fullscreen = False

# Start in windowed mode with RESIZABLE flag
flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE if use_opengl else pygame.RESIZABLE
screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

pygame.event.set_grab(True)
pygame.mouse.set_visible(False)

clock = pygame.time.Clock()

camera = Camera()

# Procedural chunk streaming
WORLD_SEED = 42
CHUNK_SIZE = 40
RENDER_DISTANCE = 2

chunk_manager = ChunkManager(
    seed=WORLD_SEED,
    chunk_size=CHUNK_SIZE,
    render_distance=RENDER_DISTANCE,
    segments=12,
)

# Configure the camera: terrain following + collision (obstacles are
# refreshed from loaded chunks each frame)
camera.terrain_height_cb = lambda x, z: get_terrain_height(x, z, WORLD_SEED, 1.5)
camera.bounds = None  # unbounded world (chunks stream infinitely)

renderer = OpenGLRenderer(WIDTH, HEIGHT) if use_opengl else Renderer(WIDTH, HEIGHT)
framebuffer = Framebuffer(WIDTH, HEIGHT) if not use_opengl else None

# Wildlife: emus (spawn near the origin chunk)
emus = []
for i in range(5):
    import random as _random
    rng = _random.Random(WORLD_SEED + 5000 + i)
    ex = rng.uniform(-CHUNK_SIZE, CHUNK_SIZE)
    ez = rng.uniform(-CHUNK_SIZE, CHUNK_SIZE)
    ey = get_terrain_height(ex, ez, WORLD_SEED, 1.5)
    emus.append(Emu(ex, ey, ez, seed=WORLD_SEED + 1000 + i))

# Inventory & journal
inventory = []           # list of collected discovery names
journal_entries = []     # list of dicts (already collected)
show_journal = False
notification = None
notification_timer = 0.0

show_help = True

HELP_TEXT = (
    "=== Walking The Walk ===\n"
    "\n"
    "Controls:\n"
    "  W/A/S/D    - Move forward/left/backward/right\n"
    "  Shift      - Sprint\n"
    "  Mouse      - Look around\n"
    "  E          - Collect nearby discovery\n"
    "  J          - Toggle journal\n"
    "\n"
    "Display:\n"
    "  F11        - Toggle fullscreen\n"
    "  F1         - Toggle this help screen\n"
    "\n"
    "Info:\n"
    "  ESC        - Release mouse grab (or quit if already released)\n"
    "  Ctrl+Q     - Quit game\n"
    "\n"
    "Written by Quan Thai\n"
    "\nGoals:\n"
    "  Explore the Australian outback.\n"
    "  Hide from its wild animals.\n"
    "  Discover its secrets.\n"
    "  Walk up to a glowing marker and press E to collect it.\n"
    "  Press J to view your journal.\n\n"
    "Use H to close this Help message.\n"
)

# Pre-render help text surface
_HELP_SURFACE = text_surface(HELP_TEXT, colour=(200, 200, 200), spacing=2)
_HELP_SURFACE_W = _HELP_SURFACE.get_width()
_HELP_SURFACE_H = _HELP_SURFACE.get_height()

# Pre-render journal overlay (rebuilt when entries change)
journal_surface = None
journal_surface_dirty = True


def _build_journal_surface():
    """Rebuild the journal overlay surface from current entries."""
    total = len(chunk_manager.all_discoveries())
    base = "=== Field Journal ===\n"
    base += "Discovered: %d/%d\n\n" % (len(journal_entries), total)

    if journal_entries:
        for e in journal_entries:
            base += "* %s (%s)\n" % (e["name"], e["category"])
            base += "    %s\n\n" % e["description"]
    else:
        base += "You haven't discovered anything yet.\n"
        base += "Find the glowing markers and press E to collect them.\n"

    return text_surface(base, colour=(220, 220, 200), spacing=2)


# OpenGL texture IDs for help overlay (lazy init)
_help_tex_id = None
_journal_tex_id = None


def _surface_to_texture(surface, tex_id):
    import OpenGL.GL as gl
    data = pygame.image.tostring(surface, "RGBA", True)
    if tex_id is None:
        tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                    surface.get_width(), surface.get_height(), 0,
                    gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex_id


def _get_help_texture():
    global _help_tex_id
    if _help_tex_id is not None:
        return _help_tex_id
    _help_tex_id = _surface_to_texture(_HELP_SURFACE, None)
    return _help_tex_id


def toggle_fullscreen():
    """Toggle between fullscreen and windowed mode."""
    global screen, is_fullscreen, WIDTH, HEIGHT
    is_fullscreen = not is_fullscreen
    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)

    flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE if use_opengl else pygame.RESIZABLE
    if is_fullscreen:
        display_info = pygame.display.Info()
        WIDTH = display_info.current_w
        HEIGHT = display_info.current_h
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags | pygame.FULLSCREEN)
    else:
        WIDTH = 1400
        HEIGHT = 1050
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

    if use_opengl:
        import OpenGL.GL as gl
        gl.glViewport(0, 0, WIDTH, HEIGHT)
        renderer.width = WIDTH
        renderer.height = HEIGHT

    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)


def draw_text_overlay(surface, texture_id, tex_w, tex_h, overlay_alpha=0.7):
    """Draw a textured text overlay centered on screen (OpenGL path)."""
    import OpenGL.GL as gl
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glPushMatrix()
    gl.glLoadIdentity()
    gl.glOrtho(0, WIDTH, HEIGHT, 0, -1, 1)
    gl.glMatrixMode(gl.GL_MODELVIEW)
    gl.glPushMatrix()
    gl.glLoadIdentity()

    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

    # Dark overlay background
    gl.glColor4f(0.0, 0.0, 0.0, overlay_alpha)
    gl.glBegin(gl.GL_QUADS)
    gl.glVertex2f(0, 0)
    gl.glVertex2f(WIDTH, 0)
    gl.glVertex2f(WIDTH, HEIGHT)
    gl.glVertex2f(0, HEIGHT)
    gl.glEnd()

    # Render text as a textured quad
    gl.glEnable(gl.GL_TEXTURE_2D)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
    gl.glColor4f(1.0, 1.0, 1.0, 1.0)

    tx = (WIDTH - tex_w) // 2
    ty = (HEIGHT - tex_h) // 2

    gl.glBegin(gl.GL_QUADS)
    gl.glTexCoord2f(0, 1)
    gl.glVertex2f(tx, ty)
    gl.glTexCoord2f(1, 1)
    gl.glVertex2f(tx + tex_w, ty)
    gl.glTexCoord2f(1, 0)
    gl.glVertex2f(tx + tex_w, ty + tex_h)
    gl.glTexCoord2f(0, 0)
    gl.glVertex2f(tx, ty + tex_h)
    gl.glEnd()

    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    gl.glDisable(gl.GL_TEXTURE_2D)

    gl.glPopMatrix()
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glPopMatrix()
    gl.glMatrixMode(gl.GL_MODELVIEW)
    gl.glEnable(gl.GL_DEPTH_TEST)


def draw_help(surface):
    """Draw the help text overlay."""
    if use_opengl:
        tex_id = _get_help_texture()
        draw_text_overlay(surface, tex_id, _HELP_SURFACE_W, _HELP_SURFACE_H, 0.7)
    else:
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        surface.blit(s, (0, 0))
        x = (WIDTH - _HELP_SURFACE_W) // 2
        y = (HEIGHT - _HELP_SURFACE_H) // 2
        surface.blit(_HELP_SURFACE, (x, y))


def draw_journal(surface):
    """Draw the journal overlay."""
    global journal_surface, journal_surface_dirty, _journal_tex_id
    if journal_surface_dirty:
        journal_surface = _build_journal_surface()
        journal_surface_dirty = False
        if use_opengl:
            _journal_tex_id = _surface_to_texture(journal_surface, _journal_tex_id)

    if use_opengl:
        draw_text_overlay(
            surface,
            _journal_tex_id,
            journal_surface.get_width(),
            journal_surface.get_height(),
            0.75,
        )
    else:
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        surface.blit(s, (0, 0))
        x = (WIDTH - journal_surface.get_width()) // 2
        y = (HEIGHT - journal_surface.get_height()) // 2
        surface.blit(journal_surface, (x, y))


def draw_notification(surface):
    """Draw the transient collection notification."""
    global notification, notification_timer
    if not notification:
        return
    font_surf = text_surface(notification, colour=(240, 240, 180), spacing=2)
    if use_opengl:
        import OpenGL.GL as gl
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glOrtho(0, WIDTH, HEIGHT, 0, -1, 1)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        # dark pill background
        bx = (WIDTH - font_surf.get_width()) // 2 - 20
        by = 60
        bw = font_surf.get_width() + 40
        bh = font_surf.get_height() + 20
        gl.glColor4f(0.0, 0.0, 0.0, 0.6)
        gl.glBegin(gl.GL_QUADS)
        gl.glVertex2f(bx, by)
        gl.glVertex2f(bx + bw, by)
        gl.glVertex2f(bx + bw, by + bh)
        gl.glVertex2f(bx, by + bh)
        gl.glEnd()

        tex_id = _surface_to_texture(font_surf, None)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        tx = bx + 20
        ty = by + 10
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0, 1)
        gl.glVertex2f(tx, ty)
        gl.glTexCoord2f(1, 1)
        gl.glVertex2f(tx + font_surf.get_width(), ty)
        gl.glTexCoord2f(1, 0)
        gl.glVertex2f(tx + font_surf.get_width(), ty + font_surf.get_height())
        gl.glTexCoord2f(0, 0)
        gl.glVertex2f(tx, ty + font_surf.get_height())
        gl.glEnd()
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glEnable(gl.GL_DEPTH_TEST)
    else:
        surface.blit(font_surf, ((WIDTH - font_surf.get_width()) // 2, 70))


def try_collect_discovery():
    """Check if the player is near an uncollected discovery and collect it."""
    global notification, notification_timer, journal_surface_dirty
    for d in chunk_manager.all_discoveries():
        if d["name"] in inventory:
            continue
        dx = camera.x - d["x"]
        dz = camera.z - d["z"]
        if math.sqrt(dx * dx + dz * dz) < 3.0:
            name = d["name"]
            inventory.append(name)
            journal_entries.append(d)
            journal_surface_dirty = True
            notification = "Discovered: %s" % name
            notification_timer = 4.0
            return
    notification = "Nothing to discover nearby."
    notification_timer = 3.0


running = True
viewport_w = WIDTH
viewport_h = HEIGHT

while running:
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if pygame.event.get_grab():
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                else:
                    running = False

            if event.key == pygame.K_F1:
                show_help = not show_help

            if event.key == pygame.K_F11:
                toggle_fullscreen()
                viewport_w = WIDTH
                viewport_h = HEIGHT
                continue

            if event.key == pygame.K_q and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                running = False

            if event.key == pygame.K_e and pygame.event.get_grab():
                try_collect_discovery()

            if event.key == pygame.K_j and pygame.event.get_grab():
                show_journal = not show_journal

        if event.type == pygame.VIDEORESIZE and not is_fullscreen:
            WIDTH, HEIGHT = event.w, event.h
            viewport_w = WIDTH
            viewport_h = HEIGHT
            if use_opengl:
                import OpenGL.GL as gl
                gl.glViewport(0, 0, WIDTH, HEIGHT)
                renderer.width = WIDTH
                renderer.height = HEIGHT
            screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

    if not pygame.event.get_grab() and pygame.mouse.get_focused():
        if pygame.mouse.get_pressed()[0]:
            pygame.event.set_grab(True)
            pygame.mouse.set_visible(False)

    camera.update(dt)

    # Stream chunks around the player and refresh collision obstacles
    chunk_manager.update(camera.x, camera.z)
    camera.obstacles = chunk_manager.all_obstacles()

    # Update emus
    for emu in emus:
        emu.update(dt, camera.x, camera.z)
        # Keep emus grounded on terrain
        emu.y = get_terrain_height(emu.x, emu.z, WORLD_SEED, 1.5)

    # Decay notification
    if notification_timer > 0.0:
        notification_timer -= dt
        if notification_timer <= 0.0:
            notification = None

    if use_opengl:
        import OpenGL.GL as gl
        gl.glViewport(0, 0, viewport_w, viewport_h)
        gl.glClearColor(90/255, 160/255, 205/255, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        renderer.render_frame(camera, chunk_manager.all_batches())

        # Render emus as camera-facing billboards
        for emu in emus:
            surf, ex, ey, ez, w, h = emu.billboard(camera.x, camera.z)
            renderer.render_billboard(camera, surf, ex, ey, ez, w, h)
    else:
        framebuffer.clear((180, 120, 80))
        for chunk in chunk_manager.chunks.values():
            for mesh in chunk.meshes:
                renderer.render_mesh(camera, framebuffer, mesh)
        for emu in emus:
            surf, ex, ey, ez, w, h = emu.billboard(camera.x, camera.z)
            # Software path: draw the sprite as a simple quad via a mesh
            from engine.mesh import Mesh
            hw = w / 2
            hh = h
            verts = [
                (ex - hw, ey, ez),
                (ex + hw, ey, ez),
                (ex + hw, ey + hh, ez),
                (ex - hw, ey + hh, ez),
            ]
            faces = [(0, 1, 2), (0, 2, 3)]
            renderer.render_mesh(camera, framebuffer, Mesh(verts, faces, (120, 100, 80), (0, 0, 0)))
        framebuffer.present(screen)

    if show_help:
        draw_help(screen)
    elif show_journal:
        draw_journal(screen)

    if notification and not show_help:
        draw_notification(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()
