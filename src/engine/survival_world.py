import math
import random

from engine.guidance import PathGuide
from engine.routes import SurvivalPaths
from engine.run_config import ARENA_RADIUS, VENOM
from engine.streaming import ForestStreaming, chunk_key


class SurvivalChunk(ForestStreaming):
    def __init__(self, seed, config):
        self.seed, self.config = seed, config
        self.paths = SurvivalPaths(seed, config)
        self.navigator = PathGuide(self.paths)
        self.arena = self.paths.arena
        self.ridge_index = {}
        for point in self.paths.ridges:
            self.ridge_index.setdefault(chunk_key(*point), []).append(point)
        self.spawn, self.beacon = (
            self.position(*self.paths.route[0]),
            self.position(*self.paths.route[-1]),
        )
        self.encounter = self.position(*self.paths.at(70))
        self.resources = self._resources()
        self.resource_index = {}
        for kind, pos in self.resources:
            self.resource_index.setdefault(chunk_key(pos[0], pos[2]), []).append(
                (kind, pos)
            )
        self.signs = [self.position(*line[4]) for line in self.paths.shortcuts]
        self.hostile_sites = self._hostiles()
        self.spawn_access = {}
        points = [p for line in self.paths.shortcuts for p in line]
        for kind, pos, _ in self.hostile_sites:
            if kind != "spider":
                continue
            a = pos[0], pos[2]
            b = min(points, key=lambda p: math.dist(a, p))
            for ix in range(
                math.floor((min(a[0], b[0]) - 3) / 32),
                math.floor((max(a[0], b[0]) + 3) / 32) + 1,
            ):
                for iz in range(
                    math.floor((min(a[1], b[1]) - 3) / 32),
                    math.floor((max(a[1], b[1]) + 3) / 32) + 1,
                ):
                    self.spawn_access.setdefault((ix, iz), []).append((a, b))
        self._init_streaming()
        self.validation = self.validate()

    def _resources(self):
        rng = random.Random(self.seed + 831)
        result = []

        def add(kind, distance):
            x, z = self.paths.at(distance)
            before, after = self.paths.at(distance - 0.3), self.paths.at(distance + 0.3)
            dx, dz = after[0] - before[0], after[1] - before[1]
            size = max(0.01, math.hypot(dx, dz))
            side = rng.choice((-1, 1)) * rng.uniform(1.25, 1.65)
            result.append(
                (kind, self.position(x + dz / size * side, z - dx / size * side))
            )

        # Starter mats get a guaranteed invite; RNG doesn't gate basic gear.
        add("can", rng.uniform(3, 5))
        add("bottle", rng.uniform(6, 8))
        for i in range(6):
            add("stick", 9 + i * 4 + rng.uniform(-0.5, 0.5))
            add("rock", 11 + i * 4 + rng.uniform(-0.5, 0.5))
        length = self.paths.lengths[-1]
        for kind, per100 in (("can", 2), ("bottle", 2), ("stick", 5), ("rock", 3)):
            count = max(1, round(length / 100 * per100 * self.config.balance.resources))
            for i in range(count):
                add(kind, (i + rng.uniform(0.25, 0.75)) * length / count)
        for i, dead in enumerate(self.paths.dead_ends):
            if i % 2 == 0:
                result.append(("can", self.position(*dead[-1])))
        # A trail cache before venom territory; the boss isn't a gear lottery.
        for distance in (length - 125, length - 70, length - 48):
            add("bottle", max(40, distance))
        for kind in ("can", "can", "stick", "rock"):
            add(kind, length - 55 - rng.uniform(0, 7))
        return result

    def is_clearing(self, x, z):
        return (
            math.dist((x, z), self.arena) < ARENA_RADIUS
            or math.dist((x, z), self.paths.route[0]) < 7
        )

    def _hostiles(self):
        rng = random.Random(self.seed + 1223)
        sites = []
        balance = self.config.balance
        for zone, line in enumerate(self.paths.shortcuts):
            count = min(5, balance.shortcut_group + zone // 3)
            for member in range(count):
                t = 0.40 + member * 0.075
                x, z = line[min(len(line) - 5, round(t * (len(line) - 1)))]
                before, after = (
                    line[max(0, round(t * (len(line) - 1)) - 2)],
                    line[min(len(line) - 1, round(t * (len(line) - 1)) + 2)],
                )
                dx, dz = after[0] - before[0], after[1] - before[1]
                norm = max(0.01, math.hypot(dx, dz))
                side = (-1 if member % 2 else 1) * rng.uniform(4.2, 6.0)
                pos = self.position(x + dz / norm * side, z - dx / norm * side)
                if (
                    math.dist((pos[0], pos[2]), self.paths.route[0]) > 38
                    and math.dist((pos[0], pos[2]), self.arena) > 24
                ):
                    sites.append(("spider", pos, "shortcut"))
            # Venom opportunities are finite, spaced and activated by remaining distance.
            for t in (0.55, 0.82):
                x, z = line[round(t * (len(line) - 1))]
                if (
                    math.dist((x, z), self.paths.route[-1])
                    <= VENOM["threshold"][self.config.length]
                    and math.dist((x, z), self.arena) > 23
                    and all(
                        k != "viper"
                        or math.dist((p[0], p[2]), (x, z)) >= VENOM["spacing"]
                        for k, p, _ in sites
                    )
                ):
                    sites.append(("viper", self.position(x, z), "shortcut"))
        count = max(1, round(self.paths.lengths[-1] / 230)) * balance.safe_dogs
        for i in range(count):
            distance = (
                48
                + (i + rng.uniform(0.1, 0.8)) * (self.paths.lengths[-1] - 110) / count
            )
            sites.append(("dog", self.position(*self.paths.at(distance)), "detour"))
        return sites

    def validate(self):
        route, _ = self.navigator.route(self.paths.route[0], self.paths.route[-1])
        if not route or route[-1] != self.paths.route[-1]:
            raise ValueError("Disconnected route graph")
        for safe, short in zip(self.paths.detours, self.paths.shortcuts):
            if safe[0] != short[0] or safe[-1] != short[-1]:
                raise ValueError("Shortcut lost its junction")
            if sum(math.dist(a, b) for a, b in zip(short, short[1:])) >= 0.95 * sum(
                math.dist(a, b) for a, b in zip(safe, safe[1:])
            ):
                raise ValueError("Shortcut is not shorter")
        for x, z in self.paths.route[::3]:
            if any(
                abs(self.height(x + dx, z + dz) - self.height(x, z)) > 1.12
                for dx, dz in ((1, 0), (0, 1))
            ):
                raise ValueError("Unwalkable route slope")
        self.paths.validate()
        surface = sum(
            math.dist(self.position(*a), self.position(*b))
            for a, b in zip(self.paths.route, self.paths.route[1:])
        )
        return dict(
            distance_metric="horizontal primary centreline including arena approach",
            target_distance=self.config.target_distance,
            surface_route_length=round(surface, 2),
            arena=self.arena,
            route_attempts=self.paths.attempts,
            fallback=self.paths.fallback,
            physical_ridges=len(self.paths.ridges),
            connected=True,
            route_samples=len(self.paths.route),
            route_length=round(self.paths.lengths[-1], 2),
            destination_distance=round(math.dist(self.spawn, self.beacon), 2),
            shortcuts=len(self.paths.shortcuts),
            dead_ends=len(self.paths.dead_ends),
            resources=len(self.resources),
            hostiles=len(self.hostile_sites),
            initial_chunks=len(self.chunks),
            obstacles=len(self.obstacles),
        )
