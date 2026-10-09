from dataclasses import dataclass
import math
from engine.mesh import Mesh
from engine.models import lathe


def create_arrow():


    return [lathe([(.26, .055), (.66, .055)], (249, 220, 68), sides=8),
            lathe([(.26, .11), (.30, .11)], (50, 52, 25), sides=8),
            lathe([(0, 0), (.28, .18)], (255, 219, 55), sides=8)]


def create_ring(position, height, radius=1.65, thickness=.18, sides=48):
    x, _, z = position
    verts, faces = [], []
    for i in range(sides):
        angle = math.tau*i/sides
        for r in (radius-thickness/2, radius+thickness/2):
            vx, vz = r*math.cos(angle), r*math.sin(angle)
            verts.append((vx, height(x+vx, z+vz)-position[1]+.055, vz))
    for i in range(sides):
        a, b = i*2, ((i+1) % sides)*2
        faces.extend(((a, b, a+1), (a+1, b, b+1)))
    return Mesh(verts, faces, (119, 244, 220), (0, 0, 0))


@dataclass(frozen=True)
class ObjectiveMarker:
    target_id: int
    style: str = 'arrow'

    def position(self, entities, elapsed=0.0):
        target = entities.get(self.target_id)
        if target is None or not target.visible:
            return None
        x, y, z = target.position
        offset = target.visual_height+.22+.08*math.sin(elapsed*2.5) if self.style == 'arrow' else 0
        return x, y+offset, z
