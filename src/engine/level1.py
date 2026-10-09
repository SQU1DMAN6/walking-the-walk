from enum import IntEnum
import math

from engine.chunk import TutorialChunk
from engine.entity import Entity, EntityManager, Dog
from engine.inventory import Inventory
from engine.items import (RESOURCE_LOOT, ITEMS, HEAL_AMOUNT, PLAYER_SPEED,
                          SPEAR_RANGE, SPEAR_DAMAGE, SPEAR_COOLDOWN, RECIPES, RECIPE_ORDER, USE_DURATION)
from engine.markers import ObjectiveMarker, create_arrow, create_ring
from engine import models


class Stage(IntEnum):
    MOVEMENT = 0
    LOOK = 1
    SUPPLIES = 2
    CONSUME = 3
    COMPASS = 4
    MATERIALS = 5
    SPEAR = 6
    COMBAT = 7
    BEACON = 8
    COMPLETE = 9
    DEAD = 10


INSTRUCTIONS = {
    Stage.MOVEMENT: ("LET'S ROLL", 'WASD to walk. Follow the forest path.'),
    Stage.LOOK: ('LOOK AROUND', 'Move your mouse to look around.'),
    Stage.SUPPLIES: ('LOOT RUN', 'Follow the yellow arrows. Hit [F] to collect the marked items.'),
    Stage.CONSUME: ('EAT STUFF', 'Pick food [{food_slot}] or water [{water_slot}], then hold [E] for a second. Each adds 10 health.'),
    Stage.COMPASS: ('GET YOUR THINGS', '[C] opens crafting. Pick Compass, check you got the materials, then craft.'),
    Stage.MATERIALS: ('GET MORE THINGS', 'Keep following the arrows. Hit [F] to collect the marked items.'),
    Stage.SPEAR: ('CRAFT', 'Open with [C], pick the Stone spear, and craft it. Then use [C] to close the menu.'),
    Stage.COMBAT: ('THAT DOG IS NOT CHILL', 'Pick spear [{spear_slot}]. Left click to thrust; back up before it bites.'),
    Stage.BEACON: ('HOME STRETCH', 'Hold compass [{compass_slot}] and follow its red needle along the path. Hit [F] once you\'re at the turquoise ring.'),
    Stage.COMPLETE: ('WALK COMPLETE. W PLAYER.', 'Looted, crafted, survived. Nice one, man. [R] runs it back.'),
    Stage.DEAD: ("YOU'RE COOKED", '[R] runs it back. Aim, poke, and keep some distance.'),
}
INTERACTION_RANGE = 2.2


