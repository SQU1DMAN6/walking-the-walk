import math
from collections import Counter, deque
from dataclasses import dataclass
from functools import lru_cache

from engine.animation import ease
from engine.mesh import Mesh, MeshPose, create_prism
from engine.models import lathe

LIFETIMES = {
    "pickup": 0.65,
    "crafted": 0.8,
    "consumed": 0.8,
    "enemy_defeated": 1.35,
    "boss_defeated": 3.0,
    "player_died": 0.9,
    "beacon_activated": 1.1,
    "tree_felled": 0.45,
    "tree_impact": 0.75,
    "tree_hit": 0.7,
}
COLOURS = {
    "pickup": (241, 218, 112),
    "crafted": (155, 234, 176),
    "food": (143, 224, 135),
    "water": (102, 209, 242),
    "bandage": (158, 240, 183),
    "tree_impact": (153, 125, 78),
    "tree_felled": (177, 143, 87),
    "enemy_defeated": (137, 143, 147),
    "boss_defeated": (193, 43, 25),
    "beacon_activated": (90, 246, 222),
    "tree_hit": (245, 114, 67),
}


@dataclass
class Effect:
    kind: str
    position: tuple
    lifetime: float
    age: float = 0.0
    yaw: float = 0.0
    meshes: tuple = ()
    detail: str = ""
    attachment: int | None = None
    velocity: tuple = (0.0, 0.0, 0.0)
    acceleration: tuple = (0.0, 0.0, 0.0)

    @property
    def progress(self):
        return min(1.0, self.age / self.lifetime)

    @property
    def opacity(self):
        return 1.0 - self.progress


@lru_cache(maxsize=16)
def mote(colour):
    return create_prism(0.09, 0.09, 0.09, colour, (0, 0, 0))


@lru_cache(maxsize=3)
def smoke(colour):
    return lathe([(0, 0.08), (0.12, 0.24), (0.34, 0.21), (0.45, 0)], colour, 6)


@lru_cache(maxsize=2)
def pulse(colour):
    vertices, faces = [], []
    for i in range(32):
        a = i * math.tau / 32
        vertices.extend(((math.sin(a) * r, 0.06, math.cos(a) * r) for r in (0.88, 1.0)))
    for i in range(32):
        a, b = i * 2, (i * 2 + 2) % 64
        faces.extend(((a, b, a + 1), (a + 1, b, b + 1)))
    return Mesh(vertices, faces, colour, (0, 0, 0))


class Effects:
    capacity = 48

    def __init__(self):
        self.live = deque(maxlen=self.capacity)
        self.emitted = Counter()

    def emit(
        self,
        kind,
        position,
        *,
        yaw=0.0,
        meshes=(),
        detail="",
        attachment=None,
        velocity=(0.0, 0.0, 0.0),
        acceleration=(0.0, 0.0, 0.0),
    ):
        effect = Effect(
            kind,
            tuple(position),
            LIFETIMES[kind],
            yaw=yaw,
            meshes=tuple(meshes),
            detail=detail,
            attachment=attachment,
            velocity=velocity,
            acceleration=acceleration,
        )
        self.live.append(effect)
        self.emitted[kind] += 1
        return effect

    def latest(self, kind):
        return next((e for e in reversed(self.live) if e.kind == kind), None)

    def update(self, dt, entities=None):
        dt = max(0.0, dt)
        for effect in self.live:
            effect.age += dt
            if effect.attachment is not None and entities is not None:
                target = entities.get(effect.attachment)
                if target is not None:
                    effect.position = target.position
        self.live = deque(
            (e for e in self.live if e.age < e.lifetime), maxlen=self.capacity
        )

    def draw(self, renderer, camera):
        # Tiny mesh confetti. No particle-engine side quest.
        from OpenGL import GL as gl

        gl.glDepthMask(gl.GL_FALSE)
        try:
            for effect in sorted(
                self.live,
                key=lambda e: math.dist(e.position, (camera.x, camera.y, camera.z)),
                reverse=True,
            ):
                if math.dist(effect.position, (camera.x, camera.y, camera.z)) > 65:
                    continue
                instances = self.instances(effect)
                if instances:
                    renderer.render_models(
                        camera, instances, alpha=effect.opacity * 0.8
                    )
        finally:
            gl.glDepthMask(gl.GL_TRUE)

    def instances(self, effect):
        t, age = effect.progress, effect.age
        x, y, z = (
            p + v * age + 0.5 * a * age * age
            for p, v, a in zip(effect.position, effect.velocity, effect.acceleration)
        )
        kind = effect.kind
        if kind in ("player_died", "crafted", "consumed"):
            return []
        colour = COLOURS[kind]
        instances = []
        if kind in ("enemy_defeated", "boss_defeated"):
            boss = kind == "boss_defeated"
            collapse = ease(min(1.0, age / (0.65 if boss else 0.45)))
            sink = (
                max(0.0, (age - 0.65) / 2.35) if boss else max(0.0, age - 0.45) * 0.28
            )
            pivot = (0, 0.35 if effect.detail == "dog" else 0.12, 0)
            rotations = (
                (((0, 0, 0), -0.85 * collapse, 0),)
                if boss
                else (
                    (pivot, 0, math.pi / 2),
                    (pivot, math.pi / 2 * collapse, -math.pi / 2),
                )
            )
            for mesh in effect.meshes:
                posed = MeshPose(mesh, rotations, (0, -sink * (4 if boss else 1), 0))
                instances.append((posed, x, y, z, effect.yaw))
            if boss:
                ring = MeshPose(pulse(colour), translation=(0, 0.02, 0))
                instances.append((ring, x, y, z, 0))
            if age < (0.45 if not boss else 0.3):
                return instances
        count = 12 if kind == "boss_defeated" else 8 if kind == "enemy_defeated" else 5
        for i in range(count):
            angle = i * 2.39996 + (age * 5 if kind == "boss_defeated" else 0)
            radius = (
                (0.5 + 1.4 * (1 - t))
                if kind == "boss_defeated"
                else (0.1 + t * (0.6 if kind == "enemy_defeated" else 0.4))
            )
            rise = (
                (1 - t) * (i % 4) * 0.7
                if kind == "boss_defeated"
                else 0.2 + age * 0.7 + (i % 3) * 0.1
            )
            particle = (
                smoke(colour)
                if kind in ("enemy_defeated", "boss_defeated", "tree_impact")
                else mote(colour)
            )
            instances.append(
                (
                    particle,
                    x + math.sin(angle) * radius,
                    y + rise,
                    z + math.cos(angle) * radius,
                    angle,
                )
            )
        if kind == "beacon_activated":
            scale = 1 + 4 * ease(t)
            ring = pulse(colour)
            expanded = Mesh(
                [(vx * scale, vy, vz * scale) for vx, vy, vz in ring.vertices],
                ring.faces,
                colour,
                (0, 0, 0),
            )
            beam = lathe([(0, 0.16), (5 * (1 - t) + 2, 0.06)], colour, 8)
            instances.extend(((expanded, x, y, z, 0), (beam, x, y, z, 0)))
        return instances
