import math

from engine.vector import Vec3

class Renderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.focal_length = 400

    def draw_line(
        self,
        framebuffer,
        x0,
        y0,
        x1,
        y1,
        colour
    ):
        dx = x1 - x0
        dy = y1 - y0

        steps = int(max(abs(dx), abs(dy)))

        if steps == 0:
            return

        for i in range (steps + 1):
            t = i / steps

            x = int(x0 + dx * t)
            y = int(y0 + dy * t)

            framebuffer.set_pixel(x, y, colour)

    def project(self, vertex):
        z = vertex.z + 5

        if z <= 0.1:
            return None

        x = (
            vertex.x *
            self.focal_length /
            z
        )

        y = (
            vertex.y *
            self.focal_length /
            z
        )

        screen_x = int(self.width / 2 + x)
        screen_y = int(self.height / 2 - y)

        return (screen_x, screen_y)

    def draw_wire_cube(
        self,
        framebuffer,
        vertices,
        edges,
        angle
    ):
        transformed = []

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        for v in vertices:
            x = (
                v.x * cos_a
                - v.z * sin_a
            )

            z = (
                v.x * sin_a
                + v.z * cos_a
            )

            transformed.append(
                Vec3(
                    x,
                    v.y,
                    z
                )
            )

        projected = [
            self.project(v)
            for v in transformed
        ]

        for a, b in edges:
            p0 = projected[a]
            p1 = projected[b]

            if p0 is None or p1 is None:
                continue

            self.draw_line(
                framebuffer,
                p0[0], p0[1],
                p1[0], p1[1],
                (255, 255, 255)
            )

