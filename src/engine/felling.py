import math
from dataclasses import dataclass, field

from engine.animation import ease, rotate_point
from engine.mesh import MeshPose

FALL_SECONDS = 1.8
TREE_DAMAGE = 99
TREE_MOB_DAMAGE = 100


def segment_distance_3d(point, a, b):
    delta = tuple(y - x for x, y in zip(a, b))
    length = sum(v * v for v in delta)
    t = (
        max(
            0.0, min(1.0, sum((p - x) * d for p, x, d in zip(point, a, delta)) / length)
        )
        if length
        else 0.0
    )
    return math.dist(point, tuple(x + t * d for x, d in zip(a, delta)))


@dataclass
class FallingTree:
    site: object
    direction: float
    reward_position: tuple
    age: float = 0.0
    hit: bool = False
    settled: bool = False
    overlapping: bool = False
    mob_hits: set = field(default_factory=set)

    @property
    def angle(self):
        return ease(self.age / FALL_SECONDS) * math.pi / 2

    @property
    def trunk_height(self):
        trunk = self.site.meshes[0]
        return max(
            v[1] + trunk.position[1] - self.site.position[1] for v in trunk.vertices
        )

    def endpoint(self, angle=None):
        offset = rotate_point(
            (0, self.trunk_height, 0),
            (0, 0, 0),
            (self.angle if angle is None else angle),
            self.direction,
        )
        return tuple(p + v for p, v in zip(self.site.position, offset))

    @property
    def trunk_radius(self):
        trunk = self.site.meshes[0]
        base = min(v[1] for v in trunk.vertices)
        return max(
            (
                math.hypot(
                    v[0] + trunk.position[0] - self.site.position[0],
                    v[2] + trunk.position[2] - self.site.position[2],
                )
                for v in trunk.vertices
                if v[1] <= base + 0.15
            ),
            default=0.2,
        )

    def intersects_body(self, feet, radius, height, angle):
        dx, dz = feet[0] - self.site.position[0], feet[2] - self.site.position[2]
        if dx * math.sin(self.direction) + dz * math.cos(self.direction) <= 0:
            return False
        # The stump isn't swinging at you. Retire its hitbox from this conversation.
        end = self.endpoint(angle)
        start = tuple(
            a + (b - a) * min(0.65 / self.trunk_height, 0.2)
            for a, b in zip(self.site.position, end)
        )
        return any(
            segment_distance_3d((feet[0], feet[1] + h, feet[2]), start, end)
            <= self.trunk_radius + radius
            for h in (min(radius, height * 0.4), height * 0.55, height)
        )

    def intersects_player(self, feet, camera, angle):
        return self.intersects_body(feet, camera.radius, camera.eye_height, angle)

    def environment_contact(self, world, angle, obstacles):
        end = self.endpoint(angle)
        length = self.trunk_height
        for i in range(2, math.ceil(length / 0.25) + 1):
            t = min(1.0, i * 0.25 / length)
            x, y, z = (a + (b - a) * t for a, b in zip(self.site.position, end))
            radius = self.trunk_radius * (1 - 0.6 * t)
            if y < world.height(x, z) + 0.02:
                return True
            for obstacle in obstacles:
                height = (
                    8.0
                    if obstacle.kind == "tree"
                    else 3.2
                    if obstacle.kind == "ridge"
                    else obstacle.radius * 1.2
                )
                if (
                    math.hypot(x - obstacle.x, z - obstacle.z)
                    < radius + obstacle.radius
                    and y - radius < world.height(obstacle.x, obstacle.z) + height
                ):
                    return True
        return False

    def meshes(self):
        # Yaw into fall space, tip, then yaw back: the base stays put.
        pivot = self.site.position
        return [
            MeshPose(
                mesh, ((pivot, 0, -self.direction), (pivot, self.angle, self.direction))
            )
            for mesh in self.site.meshes
        ]


