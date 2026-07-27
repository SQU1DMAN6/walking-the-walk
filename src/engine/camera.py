import math
import pygame

class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = -8.0

        self.yaw = 0.0
        self.pitch = 0.0
        self.move_speed = 5.0
        self.mouse_sensitivity = 0.003

    def update(self, dt):
        keys = pygame.key.get_pressed()

        forward_x = math.sin(self.yaw)
        forward_z = math.cos(self.yaw)

        right_x = math.cos(self.yaw)
        right_z = -math.sin(self.yaw)

        if keys[pygame.K_w]:
            self.x += forward_x * self.move_speed * dt
            self.z += forward_z * self.move_speed * dt

        if keys[pygame.K_s]:
            self.x -= forward_x * self.move_speed * dt
            self.z -= forward_z * self.move_speed * dt

        if keys[pygame.K_d]:
            self.x += right_x * self.move_speed * dt
            self.z += right_z * self.move_speed * dt

        if keys[pygame.K_a]:
            self.x -= right_x * self.move_speed * dt
            self.z -= right_z * self.move_speed * dt

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
            min(
                math.radians(89),
                self.pitch
            )
        )