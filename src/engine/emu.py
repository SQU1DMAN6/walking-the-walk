"""Emu wildlife system — idle → roaming → detect player → react (flee)."""
import math
import random

from engine.entity import Entity
from engine.mesh import Mesh


def create_emu_meshes(seed):
    """Build the low-poly meshes for an emu (body + head + legs + beak).

    Returns a list of Mesh objects in local space, feet centred near origin.
    """
    rng = random.Random(seed)
    # Brown shades
    body_colour = (
        int(rng.uniform(80, 110)),
        int(rng.uniform(60, 85)),
        int(rng.uniform(30, 50)),
    )
    neck_colour = (
        int(rng.uniform(70, 100)),
        int(rng.uniform(85, 115)),
        int(rng.uniform(70, 100)),
    )
    leg_colour = (110, 95, 75)

    meshes = []

    # Body: flattened ellipsoid via an 8-vertex prism
    bw = 0.55
    bh = 0.6
    bd = 0.3
    body_verts = [
        (-bw, 0.0, 0.0),           # 0 back
        ( bw, -bd*0.5, -bd*0.3),   # 1 front-bottom
        ( bw, bh*0.6, -bd*0.1),    # 2 front-top
        ( 0.0, bh, -bd*0.2),       # 3 top-back
        (-bw*0.7, 0.0, -bd),       # 4 lower-left
        ( bw*0.6, -bd*0.4, -bd*0.8), # 5 front-left
    ]
    body_faces = [
        (0, 1, 2), (0, 2, 3),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 2), (2, 5, 3),
        (0, 3, 4), (3, 4, 5),
    ]
    meshes.append(Mesh(body_verts, body_faces, body_colour, (0, 0, 0)))

    # Neck + head: bent cylinder
    neck_verts = [
        (0.18, 0.6, -0.1),
        (0.28, 0.6, -0.1),
        (0.28, 1.0, -0.12),
        (0.18, 1.0, -0.12),
        (0.16, 1.0, -0.05),
        (0.30, 1.0, -0.05),
        (0.30, 1.25, -0.1),
        (0.16, 1.25, -0.1),
    ]
    neck_faces = [
        (0, 1, 2), (0, 2, 3),
        (3, 2, 6), (3, 6, 7),
        (0, 3, 7), (0, 7, 4),
        (1, 5, 6), (1, 6, 2),
        (4, 7, 6), (4, 6, 5),
    ]
    meshes.append(Mesh(neck_verts, neck_faces, neck_colour, (0, 0, 0)))

    # Beak: small wedge at head front
    beak_verts = [
        (0.18, 1.18, -0.05),
        (0.30, 1.18, -0.05),
        (0.24, 1.10, 0.0),
        (0.24, 1.28, 0.0),
    ]
    beak_faces = [
        (0, 1, 2),
        (0, 3, 1),
        (0, 2, 3),
        (1, 3, 2),
    ]
    meshes.append(Mesh(beak_verts, beak_faces, (180, 150, 90), (0, 0, 0)))

    # Legs: two small prisms
    leg_verts = [
        (-0.05, 0.0, -0.1),
        (0.05, 0.0, -0.1),
        (0.05, 0.0, 0.05),
        (-0.05, 0.0, 0.05),
        (-0.03, 0.45, -0.05),
        (0.07, 0.45, -0.05),
        (0.07, 0.45, 0.05),
        (-0.03, 0.45, 0.05),
    ]
    leg_faces = [
        (0, 1, 2), (0, 2, 3),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
        (4, 5, 6), (4, 6, 7),
    ]
    mesh = Mesh(leg_verts, leg_faces, leg_colour, (0, 0, 0))
    meshes.append(mesh)

    return meshes


class Emu(Entity):
    """An emu that roams, detects the player and flees."""

    def __init__(self, x, y, z, seed=0):
        super().__init__(x, y, z, speed=2.6, detection_range=9.0)
        self.rng = random.Random(seed)
        self.state = "idle"
        self.timer = 0.0
        self.flee_yaw = 0.0
        self.meshes = create_emu_meshes(seed)
        # Facing direction
        self.yaw = self.rng.uniform(0, math.pi * 2)

    def update(self, dt, player_x, player_z):
        dist = self.distance_to(player_x, player_z)

        # State machine
        if dist < self.detection_range:
            self.state = "react" if dist < 5.0 else "detect"
        elif self.state in ("detect", "react"):
            self.state = "idle"

        if self.state in ("detect", "react"):
            # Flee away from player
            dx = self.x - player_x
            dz = self.z - player_z
            if dx == 0 and dz == 0:
                dx = 0.1
            self.flee_yaw = math.atan2(dz, dx)
            spd = self.speed * (1.8 if self.state == "react" else 1.3)
            self.x += math.sin(self.flee_yaw) * spd * dt
            self.z += math.cos(self.flee_yaw) * spd * dt
            self.yaw = self.flee_yaw
        else:
            # Idle / roam
            self.timer -= dt
            if self.timer <= 0.0:
                if self.rng.random() < 0.3:
                    self.state = "roam"
                    self.yaw = self.rng.uniform(0, math.pi * 2)
                    self.timer = self.rng.uniform(1.0, 3.0)
                else:
                    self.state = "idle"
                    self.timer = self.rng.uniform(1.5, 4.0)

            if self.state == "roam":
                self.x += math.sin(self.yaw) * self.speed * 0.5 * dt
                self.z += math.cos(self.yaw) * self.speed * 0.5 * dt

        # Keep emus roughly near spawn (don't wander off the world)
        if abs(self.x) > 48:
            self.x = 48 * (1.0 if self.x > 0 else -1.0)
        if abs(self.z) > 48:
            self.z = 48 * (1.0 if self.z > 0 else -1.0)

    def render_meshes(self):
        """Return list of (mesh, x, y, z, yaw) for dynamic rendering."""
        return [(m, self.x, self.y, self.z, self.yaw) for m in self.meshes]
