from dataclasses import dataclass
import secrets

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
    'Easy': Difficulty(1.5, 1, 1, 24, 2, 2.0, .10),
    'Medium': Difficulty(1.0, 2, 2, 16, 4, 1.3, .20),
    'Hard': Difficulty(.65, 3, 3, 10, 7, .7, .30),
}
# Width hint (m), primary-route distance (m), major forks.
LENGTHS = {'Short': (140, 400, 3), 'Normal': (180, 800, 5), 'Long': (240, 1500, 8)}
GENERATION_ATTEMPTS = 4
ROUTE_TOLERANCE = .05
ARENA_RADIUS = 16.0
ARENA_APPROACH = 28.0
RIDGE_RADIUS = 1.25
ROUTES = {'heading':.7,'step':(66.,92.),'spread':(38.,57.),'minimum_separation':16.,'ridge_spacing':1.65}
PERCEPTION = {'fov_degrees':160.,'attack_half_arc':65.,'coordination_gap':.24,'ambush_seconds':.65,'dog_detection':34.,'spider_detection':32.,'sense_interval':.12,
              'search_seconds':7.,'persistence':{'Easy':12.,'Medium':18.,'Hard':25.},
              'walk_noise':7.,'sprint_noise':22.,'fight_noise':24.,'chop_noise':30.,
              'dog_speed':4.6,'dog_reach':2.9,'windup_tracking':1.8,'recovery_speed':.65,'encounter_leash':96.}
VENOM = {'health':30,'speed':5.1,'detection':24.,'range':1.55,'damage':2,'windup':.24,
         'cooldown':.7,'recovery':.46,'tick_seconds':2.,'tick_damage':2,
         'threshold':{'Short':100.,'Normal':500.,'Long':500.},'spacing':36.,
         'spawn_interval':{'Easy':22.,'Medium':17.,'Hard':13.},
         'population':{'Easy':2,'Medium':3,'Hard':4},'water_stamina':60.}
BOSS = {'health':240,'detection':50.,'speed':3.2,'phase_speed':3.8,'radius':.85,'trigger':38.,'emerge':1.4,
        'leash':23.,'armor':.25,'phase_at':.5,
        'cleave':{'windup':.8,'active':.16,'recovery':1.25,'range':3.6,'damage':20,'arc':75.},
        'slam':{'windup':1.15,'active':.2,'recovery':1.6,'radius':3.4,'damage':25,'lead':.4}}


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

    @property
    def target_distance(self):
        return LENGTHS[self.length][1]


WEAPONS = {
    'spear': {'range': 3.5, 'damage': 25, 'stamina': 12, 'cooldown': .40, 'animation': .40},
    'axe': {'range': 2.3, 'damage': 32, 'stamina': 18, 'cooldown': .55, 'animation': .45},
}
SPIDER = {'health': 60, 'speed': PLAYER_SPEED*1.6, 'detection': 9.0, 'range': 1.35,
          'damage': 5, 'cooldown': .5, 'windup': .18, 'recovery': .22}
SURVIVAL_SPIDER = {**SPIDER,'speed':5.8,'detection':PERCEPTION['spider_detection'],'range':1.95,
                  'cooldown':.75,'windup':.30,'recovery':.45}
TREE_CHOPS = 3
TREE_LEAVES = 3
HEAL_RANGE = (20, 35)
SPAWN_CLEARANCE = 12.0
DAMAGE_GRACE = .20


class RunSeeds:
    def __init__(self,override=None):
        if override is not None and type(override) is not int:raise ValueError('Seed must be an integer')
        self.override,self.last = override,None

    def next(self):
        seed = self.override if self.override is not None else secrets.randbits(63)
        if self.override is None and seed==self.last:seed = (seed+1)%(1<<63)
        self.last = seed
        return seed
