import secrets
from dataclasses import dataclass

from engine.items import PLAYER_SPEED


@dataclass(frozen=True)
class Difficulty:
    resources: float
    shortcut_group: int
    safe_dogs: int
    reinforcement_interval: float
    reinforcement_limit: int
    north_exponent: float
    aggression_gain: float


DIFFICULTIES = {
    "Easy": Difficulty(1.5, 1, 1, 24, 2, 2.0, 0.10),
    "Medium": Difficulty(1.0, 2, 2, 16, 4, 1.3, 0.20),
    "Hard": Difficulty(0.65, 3, 3, 10, 7, 0.7, 0.30),
}
# Width hint (m), primary-route distance (m), major forks.
LENGTHS = {"Short": (140, 400, 3), "Normal": (180, 800, 5), "Long": (240, 1500, 8)}
GENERATION_ATTEMPTS = 4
ROUTE_TOLERANCE = 0.05
ARENA_RADIUS = 16.0
ARENA_APPROACH = 28.0
RIDGE_RADIUS = 1.25
ROUTES = {
    "heading": 0.7,
    "step": (66.0, 92.0),
    "spread": (38.0, 57.0),
    "minimum_separation": 16.0,
    "ridge_spacing": 1.65,
}
PERCEPTION = {
    "fov_degrees": 160.0,
    "attack_half_arc": 65.0,
    "coordination_gap": 0.24,
    "ambush_seconds": 0.65,
    "dog_detection": 34.0,
    "spider_detection": 32.0,
    "sense_interval": 0.12,
    "search_seconds": 7.0,
    "persistence": {"Easy": 12.0, "Medium": 18.0, "Hard": 25.0},
    "walk_noise": 7.0,
    "sprint_noise": 22.0,
    "fight_noise": 24.0,
    "chop_noise": 30.0,
    "dog_speed": 4.6,
    "dog_reach": 2.9,
    "windup_tracking": 1.8,
    "recovery_speed": 0.65,
    "encounter_leash": 96.0,
}
VENOM = {
    "health": 30,
    "speed": 5.1,
    "detection": 24.0,
    "range": 1.55,
    "damage": 2,
    "windup": 0.24,
    "cooldown": 0.7,
    "recovery": 0.46,
    "tick_seconds": 2.0,
    "tick_damage": 2,
    "threshold": {"Short": 100.0, "Normal": 500.0, "Long": 500.0},
    "spacing": 36.0,
    "spawn_interval": {"Easy": 22.0, "Medium": 17.0, "Hard": 13.0},
    "population": {"Easy": 2, "Medium": 3, "Hard": 4},
    "water_stamina": 75.0,
}
BOSS = {
    "health": 240,
    "detection": 100.0,
    "speed": 3.2,
    "phase_speed": 3.8,
    "radius": 0.85,
    "trigger": 38.0,
    "emerge": 1.4,
    "leash": 23.0,
    "armor": 0.25,
    "phase_at": 0.5,
    "cleave": {
        "windup": 0.8,
        "active": 0.16,
        "recovery": 1.25,
        "range": 2.5,
        "damage": 20,
        "arc": 75.0,
    },
    "slam": {
        "windup": 1.5,
        "active": 0.2,
        "recovery": 1.6,
        "radius": 4.4,
        "damage": 25,
        "lead": 0.4,
    },
    "spin": {
        "windup": 1.1,
        "active": 0.3,
        "recovery": 0.85,
        "radius": 1,
        "damage": 34,
    },
    "charge": {
        "windup": 0.85,
        "active": 0.8,
        "recovery": 1.35,
        "range": 5.7,
        "arc": 5.0,
        "speed": 13.0,
        "damage": 40,
    },
}


@dataclass(frozen=True)
class RunConfig:
    difficulty: str = "Medium"
    length: str = "Normal"

    def __post_init__(self):
        if self.difficulty not in DIFFICULTIES or self.length not in LENGTHS:
            raise ValueError("Choose a supported difficulty and world length")

    @property
    def balance(self):
        return DIFFICULTIES[self.difficulty]

    @property
    def target_distance(self):
        return LENGTHS[self.length][1]


WEAPONS = {
    "spear": {
        "range": 3.5,
        "damage": 25,
        "stamina": 0,
        "cooldown": 0.40,
        "animation": 0.40,
    },
    "axe": {
        "range": 2.3,
        "damage": 32,
        "stamina": 0,
        "cooldown": 0.55,
        "animation": 0.45,
    },
}
HEAVY_ATTACK = {"damage": 60, "stamina": 30, "cooldown": 1.2, "animation": 0.7}
SPIDER = {
    "health": 60,
    "speed": PLAYER_SPEED * 1.6,
    "detection": 9.0,
    "range": 1.35,
    "damage": 5,
    "cooldown": 0.5,
    "windup": 0.18,
    "recovery": 0.22,
}
SURVIVAL_SPIDER = {
    **SPIDER,
    "speed": 5.8,
    "detection": PERCEPTION["spider_detection"],
    "range": 1.95,
    "cooldown": 0.75,
    "windup": 0.30,
    "recovery": 0.45,
}
TREE_CHOPS = 4
TREE_LEAVES = 4
HEAL_RANGE = (20, 35)
SPAWN_CLEARANCE = 12.0
DAMAGE_GRACE = 0.20


class RunSeeds:
    def __init__(self, override=None):
        if override is not None and type(override) is not int:
            raise ValueError("Seed must be an integer")
        self.override, self.last = override, None

    def next(self):
        seed = self.override if self.override is not None else secrets.randbits(63)
        if self.override is None and seed == self.last:
            seed = (seed + 1) % (1 << 63)
        self.last = seed
        return seed
