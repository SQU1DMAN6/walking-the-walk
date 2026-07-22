class Vec3:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def copy(self):
        return Vec3(
            self.x, self.y, self.z
        )

