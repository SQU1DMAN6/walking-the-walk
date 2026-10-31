import math
from enum import Enum

from engine import models
from engine.combat import attack_hits, turn_towards
from engine.entity import Entity
from engine.markers import create_ring
from engine.perception import Senses
from engine.run_config import ARENA_RADIUS, BOSS
from engine.streaming import chunk_key


class BossStage(Enum):
    DORMANT = "dormant"
    EMERGING = "emerging"
    ACTIVE = "active"
    DEFEATED = "defeated"


class Demon(Senses, Entity):
    max_health = BOSS["health"]
    radius = BOSS["radius"]
    detection = BOSS["detection"]

    def __init__(self, position):
        Entity.__init__(self, "boss", *position, meshes=models.demon())
        self.health, self.speed = self.max_health, BOSS["speed"]
        self.walk_phase = self.walk_blend = self.cooldown = 0.0
        self.setup_senses()
        self.state = "dormant"
        self.encounter = BossStage.DORMANT
        self.pattern_index, self.phase = 0, 1
        self.telegraph = None
        self.attack_center = self.home
        self.hit_resolved = False
        self.visible = False
        self.events = []

    @property
    def visual_height(self):
        return 3.8

    @property
    def render_meshes(self):
        return models.pose_demon(
            self.meshes, self.state, self.state_time, self.walk_phase, self.walk_blend
        )

    def receive_hit(self, damage):
        if self.encounter != BossStage.ACTIVE:
            return 0
        amount = (
            damage if self.state == "recover" else math.ceil(damage * BOSS["armor"])
        )
        amount = min(self.health, amount)
        self.health -= amount
        if self.health <= 0:
            self.encounter = BossStage.DEFEATED
            self.visible = False
            self.transition("defeated")
            self.telegraph = None
            self.events.append("defeated")
        return amount

    def _begin(self, pattern, camera, world):
        self.transition(pattern)
        self.hit_resolved = False
        self.yaw = math.atan2(camera.x - self.x, camera.z - self.z)
        self.attack_heading = self.yaw
        if pattern == "slam":
            vx, vz = world.player_velocity
            dx, dz = vx * BOSS["slam"]["lead"], vz * BOSS["slam"]["lead"]
            scale = min(1, 2 / max(0.001, math.hypot(dx, dz)))
            center = camera.x + dx * scale, camera.z + dz * scale
            if math.dist(center, self.home) > BOSS["leash"]:
                center = self.home
            self.attack_center = center
            location = center[0], world.height(*center), center[1]
            mesh = create_ring(
                location, world.height, radius=BOSS["slam"]["radius"], thickness=0.24
            )
            mesh.colour = (255, 83, 45)
            self.telegraph = location, [mesh]
        self.events.append(pattern)
        world.next_attack = max(
            world.next_attack, world.clock + BOSS[pattern]["windup"] + 0.2
        )

    def update(self, dt, camera, world):
        if self.encounter == BossStage.DEFEATED:
            return 0
        if hasattr(world, "chunks") and chunk_key(self.x, self.z) not in world.chunks:
            return 0
        self.state_time += dt
        self.walk_blend *= math.exp(-dt * 14)
        distance = self.distance_to(camera.x, camera.z)
        if self.encounter == BossStage.DORMANT:
            if distance <= BOSS["trigger"]:
                if distance < 12:
                    safe = next(
                        (
                            (
                                self.home[0] + math.sin(a) * 13,
                                self.home[1] + math.cos(a) * 13,
                            )
                            for a in (i * math.tau / 8 for i in range(8))
                            if world.is_walkable(
                                self.home[0] + math.sin(a) * 13,
                                self.home[1] + math.cos(a) * 13,
                                self.radius,
                            )
                            and math.hypot(
                                self.home[0] + math.sin(a) * 13 - camera.x,
                                self.home[1] + math.cos(a) * 13 - camera.z,
                            )
                            >= 12
                        ),
                        None,
                    )
                    if safe is None:
                        return 0
                    self.x, self.z = safe
                self.encounter = BossStage.EMERGING
                self.transition("emerging")
                self.visible = True
                self.events.append("emerging")
            return 0
        if self.encounter == BossStage.EMERGING:
            t = min(1, self.state_time / BOSS["emerge"])
            self.y = world.height(self.x, self.z) - 3 * (1 - t * t * (3 - 2 * t))
            if t >= 1:
                self.encounter = BossStage.ACTIVE
                self.transition("pursue")
            return 0
        phase = 2 if self.health <= self.max_health * BOSS["phase_at"] else 1
        if phase != self.phase:
            self.phase = phase
            self.meshes = models.demon(phase)
            self.events.append("phase_two")
        self.speed = BOSS["phase_speed"] if self.phase == 2 else BOSS["speed"]
        if math.dist((camera.x, camera.z), self.home) > BOSS["leash"] + 12:
            self.telegraph = None
            self.transition("return")
            self._move(dt, self.home, world, camera)
            return 0
        if self.state in ("cleave", "slam"):
            pattern = BOSS[self.state]
            if self.state == "cleave" and self.state_time < pattern["windup"] * 0.5:
                self.attack_heading = turn_towards(
                    self.attack_heading,
                    math.atan2(camera.x - self.x, camera.z - self.z),
                    0.8,
                    dt,
                )
                self.yaw = self.attack_heading
                self._nav_timer = 0
                self._move(
                    dt,
                    (self.x + math.sin(self.yaw) * 2, self.z + math.cos(self.yaw) * 2),
                    world,
                    camera,
                    self.speed * 0.45,
                    0,
                )
            if self.state_time + 1e-9 >= pattern["windup"] and not self.hit_resolved:
                self.hit_resolved = True
                if self.state == "cleave":
                    hit = attack_hits(
                        self, camera, world, pattern["range"], pattern["arc"], 3.0
                    )
                else:
                    hit = (
                        math.dist((camera.x, camera.z), self.attack_center)
                        <= pattern["radius"]
                        and abs(
                            camera.y
                            - camera.eye_height
                            - world.height(*self.attack_center)
                        )
                        < 3
                        and world.line_clear(self.x, self.z, camera.x, camera.z, 0.1)
                    )
                if hit:
                    return pattern["damage"]
            if self.state_time >= pattern["windup"] + pattern["active"]:
                self.recovery_duration = pattern["recovery"]
                self.transition("recover")
                self.telegraph = None
            return 0
        if self.state == "recover":
            if self.state_time >= self.recovery_duration:
                self.transition("pursue")
            return 0
        if self.state == "reposition":
            angle = self.yaw + math.pi / 2
            self._move(
                dt,
                (self.x + math.sin(angle) * 2, self.z + math.cos(angle) * 2),
                world,
                camera,
            )
            if self.state_time > 0.7:
                self.transition("pursue")
            return 0
        if (
            distance < 7
            and world.clock >= world.next_attack
            and world.line_clear(self.x, self.z, camera.x, camera.z, 0.2)
        ):
            pattern = "slam" if self.pattern_index % 2 or distance > 4 else "cleave"
            self.pattern_index += 1
            self._begin(pattern, camera, world)
        else:
            target = camera.x, camera.z
            if math.dist(target, self.home) > BOSS["leash"]:
                dx, dz = target[0] - self.home[0], target[1] - self.home[1]
                scale = BOSS["leash"] / max(0.001, math.hypot(dx, dz))
                target = self.home[0] + dx * scale, self.home[1] + dz * scale
            self.transition("pursue") if self.state == "return" else None
            self._move(dt, target, world, camera)
        return 0
