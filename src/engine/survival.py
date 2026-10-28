import math
import random
from collections import deque

from engine import models
from engine.entity import Entity
from engine.perception import WildDog as Dog, AmbushSpider as Spider, Viper, SoundEvent
from engine.status import PoisonStatus
from engine.encounters import Demon, BossStage
from engine.inventory import Inventory
from engine.items import ITEMS, RECIPES, RUN_RECIPE_ORDER, HEAL_AMOUNT, USE_DURATION, CONSUMED_CONTAINER
from engine.level1 import Level1, Stage, INTERACTION_RANGE
from engine.markers import ObjectiveMarker
from engine.prompts import WorldPrompt
from engine.run_config import (RunConfig, WEAPONS, TREE_CHOPS, TREE_LEAVES, HEAL_RANGE,
                               SPAWN_CLEARANCE, DAMAGE_GRACE, PERCEPTION, VENOM, RunSeeds)
from engine.survival_world import SurvivalChunk
from engine.streaming import chunk_key


LOOT = {'can': {'food': 1}, 'bottle': {'water': 1},
        'stick': {'stick': 1}, 'rock': {'rock': 1}, 'leaves': {'leaves': TREE_LEAVES}}
HOSTILE_TYPES = {'dog':Dog,'spider':Spider,'viper':Viper}


class RunTree(Entity):
    def __init__(self, site):
        super().__init__('tree', *site.position, interactable=True)
        self.site, self.chops = site, 0

    @property
    def render_meshes(self):
        return ()

    @property
    def visual_height(self):
        return 1.1


