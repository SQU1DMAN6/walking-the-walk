from dataclasses import dataclass
import math
import random

from engine.mesh import Mesh
from engine.paths import PathNetwork, segment_distance
from engine.worldgen import create_tree, create_bush, create_spinifex, get_terrain_height
from engine.models import rock


@dataclass(frozen=True)
class Obstacle:
    x: float
    z: float
    radius: float
    kind: str


class TutorialChunk:
    bounds = (-36.0, 36.0, -36.0, 36.0)
    player_radius = .4

    def __init__(self, seed=42):
        self.seed = seed
        self.paths = PathNetwork(seed)
        self.spawn = self.position(*self.paths.route[0])
        self.beacon = self.position(*self.paths.route[-1])

        self.resources = [(kind, self.position(*self.paths.at(distance)))
                          for kind, distance in [('can', 9), ('bottle', 15),
                                                 ('stick', 32), ('stick', 37), ('rock', 43)]]
        self.encounter = self.position(*self.paths.at(64))
        self.obstacles = []
        self.meshes = [self._terrain()]
        self.details = []
        self._vegetation()
        self.validation = self.validate()

    def height(self, x, z):
        return get_terrain_height(x, z, self.seed, height_scale=.8)

    def position(self, x, z):
        return (x, self.height(x, z), z)

    def _terrain(self):
        verts, colours, faces = [], [], []
        segments, width = 80, 80
        for iz in range(segments + 1):
            for ix in range(segments + 1):
                x, z = -40 + ix * width/segments, -40 + iz * width/segments
                verts.append((x, self.height(x, z), z))
                earth = self.paths.on_path(x, z)
                variation = int(6 * math.sin(x*.7 + z*.4))
                base = (116, 95, 62) if earth else (49, 79, 42)
                colours.append(tuple(c + variation for c in base))
        for iz in range(segments):
            for ix in range(segments):
                a = iz * (segments+1) + ix
                faces.extend(((a, a+segments+1, a+1), (a+1, a+segments+1, a+segments+2)))
        return Mesh(verts, faces, (70, 91, 47), (0, 0, 0), vertex_colours=colours)

    @staticmethod
    def _jungle(mesh, leaf=False):

        if leaf:
            mesh.colour = (40, 104, 54)
        else:
            mesh.colour = tuple(round(c / 24) * 24 for c in mesh.colour)
        return mesh

    def _vegetation(self):
        rng = random.Random(self.seed)
        sites = [(rng.uniform(-35, 35), rng.uniform(-35, 35)) for _ in range(630)]

        for edge in (-37.5, 37.5):
            for n in range(40):
                v = -39 + n * 2
                sites.extend(((edge, v), (v, edge)))
        for i, (x, z) in enumerate(sites):
            if self.paths.distance(x, z) < self.paths.half_width + 2.8:
                continue
            if any(math.hypot(x-o.x, z-o.z) < 1.4 for o in self.obstacles):
                continue
            tree = create_tree(self.position(x, z), self.seed + i*7, base_height=4.5)


            ground = self.height(x, z)
            radius = .7
            # Low branches count too; keep the route clear.
            for mesh in tree:
                if min(v[1]+mesh.position[1]-ground for v in mesh.vertices) <= 2.0:
                    radius = max(radius, max(math.hypot(v[0]+mesh.position[0]-x,
                                                       v[2]+mesh.position[2]-z) for v in mesh.vertices))
            if self.paths.distance(x, z) < self.paths.half_width + radius:
                continue

            for mesh in tree:
                self.meshes.append(self._jungle(mesh, mesh.colour[1] > mesh.colour[0]))
            self.obstacles.append(Obstacle(x, z, radius, 'tree'))
            self.details.append(('tree', x, z, False))
        for i in range(1100):
            x, z = rng.uniform(-38, 38), rng.uniform(-38, 38)
            if self.paths.distance(x, z) < self.paths.half_width + 1.05:
                continue
            mesh = self._jungle(create_bush(self.position(x, z), self.seed + i*13), True)
            self.meshes.append(mesh)
            self.details.append(('bush', x, z, False))
        for i in range(2200):
            x, z = rng.uniform(-38, 38), rng.uniform(-38, 38)
            on_path = self.paths.on_path(x, z)
            if on_path and rng.random() > .06:
                continue
            grass = self._jungle(create_spinifex(self.position(x, z), self.seed+i*31), True)
            self.meshes.append(grass)
            self.details.append(('grass', x, z, on_path))

        for i in range(250):
            if i < 200:
                x, z = self.paths.at(rng.uniform(0, self.paths.lengths[-1]))
                x += rng.uniform(-1.9, 1.9)
                z += rng.uniform(-1.9, 1.9)
            else:
                x, z = rng.uniform(-35, 35), rng.uniform(-35, 35)
            mesh = rock(self.seed+i)[0]
            mesh.vertices = [(vx*.45, vy*.16, vz*.45) for vx, vy, vz in mesh.vertices]
            mesh.position = self.position(x, z)
            self.meshes.append(mesh)
            self.details.append(('stone', x, z, self.paths.on_path(x, z)))

    def is_walkable(self, x, z, radius=.4):
        minx, maxx, minz, maxz = self.bounds
        return (minx+radius <= x <= maxx-radius and minz+radius <= z <= maxz-radius
                and all(math.hypot(x-o.x, z-o.z) >= radius+o.radius for o in self.obstacles))

    def move(self, x, z, dx, dz, radius=.4):

        minx, maxx, minz, maxz = self.bounds
        tx = max(minx+radius, min(maxx-radius, x+dx))
        tz = max(minz+radius, min(maxz-radius, z+dz))
        dx, dz = tx-x, tz-z
        steps = max(1, math.ceil(math.hypot(dx, dz) / (radius*.5)))
        dx, dz = dx/steps, dz/steps
        for _ in range(steps):
            if self.is_walkable(x+dx, z+dz, radius):
                x, z = x+dx, z+dz
            elif self.is_walkable(x+dx, z, radius):
                x += dx
            elif self.is_walkable(x, z+dz, radius):
                z += dz
        return x, z

    def line_clear(self, x, z, tx, tz, radius=.35):
        return (self.is_walkable(tx, tz, radius) and
                all(segment_distance(o.x, o.z, (x, z), (tx, tz)) >= radius+o.radius
                    for o in self.obstacles))

    def chase_target(self, x, z, px, pz):
        if self.line_clear(x, z, px, pz):
            return px, pz
        i = self.paths.nearest_route_index(x, z)
        j = self.paths.nearest_route_index(px, pz)
        nearest = self.paths.route[i]
        if math.hypot(x-nearest[0], z-nearest[1]) > .9:
            return nearest
        return self.paths.route[i + (1 if j > i else -1 if j < i else 0)]

    def validate(self):


        for a, b in self.paths.segments:
            for x, z in (a, b):
                if not self.is_walkable(x, z, self.paths.half_width):
                    raise ValueError('Path width collides with vegetation or boundary')
            for o in self.obstacles:
                if segment_distance(o.x, o.z, a, b) < self.paths.half_width + o.radius:
                    raise ValueError('Obstruction in protected path corridor')
        for _, pos in self.resources:
            if not self.is_walkable(pos[0], pos[2]):
                raise ValueError('Unreachable resource')
        if not self.is_walkable(self.encounter[0], self.encounter[2]):
            raise ValueError('Blocked encounter')
        samples = self.paths.samples()
        if not all(self.is_walkable(x, z) for x, z in samples):
            raise ValueError('Disconnected guaranteed route')
        return {'route_samples': len(samples), 'route_length': round(self.paths.lengths[-1], 2),
                'obstacles': len(self.obstacles), 'connected': True}
