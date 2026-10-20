from dataclasses import dataclass
import math
import random

from engine.chunk import TutorialChunk, Obstacle
from engine.guidance import PathGuide
from engine.mesh import Mesh
from engine.models import rock
from engine.paths import PathNetwork, curve, segment_distance
from engine.run_config import LENGTHS
from engine.worldgen import create_tree, create_bush, create_spinifex


class SurvivalPaths(PathNetwork):
    def __init__(self, seed, config):
        rng = random.Random(seed)
        width, depth, forks = LENGTHS[config.length]
        self.route, self.branches, self.shortcuts, self.detours, self.dead_ends = [], [], [], [], []
        south, step = depth/2-7, (depth-14)/forks
        junctions = [(rng.uniform(-2, 2), south-i*step) for i in range(forks+1)]
        for i, (a, b) in enumerate(zip(junctions, junctions[1:])):
            side = (-1 if i % 2 else 1)*width*.31
            detour = curve([a, (side, a[1]-step*.25), (side+rng.uniform(-2, 2), a[1]-step*.72), b])
            shortcut = curve([a, ((a[0]+b[0])/2+rng.uniform(-1, 1), (a[1]+b[1])/2), b])
            self.route.extend(detour if not self.route else detour[1:])
            self.detours.append(detour)
            self.shortcuts.append(shortcut)
            self.branches.append(shortcut)
            anchor = detour[len(detour)//2]
            end = (anchor[0]+(5 if side > 0 else -5), anchor[1]-rng.uniform(1, 4))
            dead = curve([anchor, ((anchor[0]+end[0])/2, anchor[1]-1), end])
            self.dead_ends.append(dead)
            self.branches.append(dead)
        self.lengths = [0.0]
        for a, b in zip(self.route, self.route[1:]):
            self.lengths.append(self.lengths[-1]+math.dist(a, b))
        self.segments = [(a, b) for line in [self.route, *self.branches] for a, b in zip(line, line[1:])]
        self._grid = {}
        for a, b in self.segments:
            for ix in range(math.floor(min(a[0], b[0])/8), math.floor(max(a[0], b[0])/8)+1):
                for iz in range(math.floor(min(a[1], b[1])/8), math.floor(max(a[1], b[1])/8)+1):
                    self._grid.setdefault((ix, iz), []).append((a, b))

    def distance(self, x, z):
        ix, iz = math.floor(x/8), math.floor(z/8)
        nearby = (segment for dx in (-1, 0, 1) for dz in (-1, 0, 1)
                  for segment in self._grid.get((ix+dx, iz+dz), ()))
        return min((segment_distance(x, z, *segment) for segment in nearby), default=16)


@dataclass
class TreeSite:
    position: tuple
    obstacle: Obstacle
    meshes: list
    removed: bool = False


class SurvivalChunk(TutorialChunk):
    def __init__(self, seed, config):
        self.seed, self.config = seed, config
        width, depth, _ = LENGTHS[config.length]
        self.bounds = (-width/2, width/2, -depth/2, depth/2)
        self.paths = SurvivalPaths(seed, config)
        self.navigator = PathGuide(self.paths)
        self.spawn, self.beacon = self.position(*self.paths.route[0]), self.position(*self.paths.route[-1])
        self.encounter = self.position(*self.paths.at(self.paths.lengths[-1]*.35))
        self.obstacles, self.details, self.trees = [], [], []
        self.render_revision = 0
        self.resources = self._resources()
        self.signs = [self.position(*line[min(4, len(line)-1)]) for line in self.paths.shortcuts]
        self.hostile_sites = self._hostiles()
        self.meshes = [self._terrain()]
        self._vegetation()
        self.validation = self.validate()

    def _resources(self):
        rng = random.Random(self.seed+831)
        result = []

        def add(kind, distance):
            x, z = self.paths.at(distance)
            before, after = self.paths.at(distance-.3), self.paths.at(distance+.3)
            dx, dz = after[0]-before[0], after[1]-before[1]
            size = max(.01, math.hypot(dx, dz))
            side = rng.choice((-1, 1))*rng.uniform(1.25, 1.65)
            result.append((kind, self.position(x+dz/size*side, z-dx/size*side)))

        # Starter mats get a guaranteed invite; RNG doesn't gate basic gear.
        add('can', rng.uniform(3, 5))
        add('bottle', rng.uniform(6, 8))
        for i in range(6):
            add('stick', 9+i*4+rng.uniform(-.5, .5))
            add('rock', 11+i*4+rng.uniform(-.5, .5))
        length = self.paths.lengths[-1]
        for kind, per100 in (('can', 2), ('bottle', 2), ('stick', 5), ('rock', 3)):
            count = max(1, round(length/100*per100*self.config.balance.resources))
            for i in range(count):
                add(kind, (i+rng.uniform(.25, .75))*length/count)
        for i, dead in enumerate(self.paths.dead_ends):
            if i % 2 == 0:
                result.append(('can', self.position(*dead[-1])))
        return result

    def _hostiles(self):
        sites = []
        balance = self.config.balance
        for zone, line in enumerate(self.paths.shortcuts):
            centre = len(line)//2
            for member in range(balance.shortcut_group+zone):
                point = line[min(len(line)-5, centre+member*2)]
                sites.append(('dog' if zone == member == 0 else 'spider', self.position(*point), 'shortcut'))
        for i in range(balance.safe_dogs):
            arc = self.paths.lengths[-1]*(.35+.5*i/max(1, balance.safe_dogs-1))
            sites.append(('dog', self.position(*self.paths.at(arc)), 'detour'))
        return sites

    def _terrain(self):
        minx, maxx, minz, maxz = self.bounds
        nx, nz = math.ceil((maxx-minx+8)/2), math.ceil((maxz-minz+8)/2)
        verts, colours, faces = [], [], []
        for iz in range(nz+1):
            for ix in range(nx+1):
                x, z = minx-4+ix*(maxx-minx+8)/nx, minz-4+iz*(maxz-minz+8)/nz
                verts.append((x, self.height(x, z), z))
                base = (116, 95, 62) if self.paths.on_path(x, z) else (49, 79, 42)
                variation = int(6*math.sin(x*.7+z*.4))
                colours.append(tuple(c+variation for c in base))
        for iz in range(nz):
            for ix in range(nx):
                a = iz*(nx+1)+ix
                faces.extend(((a, a+nx+1, a+1), (a+1, a+nx+1, a+nx+2)))
        return Mesh(verts, faces, (70, 91, 47), (0, 0, 0), vertex_colours=colours)

    def _vegetation(self):
        rng = random.Random(self.seed+17)
        minx, maxx, minz, maxz = self.bounds
        area = (maxx-minx)*(maxz-minz)
        sites = [(rng.uniform(minx+1, maxx-1), rng.uniform(minz+1, maxz-1)) for _ in range(round(area*.055))]
        for z in range(math.floor(minz), math.ceil(maxz)+1, 3):
            sites.extend(((minx-1, z), (maxx+1, z)))
        for x in range(math.floor(minx), math.ceil(maxx)+1, 3):
            sites.extend(((x, minz-1), (x, maxz+1)))
        for i, (x, z) in enumerate(sites):
            if self.paths.distance(x, z) < self.paths.half_width+3:
                continue
            if any(math.hypot(x-o.x, z-o.z) < 1.6 for o in self.obstacles):
                continue
            ground = self.height(x, z)
            tree = create_tree((x, ground, z), self.seed+i*7, base_height=4)
            radius = .7
            for mesh in tree:
                if min(v[1]+mesh.position[1]-ground for v in mesh.vertices) <= 2:
                    radius = max(radius, max(math.hypot(v[0]+mesh.position[0]-x, v[2]+mesh.position[2]-z) for v in mesh.vertices))
            if self.paths.distance(x, z) < self.paths.half_width+radius:
                continue
            obstacle = Obstacle(x, z, radius, 'tree')
            for mesh in tree:
                self.meshes.append(self._jungle(mesh, mesh.colour[1] > mesh.colour[0]))
            self.obstacles.append(obstacle)
            self.trees.append(TreeSite((x, ground, z), obstacle, tree))
            self.details.append(('tree', x, z, False))
        for i in range(round(area*.12)):
            x, z = rng.uniform(minx, maxx), rng.uniform(minz, maxz)
            on_path = self.paths.on_path(x, z)
            if on_path and rng.random() > .04:
                continue
            factory = create_bush if i % 3 == 0 else create_spinifex
            self.meshes.append(self._jungle(factory(self.position(x, z), self.seed+i*13), True))
            self.details.append(('bush' if i % 3 == 0 else 'grass', x, z, on_path))
        for i in range(round(area*.04)):
            if i % 5:
                x, z = self.paths.at(rng.uniform(0, self.paths.lengths[-1]))
                x, z = x+rng.uniform(-1.8, 1.8), z+rng.uniform(-1.8, 1.8)
            else:
                x, z = rng.uniform(minx, maxx), rng.uniform(minz, maxz)
            mesh = rock(self.seed+i)[0]
            mesh.vertices = [(vx*.35, vy*.13, vz*.35) for vx, vy, vz in mesh.vertices]
            mesh.position = self.position(x, z)
            self.meshes.append(mesh)
            self.details.append(('pebble', x, z, self.paths.on_path(x, z)))

    def remove_tree(self, site):
        if site.removed:
            return False
        site.removed = True
        self.obstacles.remove(site.obstacle)
        ids = {id(mesh) for mesh in site.meshes}
        self.meshes = [mesh for mesh in self.meshes if id(mesh) not in ids]
        self.render_revision += 1
        return True

    def chase_target(self, x, z, px, pz):
        if self.line_clear(x, z, px, pz):
            return px, pz
        return self.navigator.next_waypoint((x, z), (px, pz))

    def validate(self):
        result = super().validate()
        route, _ = self.navigator.route(self.paths.route[0], self.paths.route[-1])
        if not route or route[-1] != self.paths.route[-1]:
            raise ValueError('Disconnected path graph')
        for safe, short in zip(self.paths.detours, self.paths.shortcuts):
            if safe[0] != short[0] or safe[-1] != short[-1]:
                raise ValueError('Shortcut lost its junction')
            if sum(math.dist(a, b) for a, b in zip(short, short[1:])) >= .85*sum(math.dist(a, b) for a, b in zip(safe, safe[1:])):
                raise ValueError('Shortcut is not meaningfully shorter')
        for _, point, _ in self.hostile_sites:
            if not self.is_walkable(point[0], point[2], .45):
                raise ValueError('Blocked hostile spawn')
        result.update(shortcuts=len(self.paths.shortcuts), dead_ends=len(self.paths.dead_ends),
                      resources=len(self.resources), hostiles=len(self.hostile_sites))
        return result
