from enum import IntEnum
import math
import random

from engine import models
from engine.paths import PathNetwork
from engine.streaming import ForestStreaming,chunk_key
from engine.entity import Entity
from engine.guidance import ActionCoach, ObjectiveDirection
from engine.items import ITEMS, RECIPES, RUN_RECIPE_ORDER
from engine.level1 import Level1, Stage
from engine.markers import ObjectiveMarker,ground_arrow
from engine.prompts import WorldPrompt
from engine.survival import SurvivalRun, RunTree
from engine.run_config import RunConfig,WEAPONS
from engine.status import PoisonStatus


class Lesson(IntEnum):
    MOVEMENT = 1
    LOOK = 2
    SUPPLIES = 3
    CONSUME = 4
    COMPASS = 5
    MATERIALS = 6
    SPEAR = 7
    COMBAT = 8
    AXE_MATERIALS = 9
    AXE = 10
    TREE = 11
    INJURY = 12
    BANDAGE = 13
    USE = 14
    BEACON = 15
    COMPLETE = 16


LEGACY = {Lesson[name]: Stage[name] for name in
          ('MOVEMENT','LOOK','SUPPLIES','CONSUME','COMPASS','MATERIALS','SPEAR','COMBAT','BEACON','COMPLETE')}


class TutorialForest(ForestStreaming):
    bounds=(-36.,36.,-36.,36.)

    def __init__(self,seed=42):
        self.seed=seed
        self.axe_station_arc=70.+(sum(RECIPES['axe']['materials'].values())-1)*1.45
        self.paths=PathNetwork(seed,finish_distance=self.axe_station_arc+80.)
        points=[*self.paths.route,*(p for branch in self.paths.branches for p in branch)]
        self.bounds=(min(x for x,z in points)-10,max(x for x,z in points)+10,
                     min(z for x,z in points)-10,max(z for x,z in points)+10)
        self.spawn,self.beacon=self.position(*self.paths.route[0]),self.position(*self.paths.route[-1])
        self.encounter=self.position(*self.paths.at(64))
        self.resources=[(kind,self.position(*self.paths.at(distance))) for kind,distance in
                        (('can',9),('bottle',15),('stick',32),('stick',37),('rock',43))]
        self.original_resource_count=5
        self.extension_start=70.
        distance=self.extension_start
        for kind,count in RECIPES['axe']['materials'].items():
            for i in range(count):
                x,z=self.paths.at(distance)
                a,b=self.paths.at(distance-.2),self.paths.at(distance+.2)
                dx,dz=b[0]-a[0],b[1]-a[1];length=max(.001,math.hypot(dx,dz))
                offset=.65 if i%2 else -.65
                self.resources.append((kind,self.position(x+dz/length*offset,z-dx/length*offset)))
                distance+=1.45
        self.resource_index={}
        for kind,position in self.resources:
            self.resource_index.setdefault(chunk_key(position[0],position[2]),[]).append((kind,position))
        self._init_streaming()
        for x,z in self.paths.samples(8):
            key=chunk_key(x,z)
            for dz in (-1,0,1):
                for dx in (-1,0,1):
                    neighbour=(key[0]+dx,key[1]+dz)
                    if neighbour not in self.chunks:self._activate(self.generate_chunk(neighbour))
        self._approaches={}
        self._sites=tuple(site for site in self.trees if self.in_bounds(*site.position[::2],margin=-3.))
        candidates=sorted(self._sites,key=lambda site:math.dist(site.position[::2],self.paths.at(85)))
        chosen=None
        for site in candidates:
            approach=self.approach(site)
            if approach is not None:
                chosen=site;self.chop_position,self.tree_access=approach
                break
        if chosen is None:raise ValueError('No reachable tutorial tree')
        self.suggested_tree=chosen
        self._initial_chunks={key:(tuple(c.meshes),tuple(c.obstacles),c.packed) for key,c in self.chunks.items()}
        self._initial_meshes=tuple(self.meshes)
        self._initial_obstacles=tuple(self.obstacles)
        self.validation={'connected':all(self.is_walkable(x,z) for x,z in self.paths.samples()),
                         'compass_walk_metres':self.paths.lengths[-1]-self.axe_station_arc,
                         'shared_forest_generator':True,'trees':len(self._sites),'extension_pickups':9}
        if not self.validation['connected']:raise ValueError('Tutorial route blocked')

    def in_bounds(self,x,z,margin=0.):
        a,b,c,d=self.bounds
        return a+margin<=x<=b-margin and c+margin<=z<=d-margin

    def is_clearing(self,x,z):
        return (math.hypot(x-self.spawn[0],z-self.spawn[2])<3 or
                math.hypot(x-self.beacon[0],z-self.beacon[2])<3 or
                math.hypot(x-self.encounter[0],z-self.encounter[2])<2 or
                any(math.hypot(x-p[0],z-p[2])<1.4 for _,p in self.resources))

    def is_walkable(self,x,z,radius=.4):
        return self.in_bounds(x,z,radius) and super().is_walkable(x,z,radius)

    def approach(self,site):
        if site.key in self._approaches:return self._approaches[site.key]
        nearest=min(self.paths.samples(1.),key=lambda p:math.dist(p,site.position[::2]))
        heading=math.atan2(nearest[0]-site.position[0],nearest[1]-site.position[2])
        for delta in (0,.5,-.5,1.,-1.,1.5,-1.5,math.pi):
            angle=heading+delta;distance=site.obstacle.radius+1.1
            stand=(site.position[0]+math.sin(angle)*distance,site.position[2]+math.cos(angle)*distance)
            if self.is_walkable(*stand) and self.line_clear(*nearest,*stand,.4):
                self._approaches[site.key]=(stand,nearest)
                return stand,nearest
        self._approaches[site.key]=None
        return None

    def restore_tree(self):
        self.removed_trees.clear()
        for chunk in self.chunks.values():
            if not any(site.removed for site in chunk.trees):continue
            meshes,obstacles,packed=self._initial_chunks[chunk.key]
            chunk.meshes,chunk.obstacles,chunk.packed=list(meshes),list(obstacles),packed
            for site in chunk.trees:site.removed=False
            chunk.revision+=1
        self.render_revision+=1


