import json
import math
import random

from engine.paths import PathNetwork, curve, segment_distance
from engine.run_config import LENGTHS, GENERATION_ATTEMPTS, ROUTE_TOLERANCE, ARENA_APPROACH, RIDGE_RADIUS, ROUTES


def length(line):
    return sum(math.dist(a,b) for a,b in zip(line,line[1:]))


class SurvivalPaths(PathNetwork):
    def __init__(self,seed,config):
        self.seed,self.config = seed,config
        self.fallback = False
        for attempt in range(GENERATION_ATTEMPTS):
            try:
                self._generate(random.Random(seed+attempt*104729))
                self.validate()
                self.attempts = attempt+1
                return
            except ValueError as error:
                print(json.dumps(dict(event='route_retry',seed=seed,attempt=attempt+1,error=str(error))),flush=True)
        self.fallback = True
        self._generate(random.Random(160027),fallback=True)
        self.validate()
        self.attempts = GENERATION_ATTEMPTS
        print(json.dumps(dict(event='route_fallback',seed=seed,length=config.length)),flush=True)

    def _generate(self,rng,fallback=False):
        _,target,forks = LENGTHS[self.config.length]
        self.route,self.shortcuts,self.detours,self.dead_ends,self.crosslinks = [],[],[],[],[]
        a = (0.,0.)
        heading = 0.
        for i in range(forks):
            heading = 0 if fallback else rng.uniform(-ROUTES['heading'],ROUTES['heading'])
            step = 76 if fallback else rng.uniform(*ROUTES['step'])
            forward,side = (math.sin(heading),-math.cos(heading)),(math.cos(heading),math.sin(heading))
            sign = -1 if i%2 else 1
            spread = 43 if fallback else rng.uniform(*ROUTES['spread'])
            b = a[0]+forward[0]*step,a[1]+forward[1]*step
            def point(t,offset):return a[0]+forward[0]*step*t+side[0]*offset,a[1]+forward[1]*step*t+side[1]*offset
            detour = curve([a,point(.24,sign*spread),point(.73,sign*spread*rng.uniform(.9,1.15)),b])
            short = curve([a,point(.48,0 if fallback else rng.uniform(-5,5)),b])
            self.route.extend(detour if not self.route else detour[1:])
            self.detours.append(detour)
            self.shortcuts.append(short)
            a = b
        end = a[0]+math.sin(heading)*54,a[1]-math.cos(heading)*54
        self.route.extend(curve([a,end])[1:])
        scale = target/length(self.route)
        transform = lambda p:(p[0]*scale,p[1]*scale)
        self.route = list(map(transform,self.route))
        self.detours = [list(map(transform,line)) for line in self.detours]
        self.shortcuts = [list(map(transform,line)) for line in self.shortcuts]
        for i,line in enumerate(self.detours):
            anchor = line[len(line)//2]
            direction = -1 if i%2 else 1
            end = anchor[0]+direction*6,anchor[1]+rng.uniform(-3,3)
            self.dead_ends.append(curve([anchor,end]))
        for i in range(1,len(self.detours)-1,3):
            a,b = self.detours[i][len(self.detours[i])//2],self.detours[i+1][len(self.detours[i+1])//2]
            mid = (a[0]+b[0])/2+rng.uniform(-8,8),(a[1]+b[1])/2
            self.crosslinks.append(curve([a,mid,b]))
        self.branches = [*self.shortcuts,*self.dead_ends,*self.crosslinks]
        self.lengths = [0.]
        for a,b in zip(self.route,self.route[1:]):self.lengths.append(self.lengths[-1]+math.dist(a,b))
        self.segments = [(a,b) for line in [self.route,*self.branches] for a,b in zip(line,line[1:])]
        self._grid = {}
        for a,b in self.segments:
            for ix in range(math.floor(min(a[0],b[0])/8),math.floor(max(a[0],b[0])/8)+1):
                for iz in range(math.floor(min(a[1],b[1])/8),math.floor(max(a[1],b[1])/8)+1):
                    self._grid.setdefault((ix,iz),[]).append((a,b))
        self.arena = self.at(self.lengths[-1]-ARENA_APPROACH)
        self.ridges = []
        for safe,short in zip(self.detours,self.shortcuts):
            for i in range(12,89):
                t = i/100
                a,b = safe[round(t*(len(safe)-1))],short[round(t*(len(short)-1))]
                midpoint = (a[0]+b[0])/2,(a[1]+b[1])/2
                if (math.dist(a,b)>14 and self.distance(*midpoint)>self.half_width+RIDGE_RADIUS+1
                        and math.dist(midpoint,self.arena)>24
                        and all(math.dist(midpoint,p)>ROUTES['ridge_spacing'] for p in self.ridges)):
                    self.ridges.append(midpoint)

    def nearby_segments(self,x,z):
        ix,iz = math.floor(x/8),math.floor(z/8)
        return (s for dx in (-1,0,1) for dz in (-1,0,1) for s in self._grid.get((ix+dx,iz+dz),()))

    def distance(self,x,z):
        return min((segment_distance(x,z,*s) for s in self.nearby_segments(x,z)),default=32)

    def validate(self):
        target = self.config.target_distance
        if not (1-ROUTE_TOLERANCE)*target<=self.lengths[-1]<=(1+ROUTE_TOLERANCE)*target:
            raise ValueError('Primary route outside distance tolerance')
        if any(length(short)>.9*length(safe) for safe,short in zip(self.detours,self.shortcuts)):
            raise ValueError('Shortcut lost its distance advantage')
        if any(math.dist(safe[len(safe)//2],short[len(short)//2])<ROUTES['minimum_separation']
               for safe,short in zip(self.detours,self.shortcuts)):
            raise ValueError('Route alternatives collapsed together')
        if not self.ridges:
            raise ValueError('Missing physical route separation')
        return True
