from dataclasses import dataclass

from engine.items import PLAYER_SPEED
from engine.run_recipes import BANDAGE_LEAVES


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
    'Easy': Difficulty(1.5, 1, 1, 24, 2, 2.0, .10),
    'Medium': Difficulty(1.0, 2, 2, 16, 4, 1.3, .20),
    'Hard': Difficulty(.65, 3, 3, 10, 7, .7, .30),
}
LENGTHS = {'Short': (64, 96, 2), 'Normal': (80, 160, 3), 'Long': (96, 224, 4)}


@dataclass(frozen=True)
class RunConfig:
    difficulty: str = 'Medium'
    length: str = 'Normal'

    def __post_init__(self):
        if self.difficulty not in DIFFICULTIES or self.length not in LENGTHS:
            raise ValueError('Choose a supported difficulty and world length')

    @property
    def balance(self):
        return DIFFICULTIES[self.difficulty]


WEAPONS = {
    'spear': {'range': 3.5, 'damage': 25, 'stamina': 12, 'cooldown': .40, 'animation': .40},
    'axe': {'range': 2.3, 'damage': 32, 'stamina': 18, 'cooldown': .55, 'animation': .45},
}
SPIDER = {'health': 60, 'speed': PLAYER_SPEED*1.35, 'detection': 9.0, 'range': 1.35,
          'damage': 5, 'cooldown': .5, 'windup': .18, 'recovery': .22}
TREE_CHOPS = 3
TREE_LEAVES = 3
HEAL_RANGE = (20, 35)
SPAWN_CLEARANCE = 12.0
DAMAGE_GRACE = .20
