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
#
# The emu is drawn at 32x48 resolution so its silhouette is recognisable:
#   - a small head with a beak
#   - a long, slightly curved neck
#   - a high-set rounded body
#   - long, slender legs (roughly as tall as the body)
# The palette uses dark slate/grey-brown feathers so the animal reads as an
# emu rather than a duck, and every pixel carries an explicit alpha (no
# background fill) so edges are crisp with no white borders.

_SPRITE_W = 32
_SPRITE_H = 48

# Emu palette (dark feathers)
_FEATHER = (76, 61, 48)        # main body / neck (mottled warm grey-brown)
_FEATHER_LT = (106, 88, 66)    # top highlight / lighter flank streak
_FEATHER_DK = (46, 38, 31)     # shadow / tail / feather streak / legs
_BEAK = (218, 196, 150)
_EYE = (12, 12, 12)
_NAIL = (156, 146, 126)


def _px(g, x, y, c):
    """Set a pixel (with int rounding) if inside the sprite bounds."""
    x = int(round(x))
    y = int(round(y))
    if 0 <= x < _SPRITE_W and 0 <= y < _SPRITE_H:
        g[y][x] = (c[0], c[1], c[2], 255)


def _ellipse(g, cx, cy, rx, ry, c):
    """Fill an axis-aligned ellipse, pixel-snapped."""
    import math
    for py in range(int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1):
        for px in range(int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1):
            if ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1.0:
                _px(g, px, py, c)


def _thick_line(g, x0, y0, x1, y1, width, c):
    """Aliased thick line from (x0, y0) to (x1, y1) with rounded ends."""
    import math
    steps = int(max(abs(x1 - x0), abs(y1 - y0), 1) * 3)
    r = width / 2.0
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        for dy in range(-int(math.ceil(r)), int(math.ceil(r)) + 1):
            for dx in range(-int(math.ceil(r)), int(math.ceil(r)) + 1):
                if dx * dx + dy * dy <= r * r + 0.5:
                    _px(g, x + dx, y + dy, c)


def _draw_legs(g, leg_xs, lift):
    """Three stride states: 0=both down, 1=left lifted, 2=right lifted."""
    for i, lx in enumerate(leg_xs):
        if lift == 0 or (lift == 2 and i == 0) or (lift == 1 and i == 1):
            # leg down (full length)
            _thick_line(g, lx, 35, lx, 44, 1.4, _FEATHER_DK)
            _px(g, lx - 1, 45, _NAIL)
            _px(g, lx, 45, _NAIL)
            _px(g, lx + 1, 45, _NAIL)
        else:
            # leg lifted (shorter, foot raised)
            _thick_line(g, lx, 36, lx, 41, 1.4, _FEATHER_DK)
            _px(g, lx - 1, 42, _NAIL)
            _px(g, lx, 42, _NAIL)
            _px(g, lx + 1, 42, _NAIL)


def _feather_body(g, cx, cy):
    # shaggy, mottled streak feathers over the back/flank
    streaks = [
        (-6, -2), (-3, -3), (0, -3), (3, -2),
        (-5, 0), (-2, 0), (1, 0), (4, 0),
        (-4, 2), (-1, 2), (2, 2), (-6, -4), (5, -4),
    ]
    for i, (ox, oy) in enumerate(streaks):
        c = _FEATHER_LT if i % 2 == 0 else _FEATHER_DK
        _px(g, cx + ox, cy + oy, c)
        _px(g, cx + ox, cy + oy + 1, c)


def _rump_tufts(g, rx, ry):
    # short downward feather strokes for the fluffy rear
    _thick_line(g, rx - 2, ry + 1, rx - 2, ry + 3, 1.2, _FEATHER_DK)
    _thick_line(g, rx + 1, ry + 1, rx + 1, ry + 3, 1.2, _FEATHER_DK)


