from enum import IntEnum
import math

from engine.chunk import TutorialChunk
from engine.entity import Entity, EntityManager, Dog
from engine.inventory import Inventory
from engine.items import (RESOURCE_LOOT, ITEMS, HEAL_AMOUNT, PLAYER_SPEED,
                          SPEAR_RANGE, SPEAR_DAMAGE, SPEAR_COOLDOWN, SPEAR_ANIMATION, RECIPES, RECIPE_ORDER, USE_DURATION)
from engine.markers import ObjectiveMarker, create_arrow, create_ring, BEACON_RING_RADIUS
from engine import models
from engine.prompts import WorldPrompt
from engine.guidance import PathGuide, ObjectiveDirection, ActionCoach


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
    Stage.MOVEMENT: ("LET'S ROLL", 'Press [W, A, S, D] to move along the path.'),
    Stage.LOOK: ('LOOK AROUND', 'Move the mouse to look around.'),
    Stage.SUPPLIES: ('FIND SUPPLIES', 'Follow yellow arrows. Press [F] near the can and bottle.'),
    Stage.CONSUME: ('USE SUPPLIES', 'Select food or water, then hold [E]: +10 health.'),
    Stage.COMPASS: ('CRAFT A COMPASS', 'Press [C]. Choose Compass, then [Enter] to craft.'),
    Stage.MATERIALS: ('GATHER MATERIALS', 'Press [F] near the arrows. Pick up 2 sticks and 1 rock.'),
    Stage.SPEAR: ('CRAFT A SPEAR', 'Press [C]. Choose Stone spear, then [Enter] to craft.'),
    Stage.COMBAT: ('DEFEAT THE DOG', 'Press [{spear_slot}] to equip spear. Left click to attack; back away before bites.'),
    Stage.BEACON: ('FIND THE BEACON', 'Press [{compass_slot}] to hold compass. Follow its red needle to the ring.'),
    Stage.COMPLETE: ('TUTORIAL COMPLETE', 'Press [R] to restart or [Esc] for the title.'),
    Stage.DEAD: ('GAME OVER', 'Press [R] to retry. Attack, then back away before bites.'),
}
INTERACTION_RANGE = 2.2


