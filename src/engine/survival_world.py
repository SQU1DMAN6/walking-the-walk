import math
import random

from engine.guidance import PathGuide
from engine.paths import PathNetwork, curve, segment_distance
from engine.run_config import LENGTHS
from engine.streaming import ForestStreaming, chunk_key, TreeSite


class SurvivalPaths(PathNetwork):
    def __init__(self, seed, config):
        rng = random.Random(seed)
        width, depth, forks = LENGTHS[config.length]
        self.route, self.branches, self.shortcuts, self.detours, self.dead_ends = [], [], [], [], []
        south, step = depth/2-7, (depth-14)/forks
        junctions = [(rng.uniform(-2, 2), south-i*step) for i in range(forks+1)]
        for i, (a, b) in enumerate(zip(junctions, junctions[1:])):
            side = (-1 if i % 2 else 1)*width*rng.uniform(.31,.37)
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

    def nearby_segments(self, x, z):
        ix, iz = math.floor(x/8), math.floor(z/8)
        nearby = (segment for dx in (-1, 0, 1) for dz in (-1, 0, 1)
                  for segment in self._grid.get((ix+dx, iz+dz), ()))
        return nearby

    def distance(self, x, z):
        return min((segment_distance(x,z,*s) for s in self.nearby_segments(x,z)),default=16)


class SurvivalChunk(ForestStreaming):
    def __init__(self,seed,config):
        self.seed,self.config = seed,config
        self.paths = SurvivalPaths(seed,config)
        self.navigator = PathGuide(self.paths)
        self.spawn,self.beacon = self.position(*self.paths.route[0]),self.position(*self.paths.route[-1])
        self.encounter = self.position(*self.paths.at(70))
        self.resources = self._resources()
        self.resource_index = {}
        for kind,pos in self.resources:
            self.resource_index.setdefault(chunk_key(pos[0],pos[2]),[]).append((kind,pos))
        self.signs = [self.position(*line[4]) for line in self.paths.shortcuts]
        self.hostile_sites = self._hostiles()
        self._init_streaming()
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
        rng = random.Random(self.seed+1223)
        sites = []
        balance = self.config.balance
        for zone,line in enumerate(self.paths.shortcuts):
            count = min(6,balance.shortcut_group+zone//3)
            centre = len(line)//2
            for member in range(count):
                x,z = line[min(len(line)-5,centre+member*5)]
                sites.append(('dog' if zone == member == 0 else 'spider',self.position(x,z),'shortcut'))
        count = max(1,round(self.paths.lengths[-1]/350))*balance.safe_dogs
        for i in range(count):
            distance = 65+(i+rng.uniform(.1,.8))*(self.paths.lengths[-1]-100)/count
            sites.append(('dog',self.position(*self.paths.at(distance)),'detour'))
        return sites

    def validate(self):
        route,_ = self.navigator.route(self.paths.route[0],self.paths.route[-1])
        if not route or route[-1] != self.paths.route[-1]:
            raise ValueError('Disconnected route graph')
        for safe,short in zip(self.paths.detours,self.paths.shortcuts):
            if safe[0] != short[0] or safe[-1] != short[-1]:
                raise ValueError('Shortcut lost its junction')
            if sum(math.dist(a,b) for a,b in zip(short,short[1:])) >= .95*sum(math.dist(a,b) for a,b in zip(safe,safe[1:])):
                raise ValueError('Shortcut is not shorter')
        for x,z in self.paths.route[::3]:
            if any(abs(self.height(x+dx,z+dz)-self.height(x,z))>1.12 for dx,dz in ((1,0),(0,1))):
                raise ValueError('Unwalkable route slope')
        return dict(connected=True,route_samples=len(self.paths.route),route_length=round(self.paths.lengths[-1],2),
                    destination_distance=round(math.dist(self.spawn,self.beacon),2),shortcuts=len(self.paths.shortcuts),
                    dead_ends=len(self.paths.dead_ends),resources=len(self.resources),hostiles=len(self.hostile_sites),
                    initial_chunks=len(self.chunks),obstacles=len(self.obstacles))