class TutorialRun(Level1):
    is_survival = False
    is_expanded_tutorial = True
    recipes = RUN_RECIPE_ORDER
    item_meshes = SurvivalRun.item_meshes
    chop = SurvivalRun.chop
    finish_tree_fall = SurvivalRun.finish_tree_fall
    mark_removed = SurvivalRun.mark_removed
    _swing = SurvivalRun._swing

    def __init__(self, camera, seed=42):
        self.seed, self.config = seed, RunConfig('Easy','Short')
        super().__init__(camera, seed, TutorialForest(seed))
        self.axe_meshes = models.axe()
        self.held_props.update({'leaves':models.held_prop(models.leaves()),
                                'bandage':models.held_prop(models.bandage())})

    def reset(self):
        self.world.restore_tree()
        self.lesson = Lesson.MOVEMENT
        self._e_down = False
        super().reset()
        self.health_rng = random.Random(self.seed+92)
        self.poison = PoisonStatus()
        self.stats = {'collected':0,'crafted':0,'trees':0,'defeated':0}
        self.removed_objects,self.hostile_records,self.tree_chops,self.drops = set(),{},{},{}
        self._drop_serial = 0
        self._resource_meshes = {}
        self.beacon_commit = 0.
        self.completion_time = None
        self.lesson_since = 0.
        self.injury_applied = self.bandage_used = False
        self.history = [Lesson.MOVEMENT]
        resources = [e for e in self.entities.all() if e.kind in ('can','bottle','stick','rock')]
        for index,entity in enumerate(resources):
            entity.lesson = (Lesson.SUPPLIES if index<2 else Lesson.MATERIALS
                             if index<self.world.original_resource_count else Lesson.AXE_MATERIALS)
        self._objective_id=None
        for tree in self.world._sites:
            entity = RunTree(tree);entity.world_key = ('tree',*tree.key)
            self.entities.add(entity)
        self._update_prompt()

    @property
    def active(self):return super().active and self.camera.health>0

    @property
    def hostiles(self):return tuple(e for e in self.entities.of_kind('dog') if e.health>0)

    @property
    def expected_recipe(self):
        return {Lesson.COMPASS:'compass',Lesson.SPEAR:'spear',Lesson.AXE:'axe',Lesson.BANDAGE:'bandage'}.get(self.lesson)

    @property
    def lesson_heading(self):
        return 'BEACON REACHED' if self.in_beacon_ring else f'{min(15,int(self.lesson))}/15  {self.instruction[0]}'

    @property
    def in_beacon_ring(self):
        return self.lesson == Lesson.BEACON and super().in_beacon_ring

    @property
    def instruction(self):
        if self.state == Stage.DEAD:return 'GAME OVER','[R] retry | [Esc] title'
        if self.lesson in LEGACY:return super().instruction
        axe = self.inventory.number_for('axe') or '1-9'
        bandage = self.inventory.number_for('bandage') or '1-9'
        return {
            Lesson.AXE_MATERIALS:('AXE MATERIALS','Press [F] to collect 5 rocks and 4 sticks.'),
            Lesson.AXE:('CRAFT AN AXE','Open [C] and craft a stone axe.'),
            Lesson.TREE:('TIMBER TIME','Tree falling away. Leaves drop when it lands.' if self.tree_falls.live else
                         f'Press [{axe}] to equip your axe.' if self.inventory.selected_item!='axe' else 'Press [F] to chop any tree.'),
            Lesson.INJURY:('PRACTICE INJURY','Health set to 85 for bandage practice.'),
            Lesson.BANDAGE:('CRAFT A BANDAGE','Press [F] to pick up leaves.' if not self.inventory.has('leaves',RECIPES['bandage']['materials']['leaves']) else 'Open [C] and craft a bandage.'),
            Lesson.USE:('USE THE BANDAGE',f'Press [{bandage}] to equip bandages.' if self.inventory.selected_item!='bandage' else 'Hold [E] to use your bandage.'),
        }[self.lesson]

    def _set_lesson(self, lesson):
        if self.lesson == lesson:return
        self._objective_id=None
        self.lesson,self.lesson_since = lesson,self.elapsed
        self.state = LEGACY.get(lesson,Stage.BEACON)
        self.history.append(lesson)
        self.objective_flash_timer = 2.5
        if lesson == Lesson.LOOK:self.look_rotation_total = 0.
        if lesson == Lesson.COMBAT:self._spawn_dog()

    def _progress(self):
        if not self.active:return
        stage = self.lesson
        if stage == Lesson.MOVEMENT and self.movement_distance>=2:self._set_lesson(Lesson.LOOK)
        elif stage == Lesson.LOOK and self.look_rotation_total>=.45:self._set_lesson(Lesson.SUPPLIES)
        elif stage == Lesson.SUPPLIES and {'can','bottle'}<=self.collected:self._set_lesson(Lesson.CONSUME)
        elif stage == Lesson.CONSUME and {'food','water'}<=self.consumed:self._set_lesson(Lesson.COMPASS)
        elif stage == Lesson.COMPASS and self.inventory.has('compass'):self._set_lesson(Lesson.MATERIALS)
        elif stage == Lesson.MATERIALS and self.inventory.has('stick',2) and self.inventory.has('rock'):self._set_lesson(Lesson.SPEAR)
        elif stage == Lesson.SPEAR and self.inventory.has('spear'):self._set_lesson(Lesson.COMBAT)
        elif stage == Lesson.AXE_MATERIALS and all(self.inventory.has(item,qty) for item,qty in RECIPES['axe']['materials'].items()):self._set_lesson(Lesson.AXE)
        elif stage == Lesson.AXE and self.inventory.has('axe'):self._set_lesson(Lesson.TREE)
        elif stage == Lesson.TREE and self.stats['trees'] and not self.tree_falls.live:
            self._set_lesson(Lesson.INJURY)
            if not self.injury_applied:
                self.injury_applied = True
                before=self.camera.health
                self.camera.health=min(self.camera.max_health,85.)
                self.health_feedback='damage' if before>85 else 'heal'
                self.health_flash_timer=.65
                self.notify('Health set to 85 for practice. Craft a bandage.',5)
            self._set_lesson(Lesson.BANDAGE)
        elif stage == Lesson.BANDAGE and self.inventory.has('bandage'):self._set_lesson(Lesson.USE)
        elif stage == Lesson.USE and self.bandage_used:
            self._set_lesson(Lesson.BEACON)
            self.notify('Patched up. Hold the compass and follow its needle.',4)

    def cancel_use(self):
        held = getattr(self,'_e_down',False)
        super().cancel_use()
        self._use_latched = held

    def update_use(self,dt,held):
        self._e_down = held
        return super().update_use(dt,held)

    def sound(self,kind,radius):pass

    def recipe_status(self, recipe_id):
        if recipe_id != self.expected_recipe:return False,'Follow the current lesson'
        return SurvivalRun.recipe_status(self,recipe_id)

    def toggle_crafting(self):
        result = SurvivalRun.toggle_crafting(self)
        if result and self.crafting_open and self.expected_recipe:self.selected_recipe = self.recipes.index(self.expected_recipe)
        return result

    def craft(self):
        result = SurvivalRun.craft(self)
        if result:self._progress()
        return result

    def use_status(self):
        if self.inventory.selected_item == 'bandage':
            if self.lesson != Lesson.USE:return False,'Finish the bandage lesson first'
            return SurvivalRun.use_status(self)
        if self.lesson not in LEGACY:return False,'Use the bandage for this lesson'
        return super().use_status()

    def _consume(self,item):
        before = self.camera.health
        used = SurvivalRun._consume(self,item)
        if used:
            self.consumed.add(item)
            if item == 'bandage':self.bandage_used = self.camera.health>before
            self._progress()
        return used

    def _allowed_resources(self):
        return tuple(e for e in self.entities.all() if getattr(e,'lesson',None) == self.lesson)

    def interaction_target(self):
        if self.lesson in LEGACY and self.inventory.selected_item!='axe':return super().interaction_target()
        allowed_resources=self._allowed_resources()
        def allowed(target):
            return (target.kind=='tree' or target in allowed_resources or
                    target.kind=='dropped' and self.lesson>=Lesson.TREE or
                    target.kind=='beacon' and self.lesson==Lesson.BEACON)
        return SurvivalRun.interaction_target(self,allowed)

    def world_prompt(self):
        target = self.interaction_target()
        if self.lesson in LEGACY and (target is None or target.kind not in ('tree','dropped')):
            prompt=super().world_prompt()
            if prompt and prompt.ready and target and target.kind in ('can','bottle','stick','rock'):
                position=(target.x,target.y+target.visual_height+.08,target.z)
                return WorldPrompt(prompt.target_id,prompt.title,'Press [F] to pick up '+prompt.title.lower()+'.',position)
            return prompt
        if target is None:return None
        if target.kind == 'tree':
            from engine.run_config import TREE_CHOPS
            return WorldPrompt(target.id,f'Tree {target.chops}/{TREE_CHOPS}','Press [F] to chop this tree.',
                               (target.x,target.y+1.4,target.z),self.attack_status()[0])
        ready = self.inventory.can_add_many(SurvivalRun.loot(target))
        return WorldPrompt(target.id,'Leaves' if target.kind=='dropped' else ITEMS[target.kind][0],
                           ('Press [F] to pick up leaves.' if target.kind=='dropped' else 'Press [F] to pick up '+ITEMS[target.kind][0].lower()+'.') if ready else 'Pack full',
                           (target.x,target.y+target.visual_height+.08,target.z),ready)

    def handle_interaction(self):
        if not self.active or self.crafting_open or self.help_open:return False
        target = self.interaction_target()
        if target is None:self.notify('Follow the marked objective. [F] when close.');return False
        if target.kind == 'beacon':
            self._set_lesson(Lesson.COMPLETE)
            self.completion_time = self.elapsed
            self.cancel_use()
            self.effects.emit('beacon_activated',target.position)
            self.notify('Tutorial cleared. W.',5)
            return True
        if target.kind == 'tree':return self.chop(target)
        loot = SurvivalRun.loot(target)
        if not self.inventory.add_many(loot):self.notify('Pack full.');return False
        self.mark_removed(target)
        self.collected.add(target.kind)
        self.stats['collected'] += 1
        self.effects.emit('pickup',target.position)
        self.notify(' + '.join(f'+{qty} {ITEMS[item][0]}' for item,qty in loot.items()))
        self._progress()
        return True

    def attack_status(self,heavy=False):
        if self.inventory.selected_item == 'axe':return SurvivalRun.attack_status(self,heavy)
        return super().attack_status(heavy)

    def handle_attack(self,heavy=False):
        if self.inventory.selected_item == 'axe':
            if not self.active or self.crafting_open or self.help_open:return False
            return self._swing(heavy)
        target = self.dog
        result = super().handle_attack(heavy)
        if result and target and target.health<=0:
            self.stats['defeated'] += 1
            self.effects.emit('enemy_defeated',target.position,yaw=target.yaw,meshes=target.meshes,detail='dog')
            self._set_lesson(Lesson.AXE_MATERIALS)
            self.notify('Dog handled. Next up: axe crafting.',4)
        return result

    def _sync_entities(self):
        active = {getattr(e,'world_key',None) for e in self.entities.all()}
        for key,(position,item,quantity) in self.drops.items():
            if key in active:continue
            entity = Entity('dropped',*position,meshes=self.item_meshes(item),interactable=True)
            entity.loot,entity.world_key = {item:quantity},key
            self.entities.add(entity)

    def _targets(self):
        if self.lesson==Lesson.TREE:
            return tuple(e for e in self.entities.of_kind('tree') if not e.site.removed)
        if self.lesson==Lesson.BANDAGE:
            return self.entities.of_kind('dropped') if not self.inventory.has('leaves',RECIPES['bandage']['materials']['leaves']) else ()
        if self.lesson==Lesson.COMBAT:return (self.dog,) if self.dog else ()
        if self.lesson==Lesson.BEACON:return self.entities.of_kind('beacon')
        return self._allowed_resources()

    def objective_target(self):
        targets=self._targets()
        if not targets:return None
        nearby=self.interaction_target()
        if nearby in targets:self._objective_id=nearby.id
        current=self.entities.get(getattr(self,'_objective_id',None))
        if current in targets:return current
        targets=sorted(targets,key=lambda e:e.distance_to(self.camera.x,self.camera.z))
        for target in targets:
            if target.kind!='tree' or self.world.approach(target.site) is not None:
                self._objective_id=target.id
                return target
        return None

    def objective_markers(self):
        target=self.objective_target()
        return [ObjectiveMarker(target.id,'ring' if target.kind=='beacon' else 'arrow')] if target else []

    def objective_direction(self):
        if not self.active or self.crafting_open or self.help_open or self.lesson==Lesson.BEACON:return None
        target=self.objective_target()
        if target is None:return None
        goal=(target.x,target.z)
        source=(self.camera.x,self.camera.z)
        nearby_tree=target.kind=='tree' and target.distance_to(*source)<=WEAPONS['axe']['range']+target.site.obstacle.radius
        if target.kind=='tree' and not nearby_tree:
            approach=self.world.approach(target.site)
            if approach is not None:goal=approach[0]
        route,_=self.path_guide.route(source,goal)
        point=goal if nearby_tree else next((p for p in reversed([*route,goal]) if math.dist(source,p)>.3 and self.world.line_clear(*source,*p,.4)),goal)
        relative=(math.atan2(point[0]-source[0],point[1]-source[1])-self.camera.yaw+math.pi)%math.tau-math.pi
        names={'can':'Food can','bottle':'Water bottle','stick':'Stick','rock':'Rock','tree':'Any tree','dropped':'Leaves','dog':'Dog','beacon':'Beacon'}
        name=names[target.kind] if point==goal else 'Path to '+names[target.kind].lower()
        remaining=1 if target.kind=='tree' else len(self._targets())
        return ObjectiveDirection(target.id,name,relative,target.distance_to(*source),remaining,self.world.position(*point),target.kind=='dog')

    def ground_guidance(self):
        direction=self.objective_direction()
        if direction is None:return None
        return ground_arrow(self.world,(self.camera.x,self.camera.z),direction.waypoint[::2])

    def action_coach(self):
        if not self.active or self.help_open:return None
        if self.crafting_open:
            recipe = self.expected_recipe
            if recipe is None:return ActionCoach('close','Close [C]')
            return ActionCoach('recipe','Choose '+ITEMS[recipe][0]) if self.recipes[self.selected_recipe]!=recipe else ActionCoach('craft','Press [Enter]')
        if self.expected_recipe:return ActionCoach('open','Open crafting [C]')
        if self.lesson in LEGACY:return super().action_coach()
        item = 'axe' if self.lesson==Lesson.TREE else 'bandage' if self.lesson==Lesson.USE else None
        number = self.inventory.number_for(item) if item else None
        if number and self.inventory.selected_item!=item:return ActionCoach('slot',f'Press [{number}] to equip '+ITEMS[item][0].lower(),number-1)
        if self.lesson==Lesson.USE:return ActionCoach('use','Hold [E]',(number or 1)-1)
        return None

    def update(self,dt):
        if self.crafting_open or self.help_open:return
        if self.camera.health<=0:self.confirm_death()
        dt = max(0.,min(.25,dt))
        if not self.active:self.effects.update(dt,self.entities);return
        count = max(1,math.ceil(dt/(1/60)))
        for _ in range(count):
            step = dt/count
            self.tree_falls.update(step,self)
            if not self.active:break
            super().update(step)
            if not self.active:break


# Older tools still know this alias. Same forest, fewer identity crises.
WorkshopWorld = TutorialForest
