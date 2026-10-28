from dataclasses import dataclass
import math

from engine.run_config import VENOM


@dataclass
class PoisonStatus:
    active: bool = False
    elapsed: float = 0.
    applications: int = 0
    ticks: int = 0

    def apply(self):
        first = not self.active
        if first:self.elapsed = 0.
        self.active = True
        self.applications += 1
        return first

    def cure(self):
        was_active = self.active
        self.active,self.elapsed = False,0.
        return was_active

    def update(self,dt):
        if not self.active:return 0
        self.elapsed += max(0,dt)
        count = math.floor((self.elapsed+1e-9)/VENOM['tick_seconds'])
        self.elapsed -= count*VENOM['tick_seconds']
        self.ticks += count
        return count*VENOM['tick_damage']
