import math
import pygame


class Camera:
    """First-person camera with complete movement, obstacle collision,
    smooth terrain following, a visible head-bob and a negative pivot
    offset."""

    def __init__(self, radius=0.4):
        self.x = 0.0
        self.y = 0.0
        self.z = -8.0

        self.yaw = 0.0
        self.pitch = 0.0

        self.move_speed = 3
        self.sprint_factor = 2.9
        self.mouse_sensitivity = 0.003

        # Player vitals
        self.max_health = 100.0
        self.health = 100.0
        self.max_stamina = 100.0
        self.stamina = 100.0
        self.exhausted = False    # winded: sprint disabled until stamina regens
        self.window_center = None # (width, height) set by the game loop
        self.grab_active = False  # whether the mouse is grabbed (in-game)


        # Collision radius + list of obstacles to collide with
        self.radius = radius
        self.obstacles = []  # list of (cx, cz, r, height)
        self.bounds = None   # (minx, maxx, minz, maxz)

        # Terrain height callback (set externally)
        self.terrain_height_cb = None
        self.eye_height = 1.6

        self.pivot_offset = -0.2

        # Bobbing state (applied as a render offset, not fed back into y)
        self._bob_phase = 0.0
        self._bob_active = 0.0
        self.bob_offset = 0.0

        # Sprint state (visual only)
        self.sprinting = False

    # Helpers

    def forward_vec(self):
        return (math.sin(self.yaw), math.cos(self.yaw))

    def right_vec(self):
        return (math.cos(self.yaw), -math.sin(self.yaw))

    def terrain_y_at(self, tx, tz):
        if self.terrain_height_cb is not None:
            return self.terrain_height_cb(tx, tz)
        return 0.0

    def eye_position(self):
        """Return the effective eye position (pivot + forward offset + bob)."""
        fx, fz = self.forward_vec()
        ex = self.x + fx * self.pivot_offset
        ez = self.z + fz * self.pivot_offset
        ey = self.y + self.bob_offset
        return (ex, ey, ez)

    def take_damage(self, amount):
        """Reduce the player's health and return True if still alive."""
        self.health = max(0.0, self.health - amount)
        return self.health > 0.0

    def resolve_collision(self, px, pz):
        """Push (px, pz) out of any obstacle the player overlaps."""
        for (cx, cz, r, _height) in self.obstacles:
            dx = px - cx
            dz = pz - cz
            dist = math.sqrt(dx * dx + dz * dz)
            min_dist = r + self.radius
            if dist < min_dist and dist > 1e-6:
                ox = dx / dist * min_dist
                oz = dz / dist * min_dist
                px = cx + ox
                pz = cz + oz
            elif dist <= 1e-6:
                px = cx + min_dist
        return px, pz

    # Movement

    def update(self, dt):
        keys = pygame.key.get_pressed()

        fx, fz = self.forward_vec()
        rx, rz = self.right_vec()

        mx = 0.0
        mz = 0.0
        if keys[pygame.K_w]:
            mx += fx
            mz += fz
        if keys[pygame.K_s]:
            mx -= fx
            mz -= fz
        if keys[pygame.K_d]:
            mx += rx
            mz += rz
        if keys[pygame.K_a]:
            mx -= rx
            mz -= rz

        n = math.sqrt(mx * mx + mz * mz)
        if n > 0.0:
            mx /= n
            mz /= n

        # Sprint is gated by stamina: it drains while sprinting and slowly
        # regens when not sprinting.
        want_sprint = n > 0.0 and (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        sprinting = want_sprint and self.stamina > 0.0
        if sprinting:
            self.stamina = max(0.0, self.stamina - 22.0 * dt)
        else:
            self.stamina = min(self.max_stamina, self.stamina + 14.0 * dt)
        self.exhausted = want_sprint and self.stamina <= 0.0
        self.sprinting = sprinting

        if sprinting:
            speed = self.move_speed * self.sprint_factor
        elif self.exhausted:
            speed = self.move_speed * 1.15  # winded: slower than a normal walk
        else:
            speed = self.move_speed

        nx = self.x + mx * speed * dt
        nz = self.z + mz * speed * dt

        # Obstacle collision
        nx, nz = self.resolve_collision(nx, nz)

        # Bounds: keep inside terrain
        if self.bounds is not None:
            (minx, maxx, minz, maxz) = self.bounds
            nx = max(minx, min(maxx, nx))
            nz = max(minz, min(maxz, nz))

        self.x, self.z = nx, nz

        # Ground interaction (smooth terrain following)
        ground = self.terrain_y_at(self.x, self.z)
        target_y = ground + self.eye_height
        self.y += (target_y - self.y) * min(1.0, dt * 12.0)

        # Head-bob: computed as a render offset, NOT fed back into self.y.
        moving = n > 0.0
        if moving:
            self._bob_active = min(1.0, self._bob_active + dt * 6.0)
        else:
            self._bob_active = max(0.0, self._bob_active - dt * 6.0)

        bob_speed = speed * 1.4
        self._bob_phase += dt * bob_speed * (1.0 if moving else 0.0)
        # Vertical bob + slight lateral sway for a natural feel
        self.bob_offset = (
            math.sin(self._bob_phase * 2.0) * 0.06 * self._bob_active
        )

        # Mouse look: recentre the cursor each frame so rotation stays
        # unbounded (360 degrees) even when the cursor hits a screen edge.
        center = self.window_center
        if center is not None and self.grab_active:
            cx, cy = center[0] // 2, center[1] // 2
            mpx, mpy = pygame.mouse.get_pos()
            dx = mpx - cx
            dy = mpy - cy
            if abs(dx) < center[0]:
                self.yaw += dx * self.mouse_sensitivity
            if abs(dy) < center[1]:
                self.pitch += dy * self.mouse_sensitivity
            pygame.mouse.set_pos(cx, cy)
        else:
            # Fallback: relative motion (works even when not recentring)
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            if abs(mouse_dx) < 200:
                self.yaw += mouse_dx * self.mouse_sensitivity
            if abs(mouse_dy) < 200:
                self.pitch += mouse_dy * self.mouse_sensitivity

        two_pi = 2.0 * math.pi
        self.yaw = self.yaw % two_pi
        if self.yaw > math.pi:
            self.yaw -= two_pi
        elif self.yaw < -math.pi:
            self.yaw += two_pi

        self.pitch = max(
            -math.radians(89),
            min(math.radians(89), self.pitch)
        )