class Level1:
    def __init__(self, camera, seed=67):
        self.camera = camera
        self.world = TutorialChunk(seed)
        self.path_guide = PathGuide(self.world.paths)
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
        self.help_open = False
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
        self.notification = 'CS Jungle | Follow the path'
        self.notification_timer = 5.0
        self.objective_flash_timer = self.health_flash_timer = 0.0
        self.health_feedback = None
        self._prompt_id = None
        self._sprint_blocked = False
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
        self.camera.sprint_blocked = False
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
            item = next((item for item in ('food', 'water') if item not in self.consumed), 'water')
            number = self.inventory.number_for(item)
            text = f'Press [{number}] to equip {ITEMS[item][0]}. Hold [E] to use. Using this item adds 10 health.' if number else f'No {ITEMS[item][0]} available'
        elif self.state == Stage.MATERIALS and self.inventory.selected_item != 'compass':
            text = 'Press [{compass_slot}] to equip Compass. Follow arrows and use [F] to pick up sticks and rock.'
        elif self.in_beacon_ring:
            text = 'You\'re inside the ring. Press [F] to finish the tutorial.'
        elif self.state == Stage.BEACON and self.inventory.selected_item == 'compass':
            text = 'Follow the red needle along the path. Press [F] once you\'re inside the turquoise ring.'
        elif self.state == Stage.COMBAT:
            text = 'Left click to attack, then immediately back before the dog bites.' if self.inventory.selected_item == 'spear' else 'Press [{spear_slot}] to equip spear. Left click attacks, then back away!'
        return title, text.format(**{f'{item}_slot': self.inventory.number_for(item) or '1-9'
                                    for item in ('food', 'water', 'spear', 'compass')})

    @property
    def in_beacon_ring(self):
        return (self.state == Stage.BEACON and self.active and
                math.hypot(self.camera.x-self.world.beacon[0], self.camera.z-self.world.beacon[2]) <= BEACON_RING_RADIUS)

    def action_coach(self):
        if not self.active or self.help_open:
            return None
        if self.crafting_open:
            expected = 'compass' if self.state == Stage.COMPASS else 'spear' if self.state == Stage.SPEAR else None
            if expected is None:
                return ActionCoach('close', 'Close menu [C]')
            if RECIPE_ORDER[self.selected_recipe] != expected:
                return ActionCoach('recipe', 'Choose '+ITEMS[expected][0])
            ready, _ = self.recipe_status(expected)
            return ActionCoach('craft', 'Press [Enter] to craft') if ready else ActionCoach('ingredients', 'Check the missing ingredients')
        if self.in_beacon_ring:
            return ActionCoach('finish', 'Press [F] to finish')
        item = None
        if self.state == Stage.CONSUME:
            item = next((item for item in ('food', 'water') if item not in self.consumed), None)
        elif self.state in (Stage.MATERIALS, Stage.BEACON):
            item = 'compass'
        elif self.state == Stage.COMBAT:
            item = 'spear'
        if item and self.inventory.number_for(item):
            number = self.inventory.number_for(item)
            if self.inventory.selected_item != item:
                return ActionCoach('slot', f'Press [{number}] to equip '+ITEMS[item][0], number-1)
            if item in ('food', 'water'):
                text = f'Hold [E]: using {round(100*self.use_progress/USE_DURATION)}%' if self.use_progress else 'Hold [E] until the bar fills'
                return ActionCoach('use', text, number-1)
        if self.state in (Stage.COMPASS, Stage.SPEAR):
            return ActionCoach('open', 'Press [C] to open crafting')
        return None

    def objective_direction(self):
        if not self.active or self.crafting_open or self.help_open or self.in_beacon_ring:
            return None
        targets = self._allowed_resources()
        if self.state == Stage.COMBAT:
            targets = (self.dog,) if self.dog else ()
        elif self.state == Stage.BEACON:
            if self.inventory.selected_item != 'compass':
                return None
            targets = self.entities.of_kind('beacon')
        targets = [target for target in targets if target.visible]
        if not targets:
            return None
        source = self.camera.x, self.camera.z
        target = min(targets, key=lambda entity: self.path_guide.route(source, (entity.x, entity.z))[1])
        goal = target.x, target.z
        direct_range = SPEAR_RANGE+2 if target.kind == 'dog' else INTERACTION_RANGE
        direct = math.dist(source, goal) <= direct_range and self.world.line_clear(*source, *goal)
        point = goal if direct else self.path_guide.next_waypoint(source, goal)
        bearing = math.atan2(point[0]-source[0], point[1]-source[1])
        relative = (bearing-self.camera.yaw+math.pi) % math.tau-math.pi
        names = {'can': 'Food can', 'bottle': 'Water bottle', 'stick': 'Stick', 'rock': 'Rock', 'dog': 'HOSTILE DOG', 'beacon': 'End beacon'}
        return ObjectiveDirection(target.id, names[target.kind], relative, math.dist(source, goal),
                                  len(targets), self.world.position(*point), target.kind == 'dog')

    def select_slot(self, number):
        changed = self.inventory.select_slot(number)
        if changed:
            self.cancel_use()
            item = self.inventory.selected_item
            self.notify('Equipped '+ITEMS[item][0] if item else
                        ('Empty hand' if number == 0 else f'Slot [{number}] is empty'), 1.8)
        else:
            self.notify('That slot is unavailable')
        return changed

    def cancel_use(self):
        self.use_progress = 0.0
        self.use_item = None
        self._use_latched = False

    def update_use(self, dt, held):
        item = self.inventory.selected_item
        if not held or not self.active or self.crafting_open or self.help_open:
            self.cancel_use()
            return False
        if self._use_latched:
            return False
        ready, reason = self.use_status()
        if not ready:
            self.notify(reason)
            self._use_latched = True
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

    def use_status(self):
        item = self.inventory.selected_item
        if item is None:
            return False, 'Select an item first' if self.inventory.selected_slot == 9 else 'No item available'
        if item not in ('food', 'water'):
            return False, 'Use materials in crafting [C]' if ITEMS[item][1] == 'Material' else 'This item is not consumable'
        if self.state < Stage.CONSUME:
            return False, 'Collect both supplies first'
        if self.camera.health >= self.camera.max_health and not (self.state == Stage.CONSUME and item not in self.consumed):
            return False, 'Health already full'
        return True, 'Hold [E]: +10 health' if self.camera.health < self.camera.max_health else 'Hold [E]: keep the scrap (health full)'

    def toggle_crafting(self):
        if not self.active:
            return False
        self.crafting_open = not self.crafting_open
        self.cancel_use()
        if self.crafting_open:
            self.selected_recipe = 1 if self.state == Stage.SPEAR else 0
        return True

    def recipe_status(self, recipe_id):
        recipe = RECIPES.get(recipe_id)
        if recipe is None:
            return False, 'Recipe unavailable'
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
        if not self.active or self.crafting_open or self.help_open:
            return None
        candidates = self._allowed_resources()
        if self.state == Stage.BEACON:
            candidates = self.entities.of_kind('beacon')
        nearby = [e for e in candidates if e.interactable and e.visible and
                  e.distance_to(self.camera.x, self.camera.z) <= INTERACTION_RANGE and
                  self.world.line_clear(self.camera.x, self.camera.z, e.x, e.z, .1)]
        return min(nearby, key=lambda e: (self._facing(e) < .5, e.distance_to(self.camera.x, self.camera.z)), default=None)

    def _facing(self, entity):
        dx, dz = entity.x-self.camera.x, entity.z-self.camera.z
        distance = math.hypot(dx, dz)
        return (dx*math.sin(self.camera.yaw)+dz*math.cos(self.camera.yaw))/distance if distance > 1e-6 else 1.0

    def attack_status(self):
        if self.inventory.selected_item != 'spear':
            number = self.inventory.number_for('spear')
            return False, f'Press [{number}] to equip spear' if number else 'Craft a spear first [C]'
        if self.dog is None:
            return False, 'No hostile target nearby'
        if self.attack_cooldown_timer > 0:
            return False, f'Attack ready in {self.attack_cooldown_timer:.1f}s'
        target = self.dog
        distance = target.distance_to(self.camera.x, self.camera.z)
        vertical = math.atan2(target.y+.6-self.camera.y, max(distance, .01))
        if distance > SPEAR_RANGE:
            return False, 'Move closer to the dog'
        if self._facing(target) < math.cos(math.radians(50)) or abs(vertical+self.camera.pitch) > math.radians(65):
            return False, 'Face the dog to attack'
        if not self.world.line_clear(self.camera.x, self.camera.z, target.x, target.z, .1):
            return False, 'A tree blocks the attack'
        return True, 'Left click to attack'

    def world_prompt(self):
        if not self.active or self.crafting_open or self.help_open:
            self._prompt_id = None
            return None
        target = self.interaction_target()
        combat = self.state == Stage.COMBAT and self.dog is not None
        if combat:
            target = self.dog
            limit = SPEAR_RANGE
        else:
            limit = INTERACTION_RANGE
        # Two thresholds. Boundary jitter can log off.
        if target is None or not target.visible or target.distance_to(self.camera.x, self.camera.z) > limit-(0 if target.id == self._prompt_id else .12):
            self._prompt_id = None
            return None
        if not self.world.line_clear(self.camera.x, self.camera.z, target.x, target.z, .1):
            self._prompt_id = None
            return None
        self._prompt_id = target.id
        if combat:
            ready, text = self.attack_status()
            title = 'Dog: back away!' if target.state == 'windup' else 'Hostile dog'
        else:
            ready = target.kind == 'beacon' or self.inventory.can_add_many(RESOURCE_LOOT[target.kind])
            text = ('Press [F] to finish' if target.kind == 'beacon' else 'Press [F] to pick up') if ready else 'Inventory full'
            title = {'can': 'Food can', 'bottle': 'Water bottle', 'stick': 'Stick', 'rock': 'Rock', 'beacon': 'End beacon'}[target.kind]
        return WorldPrompt(target.id, title, text, (target.x, target.y+target.visual_height+.3, target.z), ready)

    def handle_interaction(self):
        if not self.active or self.crafting_open or self.help_open:
            return False
        target = self.interaction_target()
        if target is None:
            self.notify({Stage.MOVEMENT: 'Finish the movement step first', Stage.LOOK: 'Look around with the mouse first',
                         Stage.CONSUME: 'Select supplies, then hold [E]', Stage.COMPASS: 'Open crafting with [C]',
                         Stage.SPEAR: 'Open crafting with [C]', Stage.COMBAT: 'Equip spear; left click attacks'}.get(self.state, 'Move closer to a marked item'))
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
            self.notify(' + '.join(f'+{qty} {ITEMS[item][0]}' for item, qty in loot.items()))
            self._progress()
        self._update_prompt()
        return True

    def _consume(self, item):
        if not self.active or item not in ('food', 'water') or self.inventory.selected_item != item:
            return False
        if self.state < Stage.CONSUME:
            self.notify('Grab both supplies first.')
            return False
        ready, reason = self.use_status()
        if not ready:
            self.notify(reason)
            return False
        scrap = self.inventory.consume_selected()
        if not scrap:
            self.notify('No ' + ITEMS[item][0] + ' left.')
            return False
        before = self.camera.health
        self.camera.health = min(self.camera.max_health, before+HEAL_AMOUNT)
        self.health_feedback, self.health_flash_timer = 'heal', .65
        self.consumed.add(item)
        self.notify(f'+{int(self.camera.health-before)} health | +1 {ITEMS[scrap][0]}')
        self._progress()
        self._update_prompt()
        return True

    def craft(self):
        if not self.active or not self.crafting_open or self.help_open:
            return False
        if not 0 <= self.selected_recipe < len(RECIPE_ORDER):
            self.notify('Select an available recipe')
            return False
        recipe = RECIPE_ORDER[self.selected_recipe]
        ready, reason = self.recipe_status(recipe)
        if not ready:
            self.notify(reason)
            return False
        if not self.inventory.craft(recipe):
            self.notify('Not enough mats or pack space.')
            return False
        self.notify(ITEMS[recipe][0]+' crafted')
        self._progress()
        self._update_prompt()
        return True

    def handle_attack(self):
        if not self.active or self.crafting_open or self.help_open:
            return False
        ready, reason = self.attack_status()
        if not ready:
            self.notify(reason, 1.2)
            return False
        self.attack_cooldown_timer = SPEAR_COOLDOWN
        self.attack_anim_timer = SPEAR_ANIMATION
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
                self.objective_flash_timer = 2.5
                self.notify('Dog defeated | Select compass', 3)
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
        self.notify(f'Stone spear crafted | Equip [{self.inventory.number_for("spear")}]', 3)

    def _progress(self):
        previous = self.state
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
        if self.state != previous:
            self.objective_flash_timer = 2.5

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
        prompt = self.world_prompt()
        self.interaction_prompt = prompt.text if prompt else None

    def update(self, dt):
        if self.crafting_open or self.help_open:
            return
        dt = max(0, min(dt, .1))
        self.elapsed += dt
        self.notification_timer = max(0, self.notification_timer-dt)
        self.objective_flash_timer = max(0, self.objective_flash_timer-dt)
        self.health_flash_timer = max(0, self.health_flash_timer-dt)
        self.attack_cooldown_timer = max(0, self.attack_cooldown_timer-dt)
        self.attack_anim_timer = max(0, self.attack_anim_timer-dt)
        x, z, yaw, pitch = self._last_pose
        if self.active:
            blocked = self.camera.sprint_blocked
            if blocked and not self._sprint_blocked:
                self.notify('Low stamina | Stop to recover', 2)
            self._sprint_blocked = blocked
            self.movement_distance += math.hypot(self.camera.x-x, self.camera.z-z)
            if self.state == Stage.LOOK:

                self.look_rotation_total += abs((self.camera.yaw-yaw+math.pi) % math.tau-math.pi)
                self.look_rotation_total += abs(self.camera.pitch-pitch)
            if self.dog:
                damage = self.dog.update(dt, self.camera, self.world)
                if damage:
                    self.camera.take_damage(damage)
                    self.health_feedback, self.health_flash_timer = 'damage', .65
                    self.notify(f'-{damage} health | Back away!', 2)
                    if self.camera.health <= 0:
                        self.state = Stage.DEAD
            self._progress()
            self._update_prompt()
        self._last_pose = self.camera.x, self.camera.z, self.camera.yaw, self.camera.pitch
