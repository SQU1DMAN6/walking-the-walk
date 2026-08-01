"""Walking The Walk — First-person outback exploration."""
import math
import sys

import pygame

from engine.bitmapfont import text_surface
from engine.framebuffer import Framebuffer
from engine.renderer import Renderer
from engine.opengl_renderer import OpenGLRenderer, build_batches
from engine.mesh import Mesh, create_prism, create_pyramid, create_ground
from engine.camera import Camera
from engine.worldgen import generate_world, get_terrain_height

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

# Generate the procedural world once
WORLD_SEED = 42
world_meshes = generate_world(seed=WORLD_SEED, terrain_size=100, terrain_segments=30)

renderer = OpenGLRenderer(WIDTH, HEIGHT) if use_opengl else Renderer(WIDTH, HEIGHT)

if use_opengl:
    world_batches = build_batches(world_meshes)
else:
    world_batches = None

show_help = True

HELP_TEXT = (
    "=== Walking The Walk ===\n"
    "\n"
    "Controls:\n"
    "  W/A/S/D    - Move forward/left/backward/right\n"
    "  Mouse      - Look around\n"
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
    "  Discover its secrets.\n\n"
    "Use F1 to close this Help message.\n"
)

# Pre-render help text surface
_HELP_SURFACE = text_surface(HELP_TEXT, colour=(200, 200, 200), spacing=2)
_HELP_SURFACE_W = _HELP_SURFACE.get_width()
_HELP_SURFACE_H = _HELP_SURFACE.get_height()

# OpenGL texture ID for help overlay (lazy init)
_help_tex_id = None


def _get_help_texture():
    """Convert the pre-rendered help surface to an OpenGL texture."""
    global _help_tex_id
    if _help_tex_id is not None:
        return _help_tex_id

    import OpenGL.GL as gl
    # Convert pygame surface to raw RGBA data
    mode = _HELP_SURFACE.get_bytesize()
    if mode == 4:
        fmt = gl.GL_RGBA
    else:
        fmt = gl.GL_RGB

    data = pygame.image.tostring(_HELP_SURFACE, "RGBA", True)

    _help_tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, _help_tex_id)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                    _HELP_SURFACE_W, _HELP_SURFACE_H, 0,
                    gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
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


def draw_help(surface):
    """Draw the help text overlay."""
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

        # Dark overlay background
        gl.glColor4f(0.0, 0.0, 0.0, 0.7)
        gl.glBegin(gl.GL_QUADS)
        gl.glVertex2f(0, 0)
        gl.glVertex2f(WIDTH, 0)
        gl.glVertex2f(WIDTH, HEIGHT)
        gl.glVertex2f(0, HEIGHT)
        gl.glEnd()

        # Render help text as a textured quad
        tex_id = _get_help_texture()
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glColor4f(1.0, 1.0, 1.0, 1.0)

        tx = (WIDTH - _HELP_SURFACE_W) // 2
        ty = (HEIGHT - _HELP_SURFACE_H) // 2

        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0, 1)
        gl.glVertex2f(tx, ty)
        gl.glTexCoord2f(1, 1)
        gl.glVertex2f(tx + _HELP_SURFACE_W, ty)
        gl.glTexCoord2f(1, 0)
        gl.glVertex2f(tx + _HELP_SURFACE_W, ty + _HELP_SURFACE_H)
        gl.glTexCoord2f(0, 0)
        gl.glVertex2f(tx, ty + _HELP_SURFACE_H)
        gl.glEnd()

        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glDisable(gl.GL_TEXTURE_2D)

        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glEnable(gl.GL_DEPTH_TEST)
    else:
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        surface.blit(s, (0, 0))
        x = (WIDTH - _HELP_SURFACE_W) // 2
        y = (HEIGHT - _HELP_SURFACE_H) // 2
        surface.blit(_HELP_SURFACE, (x, y))


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

    terrain_y = get_terrain_height(camera.x, camera.z, WORLD_SEED, 1.5)
    eye_height = 1.6
    if camera.y < terrain_y + eye_height:
        camera.y = terrain_y + eye_height

    if use_opengl:
        import OpenGL.GL as gl
        gl.glViewport(0, 0, viewport_w, viewport_h)
        gl.glClearColor(90/255, 160/255, 205/255, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        renderer.render_frame(camera, world_batches)
    else:
        framebuffer.clear((180, 120, 80))
        for mesh in world_meshes:
            renderer.render_mesh(camera, framebuffer, mesh)
        framebuffer.present(screen)

    if show_help:
        draw_help(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()