def _draw_emu(g, direction, lift):
    """Draw the emu silhouette for the given facing direction."""
    if direction in ("front", "back"):
        # Broad, high-set body
        _ellipse(g, 15.5, 30, 8.0, 5.5, _FEATHER)
        _ellipse(g, 15.5, 28.5, 6.0, 3.5, _FEATHER_LT)
        _feather_body(g, 15.5, 30)
        # Shorter neck: from y=24 to y=17 (7 units instead of 10)
        _thick_line(g, 15, 24, 15, 17, 2.4, _FEATHER)
        # Small head positioned higher and more forward
        head_c = _FEATHER_DK if direction == "back" else _FEATHER
        _ellipse(g, 15, 14.5, 3.4, 3.6, head_c)
        if direction == "front":
            # Two eyes and a small forward-pointing beak
            _px(g, 13.2, 14, _EYE)
            _px(g, 16.8, 14, _EYE)
            _thick_line(g, 15, 17, 15, 19.5, 1.6, _BEAK)
        if direction == "back":
            # Fluffy rear rump visible from behind
            _rump_tufts(g, 15, 30)
        # Long, widely-spaced legs
        _draw_legs(g, (12.0, 19.0), lift)
    else:
        # Side profile (left / right)
        facing_left = direction == "left"
        f = -1.0 if facing_left else 1.0
        body_cx = 19.0 if facing_left else 12.0
        # Body toward the back with mottled feathers, fluffy rear behind
        _ellipse(g, body_cx, 30, 8.0, 5.5, _FEATHER)
        _ellipse(g, body_cx, 28.5, 6.0, 3.5, _FEATHER_LT)
        _feather_body(g, body_cx, 30)
        rx = body_cx - f * 7.0
        _ellipse(g, rx, 31, 4.0, 2.5, _FEATHER_DK)
        _rump_tufts(g, rx, 31)
        # Straighter, shorter neck (less S-curve, more upright)
        hx = body_cx + f * 8.0
        _thick_line(g, body_cx - f * 3.0, 26, body_cx - f * 2.0, 20, 2.2, _FEATHER)
        _thick_line(g, body_cx - f * 2.0, 20, hx, 16, 1.8, _FEATHER)
        # Head + beak + eye (beak extends forward along the facing direction)
        _ellipse(g, hx, 14.5, 3.4, 3.6, _FEATHER)
        _thick_line(g, hx + f * 3.0, 15.5, hx + f * 4.3, 16.2, 2.0, _BEAK)
        _px(g, hx + f * 1.6, 14.5, _EYE)
        # Legs under the body
        _draw_legs(g, (body_cx - 2.5, body_cx + 2.5), lift)


def _build_emu_grid(direction, lift):
    """Return a _SPRITE_W x _SPRITE_H grid of (r,g,b,a) pixels."""
    g = [[(0, 0, 0, 0) for _ in range(_SPRITE_W)] for _ in range(_SPRITE_H)]
    _draw_emu(g, direction, lift)
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
        for lift in (0, 1, 2):
            lbl = ["down", "left", "right"][lift]
            g = _build_emu_grid(direction, lift)
            sprites["%s_%s" % (direction, lbl)] = _grid_to_surface(g)
    return sprites


# Emu entity

