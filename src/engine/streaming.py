from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import json
import math
import random
import time

from engine.chunk import Obstacle, TutorialChunk
from engine.mesh import Mesh
from engine.models import lathe, rock
from engine.run_config import RIDGE_RADIUS, ARENA_RADIUS
from engine.paths import segment_distance
from engine.worldgen import create_branch, create_spinifex


CHUNK_SIZE = 32
LOAD_RADIUS = 2
MAX_CHUNKS = 36
MAX_PENDING = 2
EXPLORATION_LIMIT = 8192


def chunk_key(x, z):
    return math.floor(x/CHUNK_SIZE), math.floor(z/CHUNK_SIZE)


@dataclass
class TreeSite:
    position: tuple
    obstacle: Obstacle
    meshes: list
    key: tuple
    removed: bool = False


@dataclass
class ForestChunk:
    key: tuple
    meshes: list = field(default_factory=list)
    trees: list = field(default_factory=list)
    obstacles: list = field(default_factory=list)
    details: list = field(default_factory=list)
    revision: int = 0
    generation_ms: float = 0
    packed: object = None


class ForestStreaming:
    player_radius = .4
    bounds = (-EXPLORATION_LIMIT, EXPLORATION_LIMIT, -EXPLORATION_LIMIT, EXPLORATION_LIMIT)

    def _init_streaming(self):
        self.chunks, self.pending = {}, {}
        self.pinned_chunks = set()
        self.removed_trees = set()
        self._executor = None
        self._closed = False
        self.render_revision = 0
        self.stream_error = None
        self.failed_chunks = set()
        self.generation_times = []
        self.activations = self.evictions = 0
        centre = chunk_key(self.spawn[0], self.spawn[2])
        for key in self.desired(centre):
            self._activate(self.generate_chunk(key))

    @staticmethod
    def desired(centre):
        cx, cz = centre
        return [(cx+dx, cz+dz) for dz in range(-LOAD_RADIUS, LOAD_RADIUS+1)
                for dx in range(-LOAD_RADIUS, LOAD_RADIUS+1)]

    def height(self, x, z):
        phase = (self.seed%104729)*.731
        ridge = 6*math.sin(x*.026+phase)*math.cos(z*.017+phase*.3)
        hills = 3*math.sin(z*.052+phase)+1.1*math.sin(x*.13+z*.045+phase)
        channel = 22*math.sin(z*.019+phase)
        ravine = -3.2*math.exp(-((x-channel)/9)**2)
        return ridge+hills+ravine

    def position(self, x, z):
        return x, self.height(x, z), z

    def _density(self, x, z):
        seed = self.seed%65521
        return .5+.28*math.sin(x*.041+seed)*math.cos(z*.036-seed*.2)+.2*math.sin(z*.071+x*.02)

    def generate_chunk(self, key, safe_fallback=False):
        started = time.perf_counter()
        cx, cz = key
        rng = random.Random((self.seed*73856093 ^ cx*19349663 ^ cz*83492791) & 0xffffffffffffffff)
        chunk = ForestChunk(key)
        minx, minz = cx*CHUNK_SIZE, cz*CHUNK_SIZE
        vertices, colours, faces = [], [], []
        n = CHUNK_SIZE//2
        for iz in range(n+1):
            for ix in range(n+1):
                x, z = minx+ix*2, minz+iz*2
                y = self.height(x, z)
                vertices.append((x, y, z))
                earth = self.paths.on_path(x,z)
                density = self._density(x,z)
                base = (116, 95, 62) if earth else (44+int(density*14), 72+int(density*22), 40)
                colours.append(base)
        for iz in range(n):
            for ix in range(n):
                a = iz*(n+1)+ix
                faces.extend(((a,a+n+1,a+1),(a+1,a+n+1,a+n+2)))
        chunk.meshes.append(Mesh(vertices,faces,(70,91,47),(0,0,0),vertex_colours=colours))
        protected = [(p[0],p[2]) for _,p,_ in getattr(self,'hostile_sites',())
                     if minx-10<p[0]<minx+42 and minz-10<p[2]<minz+42]
        def clearing(x,z,radius=0):
            return (getattr(self,'is_clearing',lambda x,z:False)(x,z)
                    or any(math.hypot(x-px,z-pz)<radius+1.1 for px,pz in protected)
                    or any(segment_distance(x,z,a,b)<radius+.7 for a,b in getattr(self,'spawn_access',{}).get(key,())))
        for x,z in (() if safe_fallback else getattr(self,'ridge_index',{}).get(key,())):
            if clearing(x,z,RIDGE_RADIUS):continue
            mesh = lathe([(0,RIDGE_RADIUS),(1.5,RIDGE_RADIUS),(2.7,.8),(3.2,0)],(83,86,75),10)
            mesh.position = self.position(x,z)
            chunk.meshes.append(mesh)
            chunk.obstacles.append(Obstacle(x,z,RIDGE_RADIUS,'ridge'))
            chunk.details.append(('ridge',x,z,False))
        for index in range(0 if safe_fallback else 80):
            x, z = minx+rng.uniform(1,31), minz+rng.uniform(1,31)
            density = self._density(x,z)
            if rng.random() > density*.85 or self.paths.distance(x,z) < self.paths.half_width+1 or clearing(x,z,1):
                continue
            if any(math.hypot(x-o.x,z-o.z) < 1.7 for o in chunk.obstacles):
                continue
            ground, radius = self.height(x,z), rng.uniform(.27,.43)
            height = rng.uniform(5,8)
            trunk = lathe([(0,radius),(height*.8,radius*.55),(height,.08)],(105,74,43),6)
            trunk.position = (x,ground,z)
            canopy = lathe([(height*.58,.3),(height*.65,2.2),(height*.85,2.9),(height,2.0),(height+.5,0)],
                           (34,92+int(density*35),49),7)
            canopy.position = trunk.position
            upper = lathe([(height*.75,0),(height*.85,1.9),(height+.1,1.8),(height+.8,0)],(48,117,61),6)
            upper.position = x+1.3,ground,z-.7
            obstacle = Obstacle(x,z,radius,'tree')
            site = TreeSite(trunk.position,obstacle,[trunk,canopy,upper],(*key,index))
            chunk.meshes.extend(site.meshes)
            chunk.trees.append(site)
            chunk.obstacles.append(obstacle)
            chunk.details.append(('tree',x,z,False))
        for index in range(130):
            x, z = minx+rng.random()*32, minz+rng.random()*32
            if self.paths.distance(x,z) < self.paths.half_width+.3 or rng.random() > self._density(x,z) or clearing(x,z):
                continue
            mesh = create_spinifex(self.position(x,z),self.seed+index+cx*371+cz*761)
            mesh.colour = (43,111,58)
            chunk.meshes.append(mesh)
            chunk.details.append(('fern',x,z,False))
        for index in range(13):
            x,z = minx+rng.random()*32,minz+rng.random()*32
            big = index < 3 and not safe_fallback
            radius = rng.uniform(.65,1.15) if big else .12
            if clearing(x,z,radius) or (big and self.paths.distance(x,z) < self.paths.half_width+radius+.6):
                continue
            mesh = rock(rng.randrange(100000))[0]
            scale = radius/.39 if big else .38
            mesh.vertices = [(vx*scale,vy*(scale if big else .18),vz*scale) for vx,vy,vz in mesh.vertices]
            mesh.position = self.position(x,z)
            mesh.colour = (76,87,70) if big else (79,76,57)
            chunk.meshes.append(mesh)
            if big:
                chunk.obstacles.append(Obstacle(x,z,radius,'boulder'))
            chunk.details.append(('boulder' if big else 'pebble',x,z,False))
        for _ in range(3):
            x,z = minx+rng.random()*32,minz+rng.random()*32
            if self.paths.distance(x,z) < self.paths.half_width+2 or clearing(x,z):
                continue
            y = self.height(x,z)+.12
            end = x+rng.uniform(1,3), z+rng.uniform(1,3)
            # Roots are ankle height. The forest doesn't need invisible walls.
            chunk.meshes.append(create_branch((x,y,z),(end[0],self.height(*end)+.12,end[1]),.16,(91,66,40)))
        try:self._validate_chunk(chunk)
        except ValueError as error:
            if safe_fallback:raise
            print(json.dumps(dict(event='chunk_fallback',seed=self.seed,chunk=key,error=str(error))),flush=True)
            fallback = self.generate_chunk(key,safe_fallback=True)
            fallback.generation_ms = (time.perf_counter()-started)*1000
            return fallback
        from engine.opengl_renderer import pack_meshes
        chunk.packed = pack_meshes(chunk.meshes)
        chunk.generation_ms = (time.perf_counter()-started)*1000
        return chunk

    def _validate_chunk(self, chunk):
        for o in chunk.obstacles:
            if self.paths.distance(o.x,o.z) < self.paths.half_width+o.radius:
                raise ValueError(f'Blocked protected corridor in chunk {chunk.key}')
        for kind, pos in self.resource_index.get(chunk.key, ()):
            if any(math.hypot(pos[0]-o.x,pos[2]-o.z)<o.radius+.4 for o in chunk.obstacles):
                raise ValueError(f'Blocked {kind} in chunk {chunk.key}')
        for kind,pos,_ in getattr(self,'hostile_sites',()):
            if chunk_key(pos[0],pos[2])==chunk.key and any(math.hypot(pos[0]-o.x,pos[2]-o.z)<o.radius+.5 for o in chunk.obstacles):
                raise ValueError(f'Blocked hostile {kind} in chunk {chunk.key}')

    def _activate(self, chunk):
        removed = [site for site in chunk.trees if site.key in self.removed_trees]
        for site in removed:
            site.removed = True
            chunk.obstacles.remove(site.obstacle)
            ids = {id(m) for m in site.meshes}
            chunk.meshes = [m for m in chunk.meshes if id(m) not in ids]
        if removed:
            from engine.opengl_renderer import pack_meshes
            chunk.packed = pack_meshes(chunk.meshes)
        self.chunks[chunk.key] = chunk
        self.generation_times.append(chunk.generation_ms)
        self.generation_times = self.generation_times[-128:]
        self.activations += 1
        self.render_revision += 1

    def update_stream(self, x, z, direction=(0,-1)):
        if self._closed:
            return
        centre = chunk_key(x,z)
        pinned = set(sorted(self.pinned_chunks,key=lambda k:math.dist(k,centre))[:8])
        desired = set(self.desired(centre))|pinned
        for key,future in tuple(self.pending.items()):
            if key not in desired and future.cancel():
                del self.pending[key]
            elif future.done():
                del self.pending[key]
                try:
                    chunk = future.result()
                    if key in desired:
                        self._activate(chunk)
                except Exception as error:
                    self.stream_error = f'Chunk {key}: {error}'
                    self.failed_chunks.add(key)
                    print(json.dumps({'event':'chunk_error','error':self.stream_error}),flush=True)
                break
        distant = sorted(self.chunks,key=lambda k:math.hypot(k[0]-centre[0],k[1]-centre[1]),reverse=True)
        for key in distant:
            if key not in pinned and (max(abs(key[0]-centre[0]),abs(key[1]-centre[1])) > LOAD_RADIUS+1 or len(self.chunks)>MAX_CHUNKS):
                del self.chunks[key]
                self.evictions += 1
                self.render_revision += 1
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1,thread_name_prefix='forest-chunk')
        missing = desired-self.chunks.keys()-self.pending.keys()-self.failed_chunks
        priority = lambda k: (math.hypot(k[0]+.5-x/32,k[1]+.5-z/32)
                              -.35*((k[0]-centre[0])*direction[0]+(k[1]-centre[1])*direction[1]))
        for key in sorted(missing,key=priority)[:max(0,MAX_PENDING-len(self.pending))]:
            self.pending[key] = self._executor.submit(self.generate_chunk,key)

    def ensure_loaded(self,x,z):
        # Deterministic tooling/loading helper; never called by the frame loop.
        for key in self.desired(chunk_key(x,z)):
            if key not in self.chunks:
                self._activate(self.generate_chunk(key))
        while len(self.chunks)>MAX_CHUNKS:
            key = max(self.chunks,key=lambda k:math.dist(k,chunk_key(x,z)))
            del self.chunks[key]

    @property
    def meshes(self):
        return [mesh for c in self.chunks.values() for mesh in c.meshes]

    @property
    def obstacles(self):
        return [o for c in self.chunks.values() for o in c.obstacles]

    @property
    def trees(self):
        return [t for c in self.chunks.values() for t in c.trees if not t.removed]

    @property
    def details(self):
        return [d for c in self.chunks.values() for d in c.details]

    def nearby_obstacles(self,x,z,radius=2):
        lo,hi = chunk_key(x-radius,z-radius),chunk_key(x+radius,z+radius)
        return (o for cx in range(lo[0],hi[0]+1) for cz in range(lo[1],hi[1]+1)
                if (cx,cz) in self.chunks for o in self.chunks[cx,cz].obstacles)

    def is_walkable(self,x,z,radius=.4):
        return (chunk_key(x,z) in self.chunks and abs(x)<EXPLORATION_LIMIT-radius and abs(z)<EXPLORATION_LIMIT-radius
                and all(math.hypot(x-o.x,z-o.z)>=radius+o.radius for o in self.nearby_obstacles(x,z,radius+1.2)))

    def move(self,x,z,dx,dz,radius=.4):
        steps = max(1,math.ceil(math.hypot(dx,dz)/max(.1,radius*.5)))
        for _ in range(steps):
            for sx,sz in ((dx/steps,dz/steps),(dx/steps,0),(0,dz/steps)):
                tx,tz = x+sx,z+sz
                if (self.is_walkable(tx,tz,radius) and
                        abs(self.height(tx,tz)-self.height(x,z)) <= math.hypot(sx,sz)*1.15+.015):
                    x,z = tx,tz
                    break
        return x,z

    def line_clear(self,x,z,tx,tz,radius=.35):
        if not self.is_walkable(tx,tz,radius):
            return False
        for key in self.chunks:
            if key[0]*32>max(x,tx)+2 or (key[0]+1)*32<min(x,tx)-2 or key[1]*32>max(z,tz)+2 or (key[1]+1)*32<min(z,tz)-2:
                continue
            if any(segment_distance(o.x,o.z,(x,z),(tx,tz))<radius+o.radius for o in self.chunks[key].obstacles):
                return False
        return True

    def vision_clear(self,source,target):
        x,y,z = source
        tx,ty,tz = target
        if not self.line_clear(x,z,tx,tz,.05):
            return False
        steps = max(1,math.ceil(math.hypot(tx-x,tz-z)/.75))
        for i in range(1,steps):
            t = i/steps
            if self.height(x+(tx-x)*t,z+(tz-z)*t) > y+(ty-y)*t:
                return False
        return True

    def remove_tree(self,site):
        if site.removed:
            return False
        site.removed = True
        self.removed_trees.add(site.key)
        chunk = self.chunks[site.key[:2]]
        chunk.obstacles.remove(site.obstacle)
        ids = {id(m) for m in site.meshes}
        chunk.meshes = [m for m in chunk.meshes if id(m) not in ids]
        from engine.opengl_renderer import pack_meshes
        chunk.packed = pack_meshes(chunk.meshes)
        chunk.revision += 1
        self.render_revision += 1
        return True

    def chase_target(self,x,z,px,pz):
        if self.line_clear(x,z,px,pz):
            return px,pz
        # Nearby route nodes beat a whole-jungle Dijkstra for each pawstep.
        nodes = self.paths.nearby_segments(x,z)
        candidates = [b for a,b in nodes if self.line_clear(x,z,*b,.4)]
        return min(candidates,key=lambda p:math.dist(p,(px,pz))+math.dist(p,(x,z))*.2,default=(x,z))

    def close(self):
        self._closed = True
        if self._executor:
            self._executor.shutdown(wait=True,cancel_futures=True)
            self._executor = None
        self.pending.clear()
        self.chunks.clear()