class TreeFalls:
    capacity = 16

    def __init__(self):
        self.live = []
        self.previous_player = None
        self.previous_mobs = {}

    def start(self, site, camera, reward_position, world):
        if len(self.live) >= self.capacity:
            return False
        dx, dz = site.position[0] - camera.x, site.position[2] - camera.z
        direction = math.atan2(dx, dz) if math.hypot(dx, dz) > 1e-6 else camera.yaw
        self.live.append(FallingTree(site, direction, tuple(reward_position)))
        self.live[-1].overlapping = self.live[-1].intersects_player(
            (camera.x, camera.y - camera.eye_height, camera.z), camera, 0.0
        )
        if self.previous_player is None:
            self.previous_player = camera.x, camera.y - camera.eye_height, camera.z
        return True

    def update(self, dt, level):
        if dt <= 0:
            return
        camera, world = level.camera, level.world
        current = camera.x, camera.y - camera.eye_height, camera.z
        previous = self.previous_player or current
        mobs = (
            tuple(e for e in getattr(level, "hostiles", ()) if e.health > 0)
            if getattr(level, "is_survival", False)
            else ()
        )
        mob_positions = {e.id: e.position for e in mobs}
        finished = []
        for tree in self.live:
            old = tree.age
            tree.age = min(FALL_SECONDS, old + dt)
            candidates = [
                e
                for e in mobs
                if math.hypot(e.x - tree.site.position[0], e.z - tree.site.position[2])
                < tree.trunk_height + e.radius + 2
            ]
            mob_travel = max(
                (
                    math.dist(self.previous_mobs.get(e.id, e.position), e.position)
                    for e in candidates
                ),
                default=0.0,
            )
            # Substeps sweep both the trunk and moving player, including low FPS.
            steps = max(
                1,
                math.ceil((tree.age - old) / (1 / 240)),
                math.ceil(math.dist(previous, current) / 0.04),
                math.ceil(mob_travel / 0.04),
            )
            obstacles = tuple(
                o
                for o in world.obstacles
                if o != tree.site.obstacle
                and math.hypot(o.x - tree.site.position[0], o.z - tree.site.position[2])
                < tree.trunk_height + o.radius
            )
            for step in range(1, steps + 1):
                t = step / steps
                age = old + (tree.age - old) * t
                angle = ease(age / FALL_SECONDS) * math.pi / 2
                contact = angle > 0.06 and tree.environment_contact(
                    world, angle, obstacles
                )
                end = tree.endpoint(angle)
                feet = tuple(a + (b - a) * t for a, b in zip(previous, current))
                collided = tree.intersects_player(feet, camera, angle)
                entered = collided and not tree.overlapping
                tree.overlapping = collided
                if (
                    angle > 0.06
                    and age < FALL_SECONDS
                    and entered
                    and not tree.hit
                    and level.active
                ):
                    tree.hit = True
                    level.receive_damage(
                        TREE_DAMAGE, tree.site.position, "Falling tree"
                    )
                    level.effects.emit("tree_hit", feet)
                    level.notify("-99 health | Falling trunk. Timber means move.", 3)
                    if hasattr(level, "beacon_commit"):
                        level.beacon_commit = 0
                if level.active and angle > 0.06 and age < FALL_SECONDS:
                    for mob in candidates:
                        if mob.id in tree.mob_hits or mob.health <= 0:
                            continue
                        start = self.previous_mobs.get(mob.id, mob.position)
                        feet = tuple(
                            a + (b - a) * t for a, b in zip(start, mob.position)
                        )
                        if tree.intersects_body(
                            feet, mob.radius, mob.visual_height, angle
                        ):
                            tree.mob_hits.add(mob.id)
                            level.hit_by_tree(mob, TREE_MOB_DAMAGE)
                if contact:
                    tree.age = age
                    tree.settled = True
                    break
            if tree.age >= FALL_SECONDS or tree.settled:
                end = tree.endpoint()
                level.effects.emit("tree_impact", end)
                level.finish_tree_fall(tree)
                finished.append(tree)
        self.live = [tree for tree in self.live if tree not in finished]
        self.previous_player = current
        self.previous_mobs = mob_positions

    def instances(self):
        return [(mesh, 0, 0, 0, 0) for tree in self.live for mesh in tree.meshes()]
