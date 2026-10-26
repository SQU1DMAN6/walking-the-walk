from collections import deque
from dataclasses import dataclass
import math

from engine.entity import Dog, Spider
from engine.run_config import SURVIVAL_SPIDER


@dataclass(frozen=True)
class SoundEvent:
    serial: int
    position: tuple
    kind: str
    radius: float
    expires: float


class Senses:
    fov = math.cos(math.radians(65))

    def setup_senses(self):
        self.home = self.x,self.z
        self.last_known = None
        self.memory = self.sense_timer = self.state_time = 0.0
        self.last_sound = 0
        self.patrol_side = 1
        self.state = 'patrol' if self.kind == 'dog' else 'concealed'
        self.ambush_used = False
        self.ambush_height = 0.0
        self.alert_duration = .4
        self.transitions = deque(maxlen=24)
        self.sees_player = False

    def transition(self,state):
        if self.state != state:
            self.transitions.append((self.state,state))
            self.state,self.state_time = state,0.0

    def perceive(self,camera,world):
        dx,dz = camera.x-self.x,camera.z-self.z
        distance = max(.001,math.hypot(dx,dz))
        facing = (dx*math.sin(self.yaw)+dz*math.cos(self.yaw))/distance
        fov = -.15 if self.last_known and self.memory<2 else self.fov
        clear = distance<=self.detection and world.vision_clear((self.x,self.y+.8,self.z),(camera.x,camera.y-.3,camera.z))
        self.sees_player = distance<=self.detection and facing>=fov and clear
        if self.kind == 'spider' and distance<2.8 and clear:
            self.sees_player = True
        if self.sees_player:
            self.last_known,self.memory = (camera.x,camera.z),0.0
            if self.state in ('patrol','idle','investigate','search','suspicious','reposition'):
                self.transition('alert')
        events = [s for s in world.sounds if s.serial>self.last_sound and s.expires>=world.clock]
        for sound in events:
            self.last_sound = max(self.last_sound,sound.serial)
            if self.distance_to(*sound.position)<=sound.radius and not self.sees_player:
                if self.state in ('patrol','idle','search','investigate','suspicious','concealed'):
                    self.last_known,self.memory = sound.position,0.0
                    if self.state != 'concealed':
                        self.transition('investigate')

    def _move(self,dt,target,world,camera,speed=None):
        tx,tz = world.chase_target(self.x,self.z,*target)
        dx,dz = tx-self.x,tz-self.z
        length = math.hypot(dx,dz)
        if length<.05:
            return
        yaw = math.atan2(dx,dz)
        delta = (yaw-self.yaw+math.pi)%math.tau-math.pi
        self.yaw += max(-dt*5,min(dt*5,delta))
        step = min(length,(self.speed if speed is None else speed)*dt)
        old = self.x,self.z
        nx,nz = world.move(self.x,self.z,dx/length*step,dz/length*step,self.radius)
        bodies = [(camera.x,camera.z,camera.radius)]+[(e.x,e.z,e.radius) for e in world.actors
                                                   if e is not self and e.state not in ('concealed','ambush')]
        for x,z,radius in bodies:
            minimum = self.radius+radius+.08
            before,after = math.hypot(self.x-x,self.z-z),math.hypot(nx-x,nz-z)
            if after<minimum and after<before:
                # Slide around bodies; conga lines have had their moment.
                alternatives = [(nx,self.z),(self.x,nz)]
                nx,nz = next(((a,b) for a,b in alternatives if math.hypot(a-x,b-z)>=min(minimum,before)
                              and world.is_walkable(a,b,self.radius)),(self.x,self.z))
        if any(math.hypot(nx-x,nz-z)<self.radius+r+.08 and
               math.hypot(nx-x,nz-z)<math.hypot(self.x-x,self.z-z) for x,z,r in bodies):
            nx,nz = self.x,self.z
        self.x,self.z = nx,nz
        self.y = world.height(nx,nz)
        moved = math.dist(old,(nx,nz))
        self.walk_phase += moved*8
        if moved>1e-6:
            self.walk_blend += 1-math.exp(-dt*14)
        elif self.state_time>1 and self.state in ('pursue','flank'):
            self.transition('reposition')

    def update(self,dt,camera,world):
        if self.health<=0:
            self.transition('defeated')
            return 0
        self.state_time += dt
        self.memory += dt
        self.sense_timer -= dt
        self.cooldown = max(0,self.cooldown-dt)
        self.attack_elapsed = min(self.windup_duration+self.recovery,self.attack_elapsed+dt)
        self.walk_blend *= math.exp(-dt*14)
        if self.sense_timer<=0:
            self.sense_timer = .12
            self.perceive(camera,world)
        distance = self.distance_to(camera.x,camera.z)
        if self.state == 'concealed':
            self.y = world.height(self.x,self.z)+self.ambush_height
            if self.last_known is not None or distance<8:
                self.ambush_used = True
                self.transition('ambush')
                world.ambush_cue = self.position
            return 0
        if self.state == 'ambush':
            t = min(1,self.state_time/.65)
            self.y = world.height(self.x,self.z)+self.ambush_height*(1-t*t)
            if t>=1:
                minimum = self.radius+camera.radius+.15
                if distance<minimum:
                    landing = [(self.x+math.sin(a)*minimum,self.z+math.cos(a)*minimum)
                               for a in (i*math.tau/8 for i in range(8))]
                    safe = next(((x,z) for x,z in landing if math.hypot(x-camera.x,z-camera.z)>=minimum
                                 and world.is_walkable(x,z,self.radius)
                                 and world.line_clear(self.x,self.z,x,z,self.radius)
                                 and all(e is self or e.distance_to(x,z)>e.radius+self.radius+.1 for e in world.actors)),None)
                    if safe is None:
                        return 0
                    self.x,self.z = safe
                    self.y = world.height(*safe)
                self.transition('alert')
                self.last_known = camera.x,camera.z
            return 0
        if self.state == 'attack':
            self.windup -= dt
            if self.windup<=1e-6:
                self.transition('recover')
                self.cooldown = max(self.recovery,self.attack_cooldown-self.windup_duration)
                facing = ((camera.x-self.x)*math.sin(self.yaw)+(camera.z-self.z)*math.cos(self.yaw))/max(.01,distance)
                if distance<=self.reach and facing>.5 and world.line_clear(self.x,self.z,camera.x,camera.z,.1):
                    return self.damage
            return 0
        if self.state == 'recover':
            if self.cooldown<=1e-6:
                self.transition('pursue' if self.memory<world.ai_persistence else 'search')
            return 0
        if self.state == 'alert':
            self.yaw = math.atan2(camera.x-self.x,camera.z-self.z)
            if self.state_time>=self.alert_duration:
                self.transition('pursue')
            return 0
        if self.state in ('pursue','flank','reposition'):
            if self.memory>world.ai_persistence:
                self.transition('search')
                return 0
            if distance<=self.reach and self.memory<.4 and self.cooldown<=0:
                attacking = sum(e is not self and e.state=='attack' and e.distance_to(self.x,self.z)<8 for e in world.actors)
                if attacking<getattr(world,'max_attackers',2) and world.clock>=world.next_attack and world.line_clear(self.x,self.z,camera.x,camera.z,.1):
                    self.yaw = math.atan2(camera.x-self.x,camera.z-self.z)
                    self.transition('attack')
                    self.windup = self.windup_duration
                    self.attack_elapsed = 0
                    world.next_attack = world.clock+.24
                return 0
            target = self.last_known or self.home
            if self.kind=='spider' and self.memory<.4 and distance>2.5:
                peers = [e for e in world.actors if e.kind=='spider' and e is not self and e.distance_to(self.x,self.z)<10]
                if peers:
                    angle = (self.id%6)*math.tau/6+world.clock*.1
                    radius = min(3,distance*.3)
                    target = (target[0]+math.sin(angle)*radius,target[1]+math.cos(angle)*radius)
                    self.transition('flank')
                elif distance>4:
                    vx,vz = world.player_velocity
                    target = target[0]+max(-2,min(2,vx*.4)),target[1]+max(-2,min(2,vz*.4))
            if self.state=='reposition':
                angle = self.yaw+math.pi/2*(1 if self.id%2 else -1)
                target = self.x+math.sin(angle)*2,self.z+math.cos(angle)*2
                if self.state_time>.7:
                    self.transition('pursue')
            self._move(dt,target,world,camera)
            return 0
        if self.state == 'investigate':
            self._move(dt,self.last_known,world,camera,self.speed*.7)
            if self.distance_to(*self.last_known)<1 or self.state_time>6:
                self.transition('search')
        elif self.state == 'search':
            self.yaw += dt*1.5
            if self.state_time>3:
                self.last_known = None
                self.transition('patrol')
        elif self.state in ('patrol','idle'):
            target = self.home[0]+self.patrol_side*3,self.home[1]+self.patrol_side*2
            if self.distance_to(*target)<.6 or self.state_time>5:
                self.patrol_side *= -1
                self.state_time = 0
            self._move(dt,target,world,camera,self.speed*.35)
        return 0

    def snapshot(self):
        names = ('kind','x','y','z','yaw','health','state','cooldown','windup','attack_elapsed','home','last_known',
                 'memory','state_time','patrol_side','ambush_used','ambush_height','sees_player','last_sound')
        return {name:getattr(self,name) for name in names}


class WildDog(Senses,Dog):
    def __init__(self,position):
        super().__init__(position)
        self.setup_senses()


class AmbushSpider(Senses,Spider):
    default_speed = SURVIVAL_SPIDER['speed']
    detection = SURVIVAL_SPIDER['detection']
    windup_duration = SURVIVAL_SPIDER['windup']
    attack_cooldown = SURVIVAL_SPIDER['cooldown']
    recovery = SURVIVAL_SPIDER['recovery']

    def __init__(self,position):
        super().__init__(position)
        self.setup_senses()

    @property
    def render_meshes(self):
        from engine import models
        return models.pose_spider(self.meshes,self.walk_phase,self.walk_blend,self.attack_elapsed)
