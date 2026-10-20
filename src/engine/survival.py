import math
import random

from engine import models
from engine.entity import Entity, Dog, Spider
from engine.inventory import Inventory
from engine.items import ITEMS, RECIPES, RUN_RECIPE_ORDER, HEAL_AMOUNT, USE_DURATION
from engine.level1 import Level1, Stage, INTERACTION_RANGE
from engine.markers import ObjectiveMarker
from engine.prompts import WorldPrompt
from engine.run_config import (RunConfig, WEAPONS, TREE_CHOPS, TREE_LEAVES, HEAL_RANGE,
                               SPAWN_CLEARANCE, DAMAGE_GRACE)
from engine.survival_world import SurvivalChunk


LOOT = {'can': {'food': 1, 'metal_scrap': 1}, 'bottle': {'water': 1, 'plastic_scrap': 1},
        'stick': {'stick': 1}, 'rock': {'rock': 1}, 'leaves': {'leaves': TREE_LEAVES}}


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

    def __init__(self, camera, seed=42, config=None):
        self.config, self.seed = config or RunConfig(), seed
        self._ready = False
        super().__init__(camera, seed, SurvivalChunk(seed, self.config))
        self.axe_meshes = models.axe()
        self.held_props.update({'leaves': models.held_prop(models.leaves()),
                                'bandage': models.held_prop(models.bandage())})

    def reset(self):
        if self._ready:
            self.world = SurvivalChunk(self.seed, self.config)
        super().reset()
        self._ready = True
        self.state = Stage.BEACON
        self.camera.health = self.camera.max_health
        self.inventory = Inventory()
        self.notification, self.notification_timer = '', 0
        self.health_rng = random.Random(self.seed+92)
        self.spawn_rng = random.Random(self.seed+401)
        self.damage_grace = self.pressure = 0.0
        self.reinforcements = 0
        self.completion_time = None
        self.stats = {'collected': 0, 'crafted': 0, 'defeated': 0, 'trees': 0}
        for site in self.world.trees:
            if self.world.is_walkable(site.position[0], site.position[2], 0):
                continue
            minx, maxx, minz, maxz = self.world.bounds
            if minx+1 < site.position[0] < maxx-1 and minz+1 < site.position[2] < maxz-1:
                self.entities.add(RunTree(site))
        for position in self.world.signs:
            self.entities.add(Entity('sign', *position, meshes=models.skull_sign(), interactable=True))
        for kind, position, _ in self.world.hostile_sites:
            if math.hypot(position[0]-self.camera.x, position[2]-self.camera.z) >= SPAWN_CLEARANCE:
                self.entities.add((Dog if kind == 'dog' else Spider)(position))
        self._update_prompt()

    @property
    def hostiles(self):
        return self.entities.of_kind('dog', 'spider')

    @property
    def dog(self):
        return min(self.hostiles, key=lambda e: e.distance_to(self.camera.x, self.camera.z), default=None)

    @property
    def instruction(self):
        return ('RUN COMPLETE' if self.level_complete else 'GAME OVER' if not self.active else 'CS JUNGLE',
                f'Time: {self.elapsed:.1f}s')

    def action_coach(self):
        return None

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
        if self.camera.health >= self.camera.max_health:
            return False, 'Health already full'
        return True, 'Hold [E]: heal 20-35' if item == 'bandage' else 'Hold [E]: +10 health'

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
        factory = {'food':models.food_can, 'water':models.plastic_bottle, 'rock':models.rock,
                   'stick':models.stick, 'leaves':models.leaves, 'bandage':models.bandage,
                   'axe':models.axe, 'spear':models.spear}.get(item, models.bandage)
        target = Entity('dropped', *self.world.position(x,z), meshes=factory(), interactable=True)
        target.loot = {item:slot[1]}
        self.entities.add(target)
        self.inventory.slots[self.inventory.selected_slot] = None
        self.cancel_use()
        self.notify(f'Dropped {ITEMS[item][0]} x{slot[1]}')
        return True

    def _consume(self, item):
        if not self.active or self.inventory.selected_item != item or not self.use_status()[0]:
            return False
        index = self.inventory.selected_slot
        slot = self.inventory.slots[index]
        self.inventory.slots[index] = (item, slot[1]-1) if slot[1] > 1 else None
        amount = self.health_rng.randint(*HEAL_RANGE) if item == 'bandage' else HEAL_AMOUNT
        before = self.camera.health
        self.camera.health = min(self.camera.max_health, before+amount)
        self.health_feedback, self.health_flash_timer = 'heal', .65
        self.notify(f'+{int(self.camera.health-before)} health')
        return True

    def interaction_target(self):
        if not self.active or self.crafting_open or self.help_open:
            return None
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
                title, text = 'Northern beacon', 'Press [F] to finish run'
            else:
                if not self.inventory.can_add_many(self.loot(target)):
                    return WorldPrompt(target.id, 'Inventory full', 'Select a slot; [G] drops its stack', (target.x, target.y+.6, target.z), False)
                title = ITEMS[next(iter(target.loot))][0] if target.kind == 'dropped' else {
                    'can': 'Food can + metal', 'bottle': 'Water + plastic', 'rock': 'Collectible stone',
                    'stick': 'Stick', 'leaves': 'Leaves'}[target.kind]
                text = 'Press [F] to pick up'
            return WorldPrompt(target.id, title, text, (target.x, target.y+target.visual_height+.2, target.z), True)
        target = self.attack_target()
        if target and self.attack_status()[0]:
            return WorldPrompt(target.id, 'Giant spider' if target.kind == 'spider' else 'Hostile dog',
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
            self.state, self.completion_time = Stage.COMPLETE, self.elapsed
            self.cancel_use()
            self.notify('Northern end reached. W.', 6)
        elif target.kind == 'sign':
            self.notify('Skull sign: shorter route, more hostiles.', 5)
        elif target.kind == 'tree':
            return self.chop(target)
        else:
            if not self.inventory.add_many(self.loot(target)):
                self.notify("Pack full | Select a slot; [G] drops its stack")
                return False
            self.entities.remove(target.id)
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
        return True

    def handle_attack(self):
        if not self.active or self.crafting_open or self.help_open or not self._swing():
            return False
        target = self.attack_target()
        if target:
            target.health = max(0, target.health-WEAPONS[self.inventory.selected_item]['damage'])
            self.notify(f'Hit landed | {target.kind}: {target.health} health')
            if target.health <= 0:
                self.entities.remove(target.id)
                self.stats['defeated'] += 1
                self.notify(target.kind.title()+' defeated')
        return True

    def chop(self, target):
        if self.inventory.selected_item != 'axe' or self.interaction_target() != target or not self._swing():
            return False
        target.chops += 1
        self.notify(f'Chop {target.chops}/{TREE_CHOPS}')
        if target.chops >= TREE_CHOPS:
            self.world.remove_tree(target.site)
            self.entities.remove(target.id)
            self.camera.obstacles = [(o.x, o.z, o.radius, 2) for o in self.world.obstacles]
            distance = max(.01, target.distance_to(self.camera.x, self.camera.z))
            x = self.camera.x+(target.x-self.camera.x)/distance*.5
            z = self.camera.z+(target.z-self.camera.z)/distance*.5
            if not self.world.is_walkable(x, z):
                x, z = self.camera.x, self.camera.z
            self.entities.add(Entity('leaves', x, self.world.height(x, z), z, meshes=models.leaves(), interactable=True))
            self.stats['trees'] += 1
            self.notify('Tree cleared | Leaves dropped')
        return True

    @property
    def north_progress(self):
        return max(0, min(1, (self.world.spawn[2]-self.camera.z)/(self.world.spawn[2]-self.world.beacon[2])))

    def _emerge(self, dt):
        balance = self.config.balance
        if self.north_progress < .25 or self.reinforcements >= balance.reinforcement_limit:
            return
        self.pressure += dt*(.15+.85*self.north_progress**balance.north_exponent)
        if self.pressure < balance.reinforcement_interval:
            return
        candidates = [point for line in self.world.paths.shortcuts for point in line
                      if SPAWN_CLEARANCE <= math.hypot(point[0]-self.camera.x, point[1]-self.camera.z) <= 24
                      and self.world.is_walkable(*point, .45)]
        if not candidates:
            return
        point = self.spawn_rng.choice(candidates)
        enemy = Spider(self.world.position(*point))
        self.entities.add(enemy)
        self.reinforcements += 1
        self.pressure = 0

    def update(self, dt):
        if not self.active or self.crafting_open or self.help_open:
            return
        dt = max(0, min(.1, dt))
        self.elapsed += dt
        for name in ('notification_timer', 'health_flash_timer', 'attack_cooldown_timer', 'attack_anim_timer', 'damage_grace'):
            setattr(self, name, max(0, getattr(self, name)-dt))
        self._emerge(dt)
        for enemy in self.hostiles:
            enemy.detection = type(enemy).detection*(1+self.config.balance.aggression_gain*self.north_progress)
            damage = enemy.update(dt, self.camera, self.world)
            if damage and self.damage_grace <= 0:
                self.camera.take_damage(damage)
                self.damage_grace = DAMAGE_GRACE
                self.health_feedback, self.health_flash_timer = 'damage', .65
                self.notify(f'-{damage} health')
                if self.camera.health <= 0:
                    self.state = Stage.DEAD
                    self.cancel_use()
                    break
        if self.camera.sprint_blocked and not self._sprint_blocked:
            self.notify('Low stamina | Stop to recover', 2)
        self._sprint_blocked = self.camera.sprint_blocked
