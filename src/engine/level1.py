"""Level 1 game logic for Walking the Walk."""
import math
import random

from engine.worldgen import (
    get_terrain_height,
    create_tree,
    create_bush,
    create_rock,
    create_spinifex,
    generate_terrain,
    create_branch,
    create_spear,
)
from engine.emu import Emu

WORLD_SEED = 42
TERRAIN_HEIGHT_SCALE = 1.5

STATE_MOVEMENT = 0
STATE_LOOKING = 1
STATE_INTERACTION = 2
STATE_SPEAR = 3
STATE_COMBAT = 4
STATE_COMPLETION = 5
STATE_DEATH = 6

INTERACTION_RANGE = 3.0
ATTACK_RANGE = 2.5
ATTACK_DURATION = 0.4
ATTACK_COOLDOWN = 0.6
SPEAR_DAMAGE = 25
EMU_HEALTH = 50
EMU_DAMAGE = 10
EMU_DETECTION_RANGE = 25.0
EMU_ATTACK_RANGE = 2.0


class Level1:
    """Manages Level 1 state and progression."""
    
    def _spawn_player(self):
        """Reset the player to the level start, facing the tutorial path
        (objectives lie toward negative z)."""
        self.camera.x = 0.0
        self.camera.z = -2.0
        self.camera.y = get_terrain_height(
            self.camera.x, self.camera.z, WORLD_SEED, TERRAIN_HEIGHT_SCALE
        ) + self.camera.eye_height
        self.camera.yaw = math.pi   # face -z (toward branch/tree/spear/clearing)
        self.camera.pitch = 0.0

    def __init__(self, camera):
        self.camera = camera
        self.state = STATE_MOVEMENT
        self.player_health = 100
        self.player_stamina = 100
        self.inventory_branch = 0
        self.has_spear = False
        self.spear_equipped = False
        self.level_complete = False
        
        self.movement_distance = 0.0
        self.look_rotation_total = 0.0
        self.branch_collected = False
        self.tree_examined = False
        self.spear_acquired = False
        self.attack_cooldown_timer = 0.0
        self.attack_anim_timer = 0.0
        
        self.emu_alive = True
        self.emu_health = EMU_HEALTH
        self.emu_x = 5.0
        self.emu_y = 0.0
        self.emu_z = -60.0  # near the final clearing landmark
        self.emu_state = "idle"
        self.emu_attack_cooldown = 0.0
        
        self.notification = None
        self.notification_timer = 0.0
        self.interaction_prompt = None
        
        self.world_meshes = []
        self.terrain_mesh = None
        self.branch_pos = None
        self.tree_pos = None
        self.spear_pos = None
        self.landmark_pos = None
        self.emu = None
        self._generate_world()
        self._spawn_player()
    
    def _generate_world(self):
        """Generate the procedural Level 1 world."""
        rng = random.Random(WORLD_SEED)
        terrain_size = 100
        
        # Generate terrain mesh (flip winding so normals face up;
        # generate_terrain emits downward-facing triangles which the
        # renderer's backface culler would discard)
        _terr = generate_terrain(
            terrain_size, terrain_size, 30, WORLD_SEED, TERRAIN_HEIGHT_SCALE,
            colour=(220, 170, 100)
        )
        _terr.faces = [(a, c, b) for (a, b, c) in _terr.faces]
        self.terrain_mesh = _terr
        
        # Add tutorial props: wooden branch, a large tree, and a stone-tipped spear.
        # All positions use the actual terrain height so items sit on the ground.
        self.branch_pos = (8.0, get_terrain_height(8.0, -10.0, WORLD_SEED, TERRAIN_HEIGHT_SCALE), -10.0)
        self.tree_pos = (-5.0, get_terrain_height(-5.0, -20.0, WORLD_SEED, TERRAIN_HEIGHT_SCALE), -20.0)
        self.spear_pos = (12.0, get_terrain_height(12.0, -30.0, WORLD_SEED, TERRAIN_HEIGHT_SCALE), -30.0)
        self.landmark_pos = (0.0, get_terrain_height(0.0, -60.0, WORLD_SEED, TERRAIN_HEIGHT_SCALE), -60.0)

        # Build explicit meshes for the collected/usable props so they render
        # as real objects rather than disappearing after generation.
        if self.branch_pos is not None:
            bx, by, bz = self.branch_pos
            self.branch_mesh = create_branch(
                (bx, by, bz),
                (bx + 0.5, by, bz - 0.4),
                0.05,
                (160, 120, 70),
            )
        if self.spear_pos is not None:
            sx, sy, sz = self.spear_pos
            self.spear_meshes = create_spear(
                (sx, sy, sz),
                (sx + 0.9, sy, sz - 0.7),
                (sx + 0.95, sy + 0.10, sz - 0.75),
            )
        
        for pos in [self.branch_pos, self.tree_pos, self.spear_pos, self.landmark_pos]:
            y = get_terrain_height(pos[0], pos[2], WORLD_SEED, TERRAIN_HEIGHT_SCALE)
            if pos == self.branch_pos:
                self.branch_pos = (pos[0], y, pos[2])
            elif pos == self.tree_pos:
                self.tree_pos = (pos[0], y, pos[2])
            elif pos == self.spear_pos:
                self.spear_pos = (pos[0], y, pos[2])
            elif pos == self.landmark_pos:
                self.landmark_pos = (pos[0], y, pos[2])
        
        for i in range(40):
            tx = rng.uniform(-terrain_size/2 + 5, terrain_size/2 - 5)
            tz = rng.uniform(-terrain_size/2 + 5, terrain_size/2 - 5)
            ty = get_terrain_height(tx, tz, WORLD_SEED, TERRAIN_HEIGHT_SCALE)
            if ty < -1.5:
                continue
            self.world_meshes.extend(create_tree((tx, ty, tz), WORLD_SEED + i * 7))
        
        for i in range(100):
            bx = rng.uniform(-terrain_size/2 + 2, terrain_size/2 - 2)
            bz = rng.uniform(-terrain_size/2 + 2, terrain_size/2 - 2)
            by = get_terrain_height(bx, bz, WORLD_SEED, TERRAIN_HEIGHT_SCALE)
            self.world_meshes.append(create_bush((bx, by, bz), WORLD_SEED + i * 13 + 1000))
        
        for i in range(30):
            rx = rng.uniform(-terrain_size/2 + 2, terrain_size/2 - 2)
            rz = rng.uniform(-terrain_size/2 + 2, terrain_size/2 - 2)
            ry = get_terrain_height(rx, rz, WORLD_SEED, TERRAIN_HEIGHT_SCALE)
            self.world_meshes.append(create_rock((rx, ry, rz), WORLD_SEED + i * 19 + 2000))
        
        for i in range(80):
            sx = rng.uniform(-terrain_size/2 + 2, terrain_size/2 - 2)
            sz = rng.uniform(-terrain_size/2 + 2, terrain_size/2 - 2)
            sy = get_terrain_height(sx, sz, WORLD_SEED, TERRAIN_HEIGHT_SCALE)
            self.world_meshes.append(create_spinifex((sx, sy, sz), WORLD_SEED + i * 31 + 3000))
    
    def _dist_to(self, pos):
        dx = self.camera.x - pos[0]
        dz = self.camera.z - pos[2]
        return math.sqrt(dx * dx + dz * dz)
    
    def handle_attack(self):
        if not self.spear_equipped:
            self.notification = "No weapon equipped!"
            self.notification_timer = 1.5
            return
        if self.attack_cooldown_timer > 0:
            return
        if self.emu is None or not self.emu_alive:
            self.notification = "Nothing to attack."
            self.notification_timer = 1.0
            return
        self.attack_anim_timer = ATTACK_DURATION
        self.attack_cooldown_timer = ATTACK_COOLDOWN
        dist = math.sqrt((self.camera.x - self.emu.x) ** 2 + (self.camera.z - self.emu.z) ** 2)
        if dist < ATTACK_RANGE:
            self.emu.health -= SPEAR_DAMAGE
            self.notification = "Hit! Emu health: %d" % self.emu.health
            self.notification_timer = 1.5
            if self.emu.health <= 0:
                self.emu_alive = False
                self.emu.state = "dead"
                self.notification = "Emu defeated!"
                self.notification_timer = 3.0
        else:
            self.notification = "Nothing in range."
            self.notification_timer = 1.0
    
    def _update_emu(self, dt):
        if not self.emu_alive:
            return
        dist = math.sqrt((self.camera.x - self.emu_x) ** 2 + (self.camera.z - self.emu_z) ** 2)
        if self.emu_state == "idle":
            if dist < EMU_DETECTION_RANGE:
                self.emu_state = "chase"
                self.notification = "Emu is chasing you!"
                self.notification_timer = 2.0
        elif self.emu_state == "chase":
            angle = math.atan2(self.camera.z - self.emu_z, self.camera.x - self.emu_x)
            self.emu_x += math.cos(angle) * 4.0 * dt
            self.emu_z += math.sin(angle) * 4.0 * dt
            if dist < EMU_ATTACK_RANGE:
                self.emu_state = "attack"
                self.emu_attack_cooldown = 1.0
        elif self.emu_state == "attack":
            if dist > EMU_ATTACK_RANGE * 1.5:
                self.emu_state = "chase"
            else:
                self.emu_attack_cooldown -= dt
                if self.emu_attack_cooldown <= 0:
                    self.player_health -= EMU_DAMAGE
                    self.notification = "Emu attacks! -%d health" % EMU_DAMAGE
                    self.notification_timer = 2.0
                    self.emu_attack_cooldown = 1.5
                    if self.player_health <= 0:
                        self.state = STATE_DEATH
    
    def _check_progression(self):
        if self.state == STATE_MOVEMENT:
            if self.movement_distance > 2.0:
                self.state = STATE_LOOKING
        elif self.state == STATE_LOOKING:
            if self.look_rotation_total > 20.0:
                self.state = STATE_INTERACTION
        elif self.state == STATE_INTERACTION:
            if self.branch_collected and self.tree_examined:
                self.state = STATE_SPEAR
        elif self.state == STATE_SPEAR:
            if self.spear_acquired:
                self.state = STATE_COMBAT
        elif self.state == STATE_COMBAT:
            if not self.emu_alive:
                self.state = STATE_COMPLETION
        elif self.state == STATE_COMPLETION:
            if self._dist_to(self.landmark_pos) < 3.0:
                self.level_complete = True
    
    def _update_prompt(self):
        self.interaction_prompt = None
        if self.state == STATE_INTERACTION:
            if not self.branch_collected and self._dist_to(self.branch_pos) < INTERACTION_RANGE:
                self.interaction_prompt = "F  PICK UP BRANCH"
            elif self.branch_collected and not self.tree_examined and self._dist_to(self.tree_pos) < INTERACTION_RANGE:
                self.interaction_prompt = "F  EXAMINE TREE"
        elif self.state == STATE_SPEAR:
            if not self.spear_acquired and self._dist_to(self.spear_pos) < INTERACTION_RANGE:
                self.interaction_prompt = "F  PICK UP SPEAR"
    
    def handle_interaction(self):
        if self.state == STATE_INTERACTION:
            if not self.branch_collected and self._dist_to(self.branch_pos) < INTERACTION_RANGE:
                self.branch_collected = True
                self.inventory_branch = 1
                self.notification = "BRANCH COLLECTED"
                self.notification_timer = 3.0
            elif self.branch_collected and not self.tree_examined and self._dist_to(self.tree_pos) < INTERACTION_RANGE:
                self.tree_examined = True
                self.notification = "This tree looks useful."
                self.notification_timer = 3.0
        elif self.state == STATE_SPEAR:
            if not self.spear_acquired and self._dist_to(self.spear_pos) < INTERACTION_RANGE:
                self.spear_acquired = True
                self.has_spear = True
                self.spear_equipped = True
                self.notification = "SPEAR ACQUIRED - A wild emu approaches!"
                self.notification_timer = 4.0
                # Spawn emu only after spear is picked up
                self.emu = Emu(self.emu_x, self.emu_y, self.emu_z, seed=WORLD_SEED + 1000, aggressive=True)
                self.emu.health = EMU_HEALTH
                self.emu.kick_damage = EMU_DAMAGE
    
    def update(self, dt):
        if self.emu is not None and self.emu_alive and not self.level_complete:
            self.emu.update(dt, self.camera.x, self.camera.z)
            self.emu.y = get_terrain_height(
                self.emu.x, self.emu.z, WORLD_SEED, TERRAIN_HEIGHT_SCALE)
            # Check for emu attack damage
            damage = self.emu.take_hit()
            if damage > 0:
                self.player_health -= damage
                self.notification = "Emu kicks you! -%d health" % int(damage)
                self.notification_timer = 2.0
                if self.player_health <= 0:
                    self.player_health = 0
                    self.state = STATE_DEATH
        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= dt
        if self.attack_anim_timer > 0:
            self.attack_anim_timer -= dt
        if self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.notification = None
        self._check_progression()
        self._update_prompt()
    
    def get_objective_position(self):
        """Get the position of the current objective for arrow guidance."""
        if self.state == STATE_INTERACTION:
            if not self.branch_collected:
                return self.branch_pos
            elif not self.tree_examined:
                return self.tree_pos
        elif self.state == STATE_SPEAR:
            if not self.spear_acquired:
                return self.spear_pos
        elif self.state == STATE_COMPLETION:
            return self.landmark_pos
        elif self.state == STATE_COMBAT:
            if self.emu is not None and self.emu_alive:
                return (self.emu.x, self.emu.y, self.emu.z)
        return None
    
    def reset(self):
        self._spawn_player()
        self.state = STATE_MOVEMENT
        self.player_health = 100
        self.player_stamina = 100
        self.inventory_branch = 0
        self.has_spear = False
        self.spear_equipped = False
        self.level_complete = False
        self.movement_distance = 0.0
        self.look_rotation_total = 0.0
        self.branch_collected = False
        self.tree_examined = False
        self.spear_acquired = False
        self.attack_cooldown_timer = 0.0
        self.attack_anim_timer = 0.0
        self.emu_alive = True
        self.emu = None