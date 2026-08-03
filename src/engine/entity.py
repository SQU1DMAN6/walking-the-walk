"""Common entity system shared by all wildlife."""
import math


class Entity:
    """Base class for all living things in the world."""

    def __init__(self, x, y, z, speed=2.0, detection_range=8.0):
        self.x = x
        self.y = y
        self.z = z
        self.speed = speed
        self.detection_range = detection_range
        self.state = "idle"
        self.yaw = 0.0

    def distance_to(self, px, pz):
        dx = px - self.x
        dz = pz - self.z
        return math.sqrt(dx * dx + dz * dz)

    def update(self, dt, player_x, player_z):
        """Update behaviour based on state."""

    def meshes(self):
        """Return a list of (mesh, x, y, z, yaw) for rendering."""
        return []