class Emu(Entity):
    """An emu that roams, detects the player and can be very aggressive.

    Rendered as a camera-facing billboard sprite.
    """

    def __init__(self, x, y, z, seed=0):
        super().__init__(x, y, z, speed=3.2, detection_range=15.0)
        self.rng = random.Random(seed)
        self.state = "idle"
        self.timer = 0.0

        # Temperament: most emus are bold and prone to chase; only a small minority flee.
        self.aggressive = self.rng.random() < 0.85

        # Attack cycle
        self.kick_range = 2.0
        self.kick_damage = 22.0
        self.attack_timer = 0.0
        self.retreat_timer = 0.0
        self._damage = 0.0  # unresolved kick damage for this frame
        
        # Tracking: remember last known player position for persistent pursuit
        self.last_player_x = x
        self.last_player_z = z
        self.tracking_timer = 0.0

        # Facing direction (cosmetic; billboard comes from camera position)
        self.yaw = self.rng.uniform(0, math.pi * 2)

        # Sprite surfaces (shared across all emus, built once)
        self._sprites = None
        self._step_phase = 0.0
        self._moving = False

        # Billboard size in world units (width, actual visual height / 2).
        # NOTE: render_billboard spans y..y+h/2 vertically, so the visible
        # height is sprite_h * 0.5. We want a tall, imposing emu (~2.6 world
        # units = taller than the player's eye height of 1.6).
        self.sprite_w = 1.7
        self.sprite_h = 5.2

    def _get_sprites(self):
        if self._sprites is None:
            self._sprites = build_emu_sprites()
        return self._sprites

    # --- Movement helpers ---

    def _angle_to_player(self, player_x, player_z):
        """Bearing from the emu toward the player (matched to move())."""
        return math.atan2(player_z - self.z, player_x - self.x)

    def _move(self, angle, spd, dt):
        """Advance the emu along `angle` (spd in world units/sec).

        `angle` comes from atan2(dz, dx); to move along (dx, dz) we apply
        cos for x and sin for z.
        """
        self.x += math.cos(angle) * spd * dt
        self.z += math.sin(angle) * spd * dt
        self.yaw = angle

    def _run_step(self, dt, moving):
        """Update the walk-cycle animation state."""
        self._moving = moving
        if moving:
            self._step_phase += dt * 6.0
        else:
            self._step_phase = 0.0

    def take_hit(self):
        """Return any kick damage dealt since the last call, then clear it."""
        d = self._damage
        self._damage = 0.0
        return d

    def update(self, dt, player_x, player_z):
        """Advance the emu's finite-state machine.

        States: idle, wander, observe, investigate, chase, flee, attack, retreat.
        Transitions depend mainly on distance to the player (plus the emu's
        temperament); aggressive emus track and pursue persistently.
        """
        dist = self.distance_to(player_x, player_z)
        
        # Update last known player position for tracking
        if dist < self.detection_range * 1.5:
            self.last_player_x = player_x
            self.last_player_z = player_z
            self.tracking_timer = 3.0  # remember for 3 seconds
        else:
            self.tracking_timer -= dt

        if self.state in ("attack", "retreat"):
            self._attack_cycle(dt, player_x, player_z)
            # Aggressive emus are persistent: only stop if player is far away
            if self.aggressive:
                if dist > self.detection_range * 3.0 and self.tracking_timer <= 0.0:
                    self.state = "idle"
                    self.timer = self.rng.uniform(1.0, 2.0)
            else:
                if dist > self.detection_range * 2.2:
                    self.state = "idle"
                    self.timer = self.rng.uniform(1.0, 2.0)
            return

        # --- Choose a behaviour based on distance to the player ---
        if self.state == "flee":
            # Keep running until the player is well clear (avoid oscillation)
            if dist > self.detection_range * 1.4:
                self.state = "idle"
                self.timer = self.rng.uniform(1.0, 2.0)
        elif dist < self.detection_range:
            if self.aggressive:
                # Bold emus chase readily and attack at range
                if dist < 5.0:
                    self.state = "attack"
                    self.attack_timer = 0.15
                elif dist < 10.0:
                    self.state = "chase"
                else:
                    self.state = "observe"
                    self.timer = self.rng.uniform(0.4, 0.8)
            else:
                # Docile emus give way but stay alert
                if dist < 3.5:
                    self.state = "flee"
                elif dist < 7.0:
                    self.state = "investigate"
                else:
                    self.state = "observe"
                    self.timer = self.rng.uniform(0.4, 0.8)
        elif self.tracking_timer > 0.0 and self.aggressive:
            # Track to last known position even if player is out of direct detection
            track_dist = math.sqrt(
                (self.last_player_x - self.x) ** 2 +
                (self.last_player_z - self.z) ** 2
            )
            if track_dist > 1.5:
                self.state = "chase"
            else:
                self.state = "observe"
                self.timer = self.rng.uniform(0.5, 1.0)
        else:
            # Player out of range: calm down
            if self.state in ("observe", "investigate", "flee", "chase"):
                self.state = "idle"
                self.timer = self.rng.uniform(1.0, 2.0)

        # --- Execute the current state ---
        moving = False
        if self.state == "observe":
            moving = False  # stand still and watch
        elif self.state == "chase":
            # Actively pursue - either directly toward player or to last known position
            if self.tracking_timer > 0.0 and dist < self.detection_range * 1.5:
                target_x, target_z = player_x, player_z
            else:
                target_x, target_z = self.last_player_x, self.last_player_z
            self._move(self._angle_to_player(target_x, target_z),
                       self.speed * 2.0, dt)
            moving = True
        elif self.state == "investigate":
            # Walk cautiously toward the player to size them up
            self._move(self._angle_to_player(player_x, player_z),
                       self.speed * 0.9, dt)
            moving = True
        elif self.state == "flee":
            # Run directly away from the player
            self._move(self._angle_to_player(player_x, player_z),
                       -self.speed * 1.9, dt)
            moving = True
        else:
            # Idle / wander (peaceful roaming)
            self.timer -= dt
            if self.timer <= 0.0:
                if self.rng.random() < 0.35:
                    self.state = "wander"
                    self.yaw = self.rng.uniform(0, math.pi * 2)
                    self.timer = self.rng.uniform(1.0, 2.5)
                else:
                    self.state = "idle"
                    self.timer = self.rng.uniform(1.5, 4.0)
            if self.state == "wander":
                self._move(self.yaw, self.speed * 0.5, dt)
                moving = True

        self._run_step(dt, moving)

        # Keep emus roughly near spawn (don't wander off the world)
        if abs(self.x) > 48:
            self.x = 48 * (1.0 if self.x > 0 else -1.0)
        if abs(self.z) > 48:
            self.z = 48 * (1.0 if self.z > 0 else -1.0)

    def _attack_cycle(self, dt, player_x, player_z):
        """Approach -> kick -> brief retreat -> repeat until the player flees."""
        if self.state == "attack":
            self.attack_timer -= dt
            # Rapidly close in on the player
            self._move(self._angle_to_player(player_x, player_z),
                       self.speed * 2.2, dt)
            self._run_step(dt, True)
            d = self.distance_to(player_x, player_z)
            # Kick when in range and the cooldown has elapsed
            if d < self.kick_range and self.attack_timer <= 0.0:
                self._damage = self.kick_damage
                self.attack_timer = 0.5  # brief pause after kicking
            if self.attack_timer <= -0.25:
                self.state = "retreat"
                self.retreat_timer = 0.5
        else:  # retreat
            self.retreat_timer -= dt
            self._move(self._angle_to_player(player_x, player_z),
                       -self.speed * 1.6, dt)
            self._run_step(dt, True)
            if self.retreat_timer <= 0.0:
                self.state = "attack"
                self.attack_timer = 0.3

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

        # Animation: three stride states (down / left lifted / right lifted)
        if self._moving:
            lbl = ["down", "left", "right"][int(self._step_phase) % 3]
        else:
            lbl = "down"
        key = "%s_%s" % (direction, lbl)
        return (sprites[key], self.x, self.y, self.z, self.sprite_w, self.sprite_h)
