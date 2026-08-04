"""Emu wildlife system — idle → roaming → detect player → react (flee).

Emus are rendered as 2D billboard sprites (pixel art) that always face the
camera. Each emu has 8 sprites: 4 directions (front/back/left/right) x 2
states (feet-on-ground / feet-up). The feet state toggles while moving to
simulate walking. All sprites are generated procedurally at runtime — no
external assets or dependencies.
"""
import math
import random

import pygame

from engine.entity import Entity


# Procedural pixel-art emu sprites

# Emu palette
_BODY = (105, 80, 50)
_NECK = (90, 105, 90)
_BEAK = (200, 160, 90)
_LEG = (120, 100, 80)
_EYE = (20, 20, 20)

_SPRITE_W = 16
_SPRITE_H = 24


def _build_emu_grid(direction, feet_up):
    """Return a 16x24 grid of (r,g,b,a) pixels for the given direction/state."""
    g = [[(0, 0, 0, 0) for _ in range(_SPRITE_W)] for _ in range(_SPRITE_H)]

    def px(x, y, c):
        if 0 <= x < _SPRITE_W and 0 <= y < _SPRITE_H:
            g[y][x] = (c[0], c[1], c[2], 255)

    # Body: rounded blob, rows 12-20, cols 3-12
    for y in range(12, 21):
        for x in range(3, 13):
            if (x == 3 or x == 12) and (y == 12 or y == 20):
                continue
            px(x, y, _BODY)

    # Neck: rises from body top to head
    neck_x = 7 if direction in ("front", "back") else (5 if direction == "left" else 9)
    for y in range(3, 12):
        px(neck_x, y, _NECK)
        px(neck_x + 1, y, _NECK)

    # Head
    head_x = neck_x - 1
    for y in range(1, 4):
        for x in range(head_x, head_x + 3):
            px(x, y, _NECK)

    # Beak
    if direction in ("front", "right"):
        px(head_x + 3, 2, _BEAK)
        px(head_x + 3, 3, _BEAK)
    else:  # back, left
        px(head_x - 1, 2, _BEAK)
        px(head_x - 1, 3, _BEAK)

    # Eye
    if direction in ("front", "right"):
        px(head_x + 2, 2, _EYE)
    else:
        px(head_x, 2, _EYE)

    # Legs
    leg_x1 = 5
    leg_x2 = 9
    if feet_up:
        for y in range(19, 22):
            px(leg_x1, y, _LEG)
            px(leg_x2, y, _LEG)
    else:
        for y in range(19, 24):
            px(leg_x1, y, _LEG)
            px(leg_x2, y, _LEG)

    return g


def _grid_to_surface(g):
    """Convert a pixel grid to a pygame SRCALPHA surface."""
    surf = pygame.Surface((_SPRITE_W, _SPRITE_H), pygame.SRCALPHA)
    for y in range(_SPRITE_H):
        for x in range(_SPRITE_W):
            surf.set_at((x, y), g[y][x])
    return surf


def build_emu_sprites():
    """Generate all 8 emu sprites as pygame surfaces.

    Returns a dict keyed by "front_down", "front_up", "back_down", ... etc.
    """
    sprites = {}
    for direction in ("front", "back", "left", "right"):
        for state in ("down", "up"):
            g = _build_emu_grid(direction, state == "up")
            sprites["%s_%s" % (direction, state)] = _grid_to_surface(g)
    return sprites


# Emu entity

class Emu(Entity):
    """An emu that roams, detects the player and flees.

    Rendered as a camera-facing billboard sprite.
    """

    def __init__(self, x, y, z, seed=0):
        super().__init__(x, y, z, speed=2.6, detection_range=9.0)
        self.rng = random.Random(seed)
        self.state = "idle"
        self.timer = 0.0
        self.flee_yaw = 0.0
        # Facing direction
        self.yaw = self.rng.uniform(0, math.pi * 2)

        # Sprite surfaces (shared across all emus, built once)
        self._sprites = None
        self._step_phase = 0.0
        self._moving = False

        # Billboard size in world units (width, height)
        self.sprite_w = 1.4
        self.sprite_h = 2.2

    def _get_sprites(self):
        if self._sprites is None:
            self._sprites = build_emu_sprites()
        return self._sprites

    def update(self, dt, player_x, player_z):
        dist = self.distance_to(player_x, player_z)

        # State machine
        if dist < self.detection_range:
            self.state = "react" if dist < 5.0 else "detect"
        elif self.state in ("detect", "react"):
            self.state = "idle"

        moving = False
        if self.state in ("detect", "react"):
            # Flee away from player
            dx = self.x - player_x
            dz = self.z - player_z
            if dx == 0 and dz == 0:
                dx = 0.1
            self.flee_yaw = math.atan2(dz, dx)
            spd = self.speed * (1.8 if self.state == "react" else 1.3)
            self.x += math.sin(self.flee_yaw) * spd * dt
            self.z += math.cos(self.flee_yaw) * spd * dt
            self.yaw = self.flee_yaw
            moving = True
        else:
            # Idle / roam
            self.timer -= dt
            if self.timer <= 0.0:
                if self.rng.random() < 0.3:
                    self.state = "roam"
                    self.yaw = self.rng.uniform(0, math.pi * 2)
                    self.timer = self.rng.uniform(1.0, 3.0)
                else:
                    self.state = "idle"
                    self.timer = self.rng.uniform(1.5, 4.0)

            if self.state == "roam":
                self.x += math.sin(self.yaw) * self.speed * 0.5 * dt
                self.z += math.cos(self.yaw) * self.speed * 0.5 * dt
                moving = True

        self._moving = moving

        # Step animation: toggle feet state while moving
        if moving:
            self._step_phase += dt * 6.0
        else:
            self._step_phase = 0.0

        # Keep emus roughly near spawn (don't wander off the world)
        if abs(self.x) > 48:
            self.x = 48 * (1.0 if self.x > 0 else -1.0)
        if abs(self.z) > 48:
            self.z = 48 * (1.0 if self.z > 0 else -1.0)

    def billboard(self, camera_x, camera_z):
        """Return (surface, x, y, z, width, height) for the current frame.

        Picks the sprite direction based on the emu's position relative to
        the camera, and toggles the feet state while moving.
        """
        sprites = self._get_sprites()

        # Direction relative to camera
        dx = self.x - camera_x
        dz = self.z - camera_z
        # Determine dominant axis in world space
        if abs(dx) > abs(dz):
            direction = "right" if dx > 0 else "left"
        else:
            direction = "front" if dz > 0 else "back"

        # Feet state
        feet = "up" if (self._moving and int(self._step_phase) % 2 == 0) else "down"

        key = "%s_%s" % (direction, feet)
        return (sprites[key], self.x, self.y, self.z, self.sprite_w, self.sprite_h)