class Level1:
    def __init__(self, camera, seed=67):
        self.camera = camera
        self.world = TutorialChunk(seed)
        self.arrow_meshes = create_arrow()
        self.ring_mesh = create_ring(self.world.beacon, self.world.height)
        self.weapon_meshes = models.spear()
        self.compass_meshes, self.compass_needle = models.compass()
        self.held_compass_meshes = [models.pose_compass(mesh) for mesh in self.compass_meshes]
        self.held_props = {
            'food': models.held_prop(models.food_can()),
            'water': models.held_prop(models.plastic_bottle()),
            'stick': models.held_prop(models.stick()),
            'rock': models.held_prop(models.rock()),
            'metal_scrap': models.held_prop([models.lathe([(0, .20), (.025, .20)], (168, 175, 180))]),
            'plastic_scrap': models.held_prop([models.lathe([(0, .15), (.06, .18)], (121, 182, 194))]),
        }
        self.reset()

    def reset(self):
        self.state = Stage.MOVEMENT
        self.inventory = Inventory()
        self.crafting_open = False
        self.selected_recipe = 0
        self.use_progress = 0.0
        self.use_item = None
        self._use_latched = False
        self.entities = EntityManager()
        self.collected = set()
        self.consumed = set()
        self.dog_id = None
        self.movement_distance = 0.0
        self.look_rotation_total = 0.0
        self.elapsed = 0.0
        self.attack_cooldown_timer = 0.0
        self.attack_anim_timer = 0.0
        self.notification = 'Welcome to CS Jungle. Grab some supplies and get your health back.'
        self.notification_timer = 5.0
        self.interaction_prompt = None
        self.camera.bounds = self.world.bounds
        self.camera.obstacles = [(o.x, o.z, o.radius, 2.0) for o in self.world.obstacles]
        self.camera.terrain_height_cb = self.world.height
        self.camera.movement_cb = self.world.move
        self.camera.move_speed = PLAYER_SPEED
        self.camera.sprint_factor = 1.35
        self.camera.x, ground, self.camera.z = self.world.spawn
        self.camera.y = ground+self.camera.eye_height
        a, b = self.world.paths.route[:2]
        self.camera.yaw = math.atan2(b[0]-a[0], b[1]-a[1])
        self.camera.pitch = 0.0

        self.camera.health = 80.0
        self.camera.stamina = self.camera.max_stamina
        self.camera.bob_offset = 0.0
        self.camera._bob_phase = self.camera._bob_active = 0.0
        for kind, pos in self.world.resources:
            self.entities.add(Entity(kind, *pos, meshes=models.RESOURCE_MODELS[kind](), interactable=True))
        self.beacon_id = self.entities.add(Entity('beacon', *self.world.beacon,
                                                 meshes=models.beacon(), interactable=True))
        self._last_pose = self.camera.x, self.camera.z, self.camera.yaw, self.camera.pitch
        self._update_prompt()

    @property
    def player_health(self):
        return self.camera.health

    @property
    def level_complete(self):
        return self.state == Stage.COMPLETE

    @property
    def active(self):
        return self.state not in (Stage.DEAD, Stage.COMPLETE)

    @property
    def dog(self):
        return self.entities.get(self.dog_id)

    @property
    def instruction(self):
        title, text = INSTRUCTIONS[self.state]
        if self.state == Stage.CONSUME:
            text = ' '.join(f'{ITEMS[item][0]}: done.' if item in self.consumed else
                            f'{ITEMS[item][0]}: pick [{self.inventory.number_for(item)}], hold E for {USE_DURATION:g}s.'
                            for item in ('food', 'water')) + ' +10 HP each.'
        return title, text.format(**{f'{item}_slot': self.inventory.number_for(item) or '1-9'
                                    for item in ('food', 'water', 'spear', 'compass')})

    def select_slot(self, number):
        changed = self.inventory.select_slot(number)
        if changed:
            self.cancel_use()
        return changed

    def cancel_use(self):
        self.use_progress = 0.0
        self.use_item = None
        self._use_latched = False

    def update_use(self, dt, held):
        item = self.inventory.selected_item
        if not held or not self.active or self.crafting_open or item not in ('food', 'water'):
            self.cancel_use()
            return False
        if self._use_latched:
            return False
        if self.state < Stage.CONSUME:
            return False
        if item != self.use_item:
            self.use_progress, self.use_item = 0.0, item
        self.use_progress += max(0, min(dt, .1))
        if self.use_progress + 1e-6 < USE_DURATION:
            return False
        consumed = self._consume(item)
        self.use_progress = 0.0
        self._use_latched = True
        return consumed

    def toggle_crafting(self):
        if not self.active:
            return False
        self.crafting_open = not self.crafting_open
        self.cancel_use()
        if self.crafting_open:
            self.selected_recipe = 1 if self.state == Stage.SPEAR else 0
        return True

    def recipe_status(self, recipe_id):
        recipe = RECIPES[recipe_id]
        if self.inventory.has(recipe['output']):
            return False, 'Already in your pack'
        missing = [f'{qty-self.inventory.count(item)} {ITEMS[item][0]}'
                   for item, qty in recipe['materials'].items() if not self.inventory.has(item, qty)]
        if missing:
            return False, 'Need ' + ', '.join(missing)
        required_stage = Stage.COMPASS if recipe_id == 'compass' else Stage.SPEAR
        if self.state != required_stage:
            return False, 'Finish the current tutorial step first'
        if not self.inventory.can_craft(recipe_id):
            return False, 'Pack is full.'
        return True, 'Materials ready.'

    def notify(self, message, seconds=3.0):
        self.notification, self.notification_timer = message, seconds

    def _allowed_resources(self):
        if self.state == Stage.SUPPLIES:
            return self.entities.of_kind('can', 'bottle')
        if self.state == Stage.MATERIALS:
            return self.entities.of_kind('stick', 'rock')
        return ()

    def interaction_target(self):
        candidates = self._allowed_resources()
        if self.state == Stage.BEACON:
            candidates = self.entities.of_kind('beacon')
        nearby = [e for e in candidates if e.interactable and e.visible and
                  e.distance_to(self.camera.x, self.camera.z) <= INTERACTION_RANGE and
                  self.world.line_clear(self.camera.x, self.camera.z, e.x, e.z, .1)]
        return min(nearby, key=lambda e: e.distance_to(self.camera.x, self.camera.z), default=None)

    def handle_interaction(self):
        if not self.active or self.crafting_open:
            return False
        target = self.interaction_target()
        if target is None:
            return False
        if target.kind == 'beacon':
            self.state = Stage.COMPLETE
            self.notify('Made it through CS Jungle. W.', 6)
        else:
            loot = RESOURCE_LOOT[target.kind]
            if not self.inventory.add_many(loot):
                self.notify("Pack's full.")
                return False
            self.collected.add(target.kind)
            self.entities.remove(target.id)
            self.notify('Collected: ' + ' + '.join(f'{qty} {ITEMS[item][0]}' for item, qty in loot.items()))
            self._progress()
        self._update_prompt()
        return True

    def _consume(self, item):
        if not self.active or item not in ('food', 'water') or self.inventory.selected_item != item:
            return False
        if self.state < Stage.CONSUME:
            self.notify('Grab both supplies first.')
            return False
        scrap = self.inventory.consume_selected()
        if not scrap:
            self.notify('No ' + ITEMS[item][0] + ' left.')
            return False
        before = self.camera.health
        self.camera.health = min(self.camera.max_health, before+HEAL_AMOUNT)
        self.consumed.add(item)
        self.notify(f'+{int(self.camera.health-before)} health.')
        self._progress()
        self._update_prompt()
        return True

    def craft(self):
        if not self.active or not self.crafting_open:
            return False
        recipe = RECIPE_ORDER[self.selected_recipe]
        ready, reason = self.recipe_status(recipe)
        if not ready:
            self.notify(reason)
            return False
        if not self.inventory.craft(recipe):
            self.notify('Not enough mats or pack space.')
            return False
        self.notify('Crafted ' + ITEMS[recipe][0] + '. Pick its number slot to hold it.')
        self._progress()
        self._update_prompt()
        return True

    def handle_attack(self):
        if not self.active or self.crafting_open or self.inventory.selected_item != 'spear' or self.attack_cooldown_timer > 0:
            return False
        self.attack_cooldown_timer = SPEAR_COOLDOWN
        self.attack_anim_timer = .22
        target = self.dog
        if target is None:
            return False
        dx, dz = target.x-self.camera.x, target.z-self.camera.z
        distance = math.hypot(dx, dz)
        alignment = ((dx*math.sin(self.camera.yaw)+dz*math.cos(self.camera.yaw)) / distance
                     if distance > 1e-6 else 1.0)
        vertical_angle = math.atan2(target.y+.6-self.camera.y, max(distance, .01))
        if (distance <= SPEAR_RANGE and alignment >= math.cos(math.radians(50)) and
                abs(vertical_angle+self.camera.pitch) <= math.radians(65) and
                self.world.line_clear(self.camera.x, self.camera.z, target.x, target.z, .1)):
            target.health = max(0, target.health-SPEAR_DAMAGE)
            self.notify(f'Hit landed. Dog health: {target.health}')
            if target.health == 0:
                self.entities.remove(target.id)
                self.dog_id = None
                self.state = Stage.BEACON
                self.notify('Dog down. Hold your compass and find that beacon.', 5)
            self._update_prompt()
            return True
        return False

    def _spawn_dog(self):
        pos = self.world.encounter

        if math.hypot(pos[0]-self.camera.x, pos[2]-self.camera.z) < 7:
            candidates = self.world.paths.samples(2.0)
            x, z = min((p for p in candidates if math.hypot(p[0]-self.camera.x, p[1]-self.camera.z) >= 7),
                       key=lambda p: math.hypot(p[0]-self.camera.x, p[1]-self.camera.z))
            pos = self.world.position(x, z)
        self.dog_id = self.entities.add(Dog(pos))
        self.notify('Spear crafted. Pick its slot. That dog is lurking up ahead.', 5)

    def _progress(self):
        if self.state == Stage.MOVEMENT and self.movement_distance >= 2:
            self.state = Stage.LOOK
            self.look_rotation_total = 0.0
        elif self.state == Stage.LOOK and self.look_rotation_total >= .45:
            self.state = Stage.SUPPLIES
        elif self.state == Stage.SUPPLIES and {'can', 'bottle'} <= self.collected:
            self.state = Stage.CONSUME
        elif self.state == Stage.CONSUME and {'food', 'water'} <= self.consumed:
            self.state = Stage.COMPASS
        elif self.state == Stage.COMPASS and self.inventory.has('compass'):
            self.state = Stage.MATERIALS
        elif self.state == Stage.MATERIALS and self.inventory.has('stick', 2) and self.inventory.has('rock'):
            self.state = Stage.SPEAR
        elif self.state == Stage.SPEAR and self.inventory.has('spear'):
            self.state = Stage.COMBAT
            self._spawn_dog()

    def objective_markers(self):
        if self.state in (Stage.SUPPLIES, Stage.MATERIALS):
            return [ObjectiveMarker(e.id) for e in self._allowed_resources()]
        if self.state == Stage.COMBAT and self.dog:
            return [ObjectiveMarker(self.dog_id)]
        if self.state == Stage.BEACON:
            return [ObjectiveMarker(self.beacon_id, 'ring')]
        return []

    def compass_guidance(self):
        if self.inventory.selected_item != 'compass':
            return None
        dx = self.world.beacon[0]-self.camera.x
        dz = self.world.beacon[2]-self.camera.z
        bearing = math.atan2(dx, dz)
        relative = (bearing-self.camera.yaw+math.pi) % math.tau-math.pi
        return relative, math.hypot(dx, dz), math.degrees(bearing) % 360

    def _update_prompt(self):
        target = self.interaction_target() if self.active else None
        self.interaction_prompt = ('F: FINISH THE WALK' if target.kind == 'beacon' else
                                   'F: GRAB ' + target.kind.upper()) if target else None

    def update(self, dt):
        if self.crafting_open:
            return
        dt = max(0, min(dt, .1))
        self.elapsed += dt
        self.notification_timer = max(0, self.notification_timer-dt)
        self.attack_cooldown_timer = max(0, self.attack_cooldown_timer-dt)
        self.attack_anim_timer = max(0, self.attack_anim_timer-dt)
        x, z, yaw, pitch = self._last_pose
        if self.active:
            self.movement_distance += math.hypot(self.camera.x-x, self.camera.z-z)
            if self.state == Stage.LOOK:

                self.look_rotation_total += abs((self.camera.yaw-yaw+math.pi) % math.tau-math.pi)
                self.look_rotation_total += abs(self.camera.pitch-pitch)
            if self.dog:
                damage = self.dog.update(dt, self.camera, self.world)
                if damage:
                    self.camera.take_damage(damage)
                    self.notify(f'Oof. -{damage} health. Back up before the next bite.', 2)
                    if self.camera.health <= 0:
                        self.state = Stage.DEAD
            self._progress()
            self._update_prompt()
        self._last_pose = self.camera.x, self.camera.z, self.camera.yaw, self.camera.pitch
