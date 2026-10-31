import math
from collections import deque
from dataclasses import dataclass


@dataclass
class DamageHit:
    bearing: float | None
    source: str
    remaining: float = 1.2


class DamageFeedback:
    def __init__(self):
        self.hits = deque(maxlen=4)

    def record(self, camera, position, source):
        bearing = None
        if position is not None:
            x, z = (position[0], position[2]) if len(position) == 3 else position
            dx, dz = x - camera.x, z - camera.z
            if math.hypot(dx, dz) > 0.001:
                bearing = math.atan2(dx, dz)
        self.hits.append(DamageHit(bearing, source))

    def update(self, dt):
        for hit in self.hits:
            hit.remaining -= max(0, dt)
        self.hits = deque((hit for hit in self.hits if hit.remaining > 0), maxlen=4)

    @staticmethod
    def relative(hit, yaw):
        return (
            None
            if hit.bearing is None
            else (hit.bearing - yaw + math.pi) % math.tau - math.pi
        )
