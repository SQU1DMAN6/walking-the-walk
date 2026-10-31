import math
from dataclasses import dataclass, field

from engine import models
from engine.items import (
    DOG_COOLDOWN,
    DOG_DAMAGE,
    DOG_DETECTION,
    DOG_HEALTH,
    DOG_RANGE,
    DOG_RECOVERY,
    DOG_SPEED,
    DOG_WINDUP,
)
from engine.run_config import SPIDER


@dataclass
class Entity:
    kind: str
    x: float
    y: float
    z: float
    meshes: list = field(default_factory=list)
    yaw: float = 0.0
    visible: bool = True
    interactable: bool = False
    id: int = 0

    @property
    def position(self):
        return self.x, self.y, self.z

    def distance_to(self, x, z):
        return math.hypot(x - self.x, z - self.z)

    @property
    def render_meshes(self):
        return self.meshes

    @property
    def visual_height(self):
        return max(
            (
                vy + mesh.position[1]
                for mesh in self.meshes
                for _, vy, _ in mesh.vertices
            ),
            default=0.5,
        )


class EntityManager:
    def __init__(self):
        self._entities = {}
        # Don't recycle IDs and send old markers after new loot.
        self._next_id = 1

    def add(self, entity):
        if entity.id:
            raise ValueError("Entity already belongs to a manager")
        entity.id = self._next_id
        self._next_id += 1
        self._entities[entity.id] = entity
        return entity.id

    def get(self, entity_id):
        return self._entities.get(entity_id)

    def remove(self, entity_id):
        return self._entities.pop(entity_id, None)

    def all(self):
        return tuple(self._entities.values())

    def of_kind(self, *kinds):
        return tuple(e for e in self._entities.values() if e.kind in kinds)


class Dog(Entity):
    max_health = DOG_HEALTH
    damage = DOG_DAMAGE
    reach = DOG_RANGE
    detection = DOG_DETECTION
    windup_duration = DOG_WINDUP
    recovery = DOG_RECOVERY
    attack_cooldown = DOG_COOLDOWN
    default_speed = DOG_SPEED

    def __init__(self, position):
        super().__init__("dog", *position, meshes=models.dog())
        self.health = self.max_health
        self.state = "idle"
        self.cooldown = 0.0
        self.windup = 0.0
        self.radius = 0.35
        self.speed = self.default_speed
        self.attack_elapsed = self.windup_duration + self.recovery
        self.walk_phase = self.walk_blend = 0.0

    @property
    def render_meshes(self):
        return models.pose_dog(
            self.meshes, self.attack_elapsed, self.walk_phase, self.walk_blend
        )

    def update(self, dt, camera, world):

        if self.health <= 0:
            self.state = "defeated"
            return 0
        self.attack_elapsed = min(
            self.windup_duration + self.recovery, self.attack_elapsed + dt
        )
        self.walk_blend *= math.exp(-dt * 14)
        self.cooldown = max(0, self.cooldown - dt)
        distance = self.distance_to(camera.x, camera.z)
        if self.state == "idle":
            if distance > self.detection:
                return 0
            self.state = "chase"
        self.yaw = math.atan2(camera.x - self.x, camera.z - self.z)
        if self.state == "windup":
            self.windup -= dt
            if self.windup <= 0:
                self.state = "chase"
                self.cooldown = (
                    self.attack_cooldown
                    if self.kind == "dog"
                    else self.attack_cooldown - self.windup_duration
                )
                if distance <= self.reach and world.line_clear(
                    self.x, self.z, camera.x, camera.z, 0.1
                ):
                    return self.damage
            return 0
        if distance <= self.reach:
            if self.cooldown <= 0:
                self.state = "windup"
                self.windup = self.windup_duration
                self.attack_elapsed = 0.0
            return 0
        tx, tz = world.chase_target(self.x, self.z, camera.x, camera.z)
        dx, dz = tx - self.x, tz - self.z
        length = math.hypot(dx, dz)
        if length > 1e-6:
            step = min(self.speed * dt, length, max(0, distance - 0.8))
            previous = self.x, self.z
            self.x, self.z = world.move(
                self.x, self.z, dx / length * step, dz / length * step, self.radius
            )
            self.y = world.height(self.x, self.z)
            moved = math.dist(previous, (self.x, self.z))
            self.walk_phase += moved * 8
            if moved > 1e-6:
                self.walk_blend += 1 - math.exp(-dt * 14)
        return 0


class Spider(Dog):
    max_health = SPIDER["health"]
    damage = SPIDER["damage"]
    reach = SPIDER["range"]
    detection = SPIDER["detection"]
    windup_duration = SPIDER["windup"]
    recovery = SPIDER["recovery"]
    attack_cooldown = SPIDER["cooldown"]
    default_speed = SPIDER["speed"]

    def __init__(self, position):
        super().__init__(position)
        self.kind, self.meshes, self.radius = "spider", models.spider(), 0.45

    @property
    def render_meshes(self):
        return models.pose_spider(
            self.meshes, self.walk_phase, self.walk_blend, self.attack_elapsed
        )
