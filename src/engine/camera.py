import math
import pygame


class Camera:


    def __init__(self, radius=0.4):
        self.x = 0.0
        self.y = 0.0
        self.z = -4.0

        self.yaw = 0.0
        self.pitch = 0.0

        self.move_speed = 3
        self.sprint_factor = 2.9
        self.mouse_sensitivity = 0.003


        self.max_health = 100.0
        self.health = 100.0
        self.max_stamina = 200.0
        self.stamina = 200.0
        self.exhausted = False
        self.grab_active = False


        self.radius = radius
        self.obstacles = []
        self.bounds = None


        self.terrain_height_cb = None
        self.movement_cb = None
        self.eye_height = 1.6

        self.pivot_offset = -0.2


        self._bob_phase = 0.0
        self._bob_active = 0.0
        self.bob_offset = 0.0


        self.sprinting = False


    def forward_vec(self):
        return (math.sin(self.yaw), math.cos(self.yaw))

    def right_vec(self):
        return (math.cos(self.yaw), -math.sin(self.yaw))

    def terrain_y_at(self, tx, tz):
        if self.terrain_height_cb is not None:
            return self.terrain_height_cb(tx, tz)
        return 0.0

    def eye_position(self):

        fx, fz = self.forward_vec()
        ex = self.x + fx * self.pivot_offset
        ez = self.z + fz * self.pivot_offset
        ey = self.y + self.bob_offset
        return (ex, ey, ez)

    def take_damage(self, amount):

        self.health = max(0.0, self.health - amount)
        return self.health > 0.0

    def resolve_collision(self, px, pz):

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


    def update(self, dt, mouse_delta=None):
        dt = max(0.0, min(dt, 0.1))
        if not self.grab_active:
            self.bob_offset = 0.0
            return
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


        want_sprint = n > 0.0 and (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        

        can_sprint = want_sprint and self.stamina >= 20.0
        sprinting = can_sprint and n > 0.0
        

        if sprinting:
            drain_factor = 0.5 + 0.5 * (1.0 - self.stamina / self.max_stamina)
            self.stamina = max(0.0, self.stamina - 12.0 * dt * (0.7 + 0.3 * drain_factor))
        elif n > 0.0 and self.stamina < 20.0:

            self.stamina = max(0.0, self.stamina - 1.0 * dt)
        else:
            self.stamina = min(self.max_stamina, self.stamina + 25.0 * dt)
        
        self.exhausted = want_sprint and self.stamina <= 0.0
        self.sprinting = sprinting

        if sprinting:
            speed = self.move_speed * self.sprint_factor
        elif self.exhausted:
            speed = self.move_speed * 1.15
        else:
            speed = self.move_speed

        nx = self.x + mx * speed * dt
        nz = self.z + mz * speed * dt


        if self.movement_cb is not None:
            nx, nz = self.movement_cb(self.x, self.z, nx-self.x, nz-self.z, self.radius)
        else:
            nx, nz = self.resolve_collision(nx, nz)


        if self.bounds is not None:
            (minx, maxx, minz, maxz) = self.bounds
            nx = max(minx+self.radius, min(maxx-self.radius, nx))
            nz = max(minz+self.radius, min(maxz-self.radius, nz))

        self.x, self.z = nx, nz


        ground = self.terrain_y_at(self.x, self.z)
        target_y = ground + self.eye_height
        self.y += (target_y - self.y) * min(1.0, dt * 12.0)


        moving = n > 0.0
        if moving:
            self._bob_active = min(1.0, self._bob_active + dt * 6.0)
        else:
            self._bob_active = max(0.0, self._bob_active - dt * 6.0)

        bob_speed = speed * 1.4
        self._bob_phase += dt * bob_speed * (1.0 if moving else 0.0)

        self.bob_offset = (
            math.sin(self._bob_phase * 2.0) * 0.06 * self._bob_active
        )

        self.apply_mouse_motion(*(pygame.mouse.get_rel() if mouse_delta is None else mouse_delta))

    def apply_mouse_motion(self, dx, dy):
        # Relative motion only. No cursor teleport loop.
        if not all(math.isfinite(v) for v in (dx, dy)) or max(abs(dx), abs(dy)) > 512:
            return
        self.yaw = (self.yaw + dx*self.mouse_sensitivity + math.pi) % math.tau - math.pi
        self.pitch = max(-1.48, min(1.48, self.pitch + dy*self.mouse_sensitivity))
