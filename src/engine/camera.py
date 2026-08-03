import math
import pygame


class Camera:
    """First-person camera with complete movement, obstacle collision,
    smooth terrain following and a subtle head-bob."""

    def __init__(self, radius=0.4):
        self.x = 0.0
        self.y = 0.0
        self.z = -8.0

        self.yaw = 0.0
        self.pitch = 0.0

        self.move_speed = 3
        self.sprint_factor = 2.9
        self.mouse_sensitivity = 0.003
        self.arrow_sensitivity = 1.6

        # Collision radius + list of obstacles to collide with
        self.radius = radius
        self.obstacles = []  # list of (cx, cz, r, height)
        self.bounds = None   # (minx, maxx, minz, maxz)

        # Terrain height callback (set externally)
        self.terrain_height_cb = None
        self.eye_height = 1.6

        # Bobbing state
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

        speed = self.move_speed * (self.sprint_factor if self.sprinting else 1.0)

        mx = 0.0
        mz = 0.0
        if keys[pygame.K_w]:
            mx += fx
            mz += fz
            self.sprinting = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
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

        # Ground interaction
        ground = self.terrain_y_at(self.x, self.z)
        target_y = ground + self.eye_height
        self.y += (target_y - self.y) * min(1.0, dt * 12.0)

        # Head-bob
        moving = n > 0.0
        if moving and self.y > ground + self.eye_height - 0.05:
            self._bob_active = min(1.0, self._bob_active + dt * 6.0)
        else:
            self._bob_active = max(0.0, self._bob_active - dt * 6.0)

        bob_speed = speed * 1.2
        self._bob_phase += dt * bob_speed * (1.0 if moving else 0.0)
        self.bob_offset = math.sin(self._bob_phase * 2.0) * 0.045 * self._bob_active

        # Mouse look
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
