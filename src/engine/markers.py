from dataclasses import dataclass
import math
from engine.mesh import Mesh
from engine.models import lathe


def create_arrow():


    return [lathe([(.26, .055), (.66, .055)], (249, 220, 68), sides=8),
            lathe([(.26, .11), (.30, .11)], (50, 52, 25), sides=8),
            lathe([(0, 0), (.28, .18)], (255, 219, 55), sides=8)]


BEACON_RING_RADIUS = 1.65


def ground_arrow(world,source,goal):
    dx,dz=goal[0]-source[0],goal[1]-source[1]
    distance=math.hypot(dx,dz)
    if distance<.8:return None
    ux,uz=dx/distance,dz/distance
    ahead=min(6.,distance*.55)
    x,z=source[0]+ux*ahead,source[1]+uz*ahead
    size=min(1.,distance/3)
    outline=[(-.22,-.8),(.22,-.8),(.22,.1),(.65,.1),(0,1.),(-.65,.1),(-.22,.1)]
    points=[]
    for side,forward in outline:
        px,pz=x+(uz*side+ux*forward)*size,z+(-ux*side+uz*forward)*size
        points.append((px,world.height(px,pz)+.18,pz))
    return Mesh(points,[(0,2,1),(0,6,2),(3,5,4)],(255,64,46),(0,0,0))


def create_ring(position, height, radius=BEACON_RING_RADIUS, thickness=.18, sides=48):
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
