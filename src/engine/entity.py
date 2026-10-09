from dataclasses import dataclass, field
import math
from engine import models
from engine.items import (DOG_SPEED, DOG_HEALTH, DOG_DAMAGE, DOG_RANGE,
                          DOG_DETECTION, DOG_WINDUP, DOG_COOLDOWN)


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
        return math.hypot(x-self.x, z-self.z)

    @property
    def visual_height(self):
        return max((vy+mesh.position[1] for mesh in self.meshes for _, vy, _ in mesh.vertices), default=.5)


class EntityManager:

    def __init__(self):
        self._entities = {}
        # Don't recycle IDs and send old markers after new loot.
        self._next_id = 1

    def add(self, entity):
        if entity.id:
            raise ValueError('Entity already belongs to a manager')
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
    def __init__(self, position):
        super().__init__('dog', *position, meshes=models.dog())
        self.health = DOG_HEALTH
        self.state = 'idle'
        self.cooldown = 0.0
        self.windup = 0.0
        self.radius = .35
        self.speed = DOG_SPEED

    def update(self, dt, camera, world):

        if self.health <= 0:
            self.state = 'defeated'
            return 0
        self.cooldown = max(0, self.cooldown-dt)
        distance = self.distance_to(camera.x, camera.z)
        if self.state == 'idle':
            if distance > DOG_DETECTION:
                return 0
            self.state = 'chase'
        self.yaw = math.atan2(camera.x-self.x, camera.z-self.z)
        if self.state == 'windup':
            self.windup -= dt
            if self.windup <= 0:
                self.state = 'chase'
                self.cooldown = DOG_COOLDOWN
                if distance <= DOG_RANGE and world.line_clear(self.x, self.z, camera.x, camera.z, .1):
                    return DOG_DAMAGE
            return 0
        if distance <= DOG_RANGE:
            if self.cooldown <= 0:
                self.state = 'windup'
                self.windup = DOG_WINDUP
            return 0
        tx, tz = world.chase_target(self.x, self.z, camera.x, camera.z)
        dx, dz = tx-self.x, tz-self.z
        length = math.hypot(dx, dz)
        if length > 1e-6:
            step = min(self.speed*dt, length, max(0, distance-.8))
            self.x, self.z = world.move(self.x, self.z, dx/length*step, dz/length*step, self.radius)
            self.y = world.height(self.x, self.z)
        return 0