class SurvivalRun(Level1):
    is_survival = True
    recipes = RUN_RECIPE_ORDER

    @property
    def active(self):
        return self.state not in (Stage.DEAD,Stage.COMPLETE) and self.camera.health>0

    def __init__(self, camera, seed=None, config=None):
        self._seed_override = seed
        self._seeds = RunSeeds(seed)
        self.config, self.seed = config or RunConfig(), self._seeds.next()
        self._ready = False
        super().__init__(camera, self.seed, SurvivalChunk(self.seed, self.config))
        self.axe_meshes = models.axe()
        self.held_props.update({'leaves': models.held_prop(models.leaves()),
                                'bandage': models.held_prop(models.bandage())})

    def reset(self):
        if self._ready:
            self.world.close()
            if self._seed_override is None:self.seed = self._seeds.next()
            self.world = SurvivalChunk(self.seed, self.config)
        super().reset()
        self._ready = True
        self.state = Stage.BEACON
        self.camera.health = self.camera.max_health
        self.camera.survival_stamina = True
        self.inventory = Inventory()
        self.notification, self.notification_timer = '', 0
        self.health_rng = random.Random(self.seed+92)
        self.spawn_rng = random.Random(self.seed+401)
        self.damage_grace = self.pressure = 0.0
        self.reinforcements = 0
        self._spawn_check = 0
        self.completion_time = None
        self.stats = {'collected': 0, 'crafted': 0, 'defeated': 0, 'trees': 0}
        for entity in self.entities.all():
            if entity.kind != 'beacon':
                self.entities.remove(entity.id)
        self.removed_objects,self.hostile_records,self.tree_chops,self.drops = set(),{},{},{}
        self._drop_serial = self._sound_serial = 0
        self._stream_revision = -1
        self._last_stream_error = None
        self._noise_timer = 0
        self._previous_position = self.camera.x,self.camera.z
        self.beacon_commit = 0.0
        self.poison = PoisonStatus()
        self.next_viper_spawn = 0.
        self._venom_check = 0.
        self._simulation_accumulator = 0.
        self.boss = Demon(self.world.position(*self.world.arena))
        self.entities.add(self.boss)
        self.boss_effect_id = None
        self.world.clock,self.world.next_attack = 0.0,0.0
        self.world.sounds = deque(maxlen=32)
        self.world.actors = []
        self.world.player_velocity = (0,0)
        self.world.ambush_cue = None
        self.world.ai_persistence = PERCEPTION['persistence'][self.config.difficulty]
        self.world.max_attackers = 2 if self.config.difficulty=='Hard' else 1
        self._resource_meshes = {}
        self.camera.movement_cb = self.move_player
        self._sync_entities()
        omen = self.world.paths.at(self.world.paths.lengths[-1]-65)
        self.entities.add(Entity('omen',*self.world.position(omen[0]+2.7,omen[1]),meshes=models.boss_omen()))
        self._update_prompt()

    def _sync_entities(self):
        loaded = self.world.chunks
        for entity in self.entities.all():
            key = getattr(entity,'world_key',None)
            if key and chunk_key(entity.x,entity.z) not in loaded:
                if entity.kind in HOSTILE_TYPES:
                    self.hostile_records[key] = entity.snapshot()
                elif entity.kind=='tree' and entity.chops:
                    self.tree_chops[key] = entity.chops
                self.entities.remove(entity.id)
        active = {getattr(e,'world_key',None) for e in self.entities.all()}
        def add(key,kind,position,site=None):
            if key in active or key in self.removed_objects or chunk_key(position[0],position[2]) not in loaded:
                return
            if kind == 'tree':
                entity = RunTree(site)
                entity.chops = self.tree_chops.get(key,0)
            elif kind in HOSTILE_TYPES:
                if kind=='viper' and key not in self.hostile_records:
                    if (self.remaining_distance>VENOM['threshold'][self.config.length]
                            or self.world.clock<self.next_viper_spawn
                            or len(self.entities.of_kind('viper'))>=VENOM['population'][self.config.difficulty]
                            or math.hypot(position[0]-self.camera.x,position[2]-self.camera.z)<SPAWN_CLEARANCE):
                        return
                    self.next_viper_spawn = self.world.clock+VENOM['spawn_interval'][self.config.difficulty]
                entity = HOSTILE_TYPES[kind](position)
                saved = key in self.hostile_records
                if saved:
                    entity.__dict__.update(self.hostile_records.pop(key))
                elif kind=='spider':
                    candidates = [t for t in self.world.chunks[chunk_key(entity.x,entity.z)].trees
                                  if not t.removed and math.dist(t.position,position)<10]
                    if candidates:
                        tree = min(candidates,key=lambda t:math.dist(t.position,position))
                        x,z = tree.position[0]+tree.obstacle.radius+.7,tree.position[2]
                        if (self.world.is_walkable(x,z,.45) and all(e.distance_to(x,z)>1.3 for e in self.hostiles)
                                and self.world.line_clear(x,z,position[0],position[2],.45)):
                            entity.x,entity.z = x,z
                            entity.home = x,z
                            entity.ambush_height = 2.8
                            entity.y = self.world.height(x,z)+2.8
                if not saved:entity.yaw = (key[-1]*2.4)%math.tau
            elif kind=='dropped':
                item,quantity = self.drops[key][1:]
                entity = Entity(kind,*position,meshes=self.item_meshes(item),interactable=True)
                entity.loot = {item:quantity}
            else:
                entity = Entity(kind,*position,meshes=self.item_meshes(kind,key[-1]%8),interactable=True)
                entity.yaw = (key[-1]*2.4)%math.tau if kind in ('rock','stick') else 0
            entity.world_key = key
            self.entities.add(entity)
            active.add(key)
        for key,chunk in loaded.items():
            for tree in chunk.trees:
                if not tree.removed:
                    add(('tree',*tree.key),'tree',tree.position,tree)
        for i,(kind,pos) in enumerate(self.world.resources):
            add(('resource',i),kind,pos)
        for i,pos in enumerate(self.world.signs):
            add(('sign',i),'sign',pos)
        for i,(kind,pos,_) in enumerate(self.world.hostile_sites):
            key = ('hostile',i)
            record = self.hostile_records.get(key)
            add(key,kind,(record['x'],record['y'],record['z']) if record else pos)
        for key,record in tuple(self.hostile_records.items()):
            if key[0]=='reinforcement':
                add(key,record['kind'],(record['x'],record['y'],record['z']))
        for key,(position,item,quantity) in self.drops.items():
            add(key,'dropped',position)
        self._stream_revision = self.world.render_revision

    def item_meshes(self,kind,variant=0):
        cache_key = kind,variant if kind in ('rock','stick') else 0
        if cache_key not in self._resource_meshes:
            factory = {'can':models.food_can,'food':models.food_can,'bottle':models.plastic_bottle,'water':models.plastic_bottle,
                       'rock':models.rock,'stick':models.stick,'sign':models.skull_sign,'leaves':models.leaves,
                       'bandage':models.bandage,'axe':models.axe,'spear':models.spear,
                       'compass':lambda:models.compass()[0],
                       'metal_scrap':lambda:[models.lathe([(0,.2),(.03,.2)],(170,179,180),6)],
                       'plastic_scrap':lambda:[models.lathe([(0,.15),(.08,.18)],(123,188,206),5)]}[kind]
            meshes = models.rock(self.seed+variant*71) if kind=='rock' else factory()
            if kind=='stick':
                meshes = models.scaled_meshes(meshes,.8+variant*.05)
            self._resource_meshes[cache_key] = meshes
        return self._resource_meshes[cache_key]

    def mark_removed(self,target):
        key = getattr(target,'world_key',None)
        if key:
            if key[0]!='drop':
                self.removed_objects.add(key)
            self.drops.pop(key,None)
            self.hostile_records.pop(key,None)
        self.entities.remove(target.id)

    def move_player(self,x,z,dx,dz,radius=.4):
        steps = max(1,math.ceil(math.hypot(dx,dz)/.16))
        for _ in range(steps):
            nx,nz = self.world.move(x,z,dx/steps,dz/steps,radius)
            for enemy in self.hostiles:
                if enemy.state in ('concealed','ambush','dormant','emerging'):
                    continue
                minimum = radius+enemy.radius+.04
                if math.hypot(nx-enemy.x,nz-enemy.z)<minimum and math.hypot(nx-enemy.x,nz-enemy.z)<math.hypot(x-enemy.x,z-enemy.z):
                    alternatives = ((nx,z),(x,nz))
                    nx,nz = next(((a,b) for a,b in alternatives if math.hypot(a-enemy.x,b-enemy.z)>=minimum
                                  and self.world.is_walkable(a,b,radius)),(x,z))
            if any(e.state not in ('concealed','ambush','dormant','emerging') and math.hypot(nx-e.x,nz-e.z)<radius+e.radius+.04
                   and math.hypot(nx-e.x,nz-e.z)<math.hypot(x-e.x,z-e.z) for e in self.hostiles):
                nx,nz = x,z
            x,z = nx,nz
        return x,z

    def sound(self,kind,radius):
        self._sound_serial += 1
        self.world.sounds.append(SoundEvent(self._sound_serial,(self.camera.x,self.camera.z),kind,radius,self.world.clock+1.5))

    @property
    def hostiles(self):
        return self.entities.of_kind(*HOSTILE_TYPES,'boss')

    @property
    def remaining_distance(self):
        return math.hypot(self.camera.x-self.world.beacon[0],self.camera.z-self.world.beacon[2])

    @property
    def objective_text(self):
        if self.boss.encounter==BossStage.DEFEATED:return 'Beacon unlocked: enter the ring and press [F]'
        if self.boss.encounter==BossStage.ACTIVE:return 'Defeat the Demon | punish its recovery'
        if self.boss.encounter==BossStage.EMERGING:return 'The Demon is waking. Get ready.'
        return 'Find the northern clearing | watch the route signs'

    @property
    def dog(self):
        return min(self.hostiles, key=lambda e: e.distance_to(self.camera.x, self.camera.z), default=None)

    @property
    def instruction(self):
        return ('RUN COMPLETE' if self.level_complete else 'GAME OVER' if not self.active else 'CS JUNGLE',
                f'Time: {self.elapsed:.1f}s')

    def action_coach(self):
        return None

    def cancel_use(self):
        held = getattr(self,'_e_down',False)
        super().cancel_use()
        self._use_latched = held

    def update_use(self,dt,held):
        self._e_down = held
        return super().update_use(dt,held)

    def objective_direction(self):
        return None

    def objective_markers(self):
        return [ObjectiveMarker(self.beacon_id, 'ring')]

    def _progress(self):
        pass

    def toggle_crafting(self):
        if not self.active:
            return False
        self.crafting_open = not self.crafting_open
        self.cancel_use()
        return True

    def recipe_status(self, recipe_id):
        if recipe_id not in self.recipes:
            return False, 'Recipe unavailable'
        recipe = RECIPES[recipe_id]
        if recipe_id != 'bandage' and self.inventory.has(recipe['output']):
            return False, 'Already in your pack'
        missing = [f'{qty-self.inventory.count(item)} {ITEMS[item][0]}'
                   for item, qty in recipe['materials'].items() if not self.inventory.has(item, qty)]
        if missing:
            return False, 'Need '+', '.join(missing)
        return (True, 'Materials ready.') if self.inventory.can_craft(recipe_id) else (False, 'Pack is full.')

    def craft(self):
        if not self.active or not self.crafting_open or self.help_open:
            return False
        if not 0 <= self.selected_recipe < len(self.recipes):
            return False
        recipe = self.recipes[self.selected_recipe]
        ready, reason = self.recipe_status(recipe)
        if not ready or not self.inventory.craft(recipe):
            self.notify(reason)
            return False
        self.stats['crafted'] += 1
        self.notify(ITEMS[recipe][0]+' crafted')
        return True

    def use_status(self):
        item = self.inventory.selected_item
        if item not in ('food', 'water', 'bandage'):
            return False, 'Select food, water or a bandage'
        if self.camera.health >= self.camera.max_health and item=='bandage':
            return False, 'Health already full'
        return True, ('Hold [E]: heal 20-35' if item=='bandage' else
                      f"Hold [E]: +10 health, +{VENOM['water_stamina']:g} stamina, cure poison" if item=='water' else 'Hold [E]: +10 health, then scrap')

    @staticmethod
    def loot(target):
        return target.loot if target.kind == 'dropped' else LOOT[target.kind]

    def drop_selected(self):
        item = self.inventory.selected_item
        if not self.active or self.crafting_open or self.help_open or not item:
            return False
        slot = self.inventory.slots[self.inventory.selected_slot]
        x, z = self.camera.x+.7*math.sin(self.camera.yaw), self.camera.z+.7*math.cos(self.camera.yaw)
        if not self.world.is_walkable(x,z):
            x,z = self.camera.x,self.camera.z
        if len(self.drops)>=512:
            self.notify('Too much loose loot. Pick some up first.')
            return False
        position = self.world.position(x,z)
        target = Entity('dropped', *position, meshes=self.item_meshes(item), interactable=True)
        target.loot = {item:slot[1]}
        self._drop_serial += 1
        target.world_key = ('drop',self._drop_serial)
        self.drops[target.world_key] = position,item,slot[1]
        self.entities.add(target)
        self.inventory.slots[self.inventory.selected_slot] = None
        self.cancel_use()
        self.notify(f'Dropped {ITEMS[item][0]} x{slot[1]}')
        return True

    def _consume(self, item):
        if not self.active or self.inventory.selected_item != item or not self.use_status()[0]:
            return False
        candidate = self.inventory.slots.copy()
        index = self.inventory.selected_slot
        quantity = candidate[index][1]
        candidate[index] = (item,quantity-1) if quantity>1 else None
        scrap = CONSUMED_CONTAINER.get(item)
        if scrap and not self.inventory._insert(candidate,scrap,1):
            self.notify('Pack full. Make room for the empty container.')
            return False
        self.inventory.slots = candidate
        amount = self.health_rng.randint(*HEAL_RANGE) if item == 'bandage' else HEAL_AMOUNT
        before = self.camera.health
        self.camera.health = min(self.camera.max_health, before+amount)
        extra = ''
        if item=='water':
            stamina_before = self.camera.stamina
            self.camera.stamina = min(self.camera.max_stamina,self.camera.stamina+VENOM['water_stamina'])
            cured = self.poison.cure()
            extra = f' | +{int(self.camera.stamina-stamina_before)} stamina'+(' | Poison cured' if cured else '')
        self.health_feedback, self.health_flash_timer = 'heal', .65
        self.notify(f'+{int(self.camera.health-before)} health'+extra+(f' | +1 {ITEMS[scrap][0]}' if scrap else ''))
        return True

    def interaction_target(self):
        if not self.active or self.crafting_open or self.help_open:
            return None
        beacon = self.entities.get(self.beacon_id)
        if (beacon and beacon.distance_to(self.camera.x,self.camera.z)<=INTERACTION_RANGE
                and self.world.line_clear(self.camera.x,self.camera.z,beacon.x,beacon.z,.1)):
            return beacon
        choices = []
        for target in self.entities.all():
            if not target.interactable or not target.visible:
                continue
            distance = target.distance_to(self.camera.x, self.camera.z)
            if target.kind == 'tree':
                if self.inventory.selected_item != 'axe':
                    continue
                distance = max(0, distance-target.site.obstacle.radius)
                if distance > WEAPONS['axe']['range'] or self._facing(target) < .7:
                    continue
                radius = .1
                surface = (target.x+(self.camera.x-target.x)*target.site.obstacle.radius/max(.01, target.distance_to(self.camera.x, self.camera.z)),
                           target.z+(self.camera.z-target.z)*target.site.obstacle.radius/max(.01, target.distance_to(self.camera.x, self.camera.z)))
                if not all(o == target.site.obstacle or math.dist((self.camera.x, self.camera.z), (o.x, o.z)) > o.radius+.1
                           for o in self.world.obstacles):
                    continue
                from engine.paths import segment_distance
                if any(o != target.site.obstacle and segment_distance(o.x, o.z, (self.camera.x, self.camera.z), surface) < o.radius+radius
                       for o in self.world.obstacles):
                    continue
            elif distance > INTERACTION_RANGE or not self.world.line_clear(self.camera.x, self.camera.z, target.x, target.z, .1):
                continue
            choices.append((target, distance))
        return min(choices, key=lambda pair: (self._facing(pair[0]) < .5, pair[1]), default=(None, 0))[0]

    def world_prompt(self):
        if not self.active or self.crafting_open or self.help_open:
            return None
        target = self.interaction_target()
        if target:
            if target.kind == 'tree':
                ready, _ = self.attack_status()
                if self.inventory.selected_item != 'axe' or not ready:
                    return None
                title, text = f'Tree {target.chops}/{TREE_CHOPS}', 'Press [F] to chop tree'
            elif target.kind == 'sign':
                title, text = 'Dangerous shortcut', 'Press [F] to read sign'
            elif target.kind == 'beacon':
                if self.boss.encounter!=BossStage.DEFEATED:
                    return WorldPrompt(target.id,'Beacon sealed','Defeat the Demon first',
                                       (target.x,target.y+1.2,target.z),False)
                title = 'Northern beacon'
                text = 'Linking... stay in the ring' if self.beacon_commit>0 else 'Press [F] to finish run'
            else:
                if not self.inventory.can_add_many(self.loot(target)):
                    return WorldPrompt(target.id, 'Inventory full', 'Select a slot; [G] drops its stack', (target.x, target.y+.6, target.z), False)
                title = ITEMS[next(iter(target.loot))][0] if target.kind == 'dropped' else {
                    'can': 'Food can', 'bottle': 'Water bottle', 'rock': 'Collectible stone',
                    'stick': 'Stick', 'leaves': 'Leaves'}[target.kind]
                text = 'Press [F] to pick up'
            return WorldPrompt(target.id, title, text, (target.x, target.y+target.visual_height+.2, target.z), True)
        target = self.attack_target()
        if target and self.attack_status()[0]:
            return WorldPrompt(target.id, {'spider':'Giant spider','dog':'Hostile dog','viper':'Venom runner','boss':'Demon Thing'}[target.kind],
                               'Left click to attack', (target.x, target.y+target.visual_height+.2, target.z), True)
        return None

    def handle_interaction(self):
        if not self.active or self.crafting_open or self.help_open:
            return False
        target = self.interaction_target()
        if target is None:
            self.notify('Nothing in reach')
            return False
        if target.kind == 'beacon':
            if self.camera.health<=0 or self.boss.encounter!=BossStage.DEFEATED:
                self.notify('Beacon sealed. Defeat the Demon Thing first.',3)
                return False
            if self.beacon_commit<=0:
                self.beacon_commit = .8
                self.notify('Linking beacon... stay in the ring.',2)
        elif target.kind == 'sign':
            self.notify('Skull sign: shorter route, more hostiles.', 5)
        elif target.kind == 'tree':
            return self.chop(target)
        else:
            if not self.inventory.add_many(self.loot(target)):
                self.notify("Pack full | Select a slot; [G] drops its stack")
                return False
            self.mark_removed(target)
            self.stats['collected'] += 1
            self.notify(' + '.join(f'+{qty} {ITEMS[item][0]}' for item, qty in self.loot(target).items()))
        return True

    def attack_status(self):
        weapon = WEAPONS.get(self.inventory.selected_item)
        if not weapon:
            return False, 'Equip a spear or axe'
        if self.attack_cooldown_timer > 1e-6:
            return False, f'Attack ready in {self.attack_cooldown_timer:.1f}s'
        if self.camera.stamina < weapon['stamina']:
            return False, 'Low stamina. Stop to recover.'
        return True, 'Left click to attack'

    def attack_target(self):
        weapon = WEAPONS.get(self.inventory.selected_item)
        if not weapon:
            return None
        choices = []
        for target in self.hostiles:
            if target.kind=='boss' and target.encounter!=BossStage.ACTIVE:continue
            distance = target.distance_to(self.camera.x, self.camera.z)
            pitch = math.atan2(self.camera.y-target.y-.6, max(distance, .01))
            if (distance <= weapon['range'] and self._facing(target) >= math.cos(math.radians(45))
                    and abs(self.camera.pitch-pitch) < math.radians(55)
                    and self.world.line_clear(self.camera.x, self.camera.z, target.x, target.z, .1)):
                choices.append(target)
        return min(choices, key=lambda e: e.distance_to(self.camera.x, self.camera.z), default=None)

    def _swing(self):
        ready, reason = self.attack_status()
        if not ready:
            self.notify(reason, 1)
            return False
        weapon = WEAPONS[self.inventory.selected_item]
        self.camera.stamina = max(0, self.camera.stamina-weapon['stamina'])
        self.attack_cooldown_timer = weapon['cooldown']
        self.attack_anim_timer = weapon['animation']
        self.cancel_use()
        self.sound('fight',PERCEPTION['fight_noise'])
        return True

    def handle_attack(self):
        if not self.active or self.crafting_open or self.help_open or not self._swing():
            return False
        target = self.attack_target()
        if target:
            damage = WEAPONS[self.inventory.selected_item]['damage']
            actual = target.receive_hit(damage) if target.kind=='boss' else min(target.health,damage)
            if target.kind!='boss':target.health = max(0,target.health-actual)
            self.notify(f'Hit: {actual} | {target.kind}: {target.health} health'+
                        (' | Guarded; wait for recovery' if actual<damage and target.health>0 else ''))
            if target.health <= 0:
                self.mark_removed(target)
                self.stats['defeated'] += 1
                self.notify(target.kind.title()+' defeated')
                if target.kind=='boss':self.notify('The Demon thing has been defeated. The beacon is yours.',6)
        return True

    def chop(self, target):
        key = getattr(target,'world_key',None)
        if len(self.world.removed_trees)>=4096 or (key not in self.tree_chops and len(self.tree_chops)>=4096):
            self.notify('Forest edit budget reached. Time to find that beacon.')
            return False
        if target.chops+1>=TREE_CHOPS and len(self.drops)>=512:
            self.notify('Loose loot budget reached. Pick some up before felling more trees.')
            return False
        if self.inventory.selected_item != 'axe' or self.interaction_target() != target or not self._swing():
            return False
        target.chops += 1
        if key:self.tree_chops[key] = target.chops
        self.sound('chop',PERCEPTION['chop_noise'])
        self.notify(f'Chop {target.chops}/{TREE_CHOPS}')
        if target.chops >= TREE_CHOPS:
            self.tree_chops.pop(getattr(target,'world_key',None),None)
            self.world.remove_tree(target.site)
            self.mark_removed(target)
            self.camera.obstacles = [(o.x, o.z, o.radius, 2) for o in self.world.obstacles]
            distance = max(.01, target.distance_to(self.camera.x, self.camera.z))
            x = self.camera.x+(target.x-self.camera.x)/distance*.5
            z = self.camera.z+(target.z-self.camera.z)/distance*.5
            if not self.world.is_walkable(x, z):
                x, z = self.camera.x, self.camera.z
            self._drop_serial += 1
            key = ('drop',self._drop_serial)
            self.drops[key] = self.world.position(x,z),'leaves',TREE_LEAVES
            self._sync_entities()
            self.stats['trees'] += 1
            self.notify('Tree cleared | Leaves dropped')
        return True

    @property
    def north_progress(self):
        total = math.hypot(self.world.spawn[0]-self.world.beacon[0],self.world.spawn[2]-self.world.beacon[2])
        return max(0,min(1,1-self.remaining_distance/max(1,total)))

    def _emerge(self, dt):
        balance = self.config.balance
        if self.north_progress < .25 or self.reinforcements >= balance.reinforcement_limit:
            return
        self.pressure += dt*(.15+.85*self.north_progress**balance.north_exponent)
        self._spawn_check = max(0,self._spawn_check-dt)
        if self.pressure < balance.reinforcement_interval or self._spawn_check>0:
            return
        self._spawn_check = 1
        candidates = [point for line in self.world.paths.shortcuts
                      if min(line[0][1],line[-1][1])-24<=self.camera.z<=max(line[0][1],line[-1][1])+24
                      for point in line
                      if SPAWN_CLEARANCE <= math.hypot(point[0]-self.camera.x, point[1]-self.camera.z) <= 24
                      and self.world.is_walkable(*point, .45)
                      and math.dist(point,self.world.arena)>26
                      and all(e.distance_to(*point)>4 for e in self.hostiles)]
        if not candidates:
            return
        point = self.spawn_rng.choice(candidates)
        enemy = Spider(self.world.position(*point))
        enemy.world_key = ('reinforcement',self.reinforcements)
        enemy.state = 'patrol'
        self.entities.add(enemy)
        self.reinforcements += 1
        self.pressure = 0

    def update(self,dt):
        if self.camera.health<=0 and self.state!=Stage.COMPLETE:
            self.state = Stage.DEAD
            self.cancel_use()
        if not self.active or self.crafting_open or self.help_open:return
        self._simulation_accumulator += max(0,min(.25,dt))
        while self._simulation_accumulator+1e-9>=1/60:
            self._simulation_accumulator -= 1/60
            self._step(1/60)
            if not self.active:break

    def _damage_player(self,amount,source,position=None):
        if not self.active or amount<=0:return
        self.receive_damage(amount,position,source)
        self.beacon_commit = 0
        self.notify(f'-{amount} health | {source}')

    def _boss_feedback(self):
        while self.boss.events:
            event = self.boss.events.pop(0)
            text = {'emerging':'The clearing went quiet. The Demon is rising.',
                    'cleave':'Demon: claw sweep! Break its reach.',
                    'slam':'Demon: red ground! Change direction and get out.',
                    'phase_two':'The Demon is furious. Watch its recovery.',
                    'defeated':'The demon has been defeated and the Beacon unlocked.'}[event]
            self.notify(text,3)
        effect = self.entities.get(self.boss_effect_id)
        if self.boss.telegraph:
            position,meshes = self.boss.telegraph
            if effect:
                effect.x,effect.y,effect.z = position
                effect.meshes = meshes
            else:self.boss_effect_id = self.entities.add(Entity('telegraph',*position,meshes=meshes))
        elif effect:
            self.entities.remove(effect.id)
            self.boss_effect_id = None

    def _step(self, dt):
        if self.camera.health<=0 and self.state!=Stage.COMPLETE:
            self.state = Stage.DEAD
            self.cancel_use()
            return
        if not self.active or self.crafting_open or self.help_open:
            return
        dt = max(0, min(.1, dt))
        if self.camera.health<=0:
            self.state = Stage.DEAD
            self.cancel_use()
            return
        self.world.pinned_chunks = {chunk_key(e.x,e.z) for e in self.hostiles
                                    if e.state in ('pursue','flank','attack','recover','investigate','search','cleave','slam')
                                    and e.distance_to(self.camera.x,self.camera.z)<PERCEPTION['encounter_leash']}
        delta = self.camera.x-self._previous_position[0],self.camera.z-self._previous_position[1]
        norm = math.hypot(*delta)
        direction = (delta[0]/norm,delta[1]/norm) if norm>.001 else self.camera.forward_vec()
        self.world.update_stream(self.camera.x,self.camera.z,direction)
        if self.world.stream_error != self._last_stream_error:
            self._last_stream_error = self.world.stream_error
            self.notify('Forest loading hit a snag. Pause and start a new run.',8)
        if self._stream_revision != self.world.render_revision:
            self._sync_entities()
        self.damage_feedback.update(dt)
        self.world.clock += dt
        self.world.actors = self.hostiles
        current = self.camera.x,self.camera.z
        travelled = math.dist(current,self._previous_position)
        self.world.player_velocity = tuple((a-b)/max(.001,dt) for a,b in zip(current,self._previous_position))
        self._previous_position = current
        self._noise_timer -= dt
        if travelled>.002 and self._noise_timer<=0:
            self.sound('sprint' if self.camera.sprinting else 'walk',PERCEPTION['sprint_noise'] if self.camera.sprinting else PERCEPTION['walk_noise'])
            self._noise_timer = .35 if self.camera.sprinting else .55
        while self.world.sounds and self.world.sounds[0].expires<self.world.clock:
            self.world.sounds.popleft()
        self.elapsed += dt
        for name in ('notification_timer', 'health_flash_timer', 'attack_cooldown_timer', 'attack_anim_timer', 'damage_grace'):
            setattr(self, name, max(0, getattr(self, name)-dt))
        self._emerge(dt)
        if self.world.clock>=self.next_viper_spawn and self.world.clock>=self._venom_check:
            self._venom_check = self.world.clock+1
            if self.remaining_distance<=VENOM['threshold'][self.config.length]:self._sync_entities()
        poison_damage = self.poison.update(dt)
        if poison_damage:self._damage_player(poison_damage,'Poison')
        if not self.active:return
        for enemy in self.hostiles:
            enemy.detection = type(enemy).detection*(1+self.config.balance.aggression_gain*self.north_progress)
            enemy.alert_duration = {'Easy':.6,'Medium':.4,'Hard':.3}[self.config.difficulty]
            damage = enemy.update(dt, self.camera, self.world)
            if damage and self.damage_grace <= 0:
                self.damage_grace = DAMAGE_GRACE
                self._damage_player(damage,'Demon' if enemy.kind=='boss' else enemy.kind.title(),enemy.position)
                if enemy.kind=='viper':
                    self.poison.apply()
                    self.notify(f'-{damage} health | Poisoned! Drink water to cure.',4)
                if not self.active:break
        self._boss_feedback()
        if self.world.ambush_cue:
            if math.dist((self.camera.x,self.camera.z),(self.world.ambush_cue[0],self.world.ambush_cue[2]))<14:
                self.notify('Skittering overhead. Heads up.',2)
            self.world.ambush_cue = None
        if self.beacon_commit>0 and self.active:
            beacon = self.entities.get(self.beacon_id)
            if beacon.distance_to(self.camera.x,self.camera.z)>INTERACTION_RANGE or self.boss.encounter!=BossStage.DEFEATED:
                self.beacon_commit = 0
            else:
                self.beacon_commit -= dt
                if self.beacon_commit<=1e-6:
                    self.state,self.completion_time = Stage.COMPLETE,self.elapsed
                    self.cancel_use()
                    self.notify('Northern end reached. W.',6)
        if self.camera.sprint_blocked and not self._sprint_blocked:
            self.notify('Low stamina | Stop to recover', 2)
        self._sprint_blocked = self.camera.sprint_blocked
