import math
import random


def segment_distance(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dz * dz
    t = max(0.0, min(1.0, ((x - a[0]) * dx + (z - a[1]) * dz) / length2)) if length2 else 0
    return math.hypot(x - a[0] - t * dx, z - a[1] - t * dz)


def curve(anchors):
    points = []
    extended = [anchors[0], *anchors, anchors[-1]]
    for i in range(1, len(extended) - 2):
        a, b, c, d = extended[i - 1:i + 3]
        steps = max(8, math.ceil(math.dist(b, c) / .8))
        for j in range(steps):
            t = j / steps
            points.append(tuple(.5 * (2 * b[k] + (-a[k] + c[k]) * t
                                     + (2*a[k] - 5*b[k] + 4*c[k] - d[k]) * t*t
                                     + (-a[k] + 3*b[k] - 3*c[k] + d[k]) * t*t*t)
                                for k in range(2)))
    return [*points, anchors[-1]]


class PathNetwork:
    half_width = 2.1

    def __init__(self, seed=42):
        rng = random.Random(seed)
        anchors = [(-24, 25), (-19, 17), (-9, 17), (-5, 9), (-13, 1),
                   (-7, -9), (5, -10), (14, -17), (8, -26), (24, -27)]
        anchors = [p if i in (0, len(anchors)-1) else
                   (p[0] + rng.uniform(-1, 1), p[1] + rng.uniform(-1, 1))
                   for i, p in enumerate(anchors)]
        self.route = curve(anchors)
        self.lengths = [0.0]
        for a, b in zip(self.route, self.route[1:]):
            self.lengths.append(self.lengths[-1] + math.dist(a, b))
        self.branches = [curve([self.route[30], (4, 20), (14, 14)]),
                         curve([self.route[75], (-22, -16), (-26, -24)])]
        self.segments = [(a, b) for line in [self.route, *self.branches]
                         for a, b in zip(line, line[1:])]

    def distance(self, x, z):
        return min(segment_distance(x, z, a, b) for a, b in self.segments)

    def visual_width(self, x, z):

        return self.half_width + .30 + .22 * math.sin(x * 1.3 + z * .7)

    def on_path(self, x, z):
        return self.distance(x, z) <= self.visual_width(x, z)

    def at(self, distance):
        distance = max(0, min(self.lengths[-1], distance))
        for i in range(1, len(self.lengths)):
            if distance <= self.lengths[i]:
                t = (distance - self.lengths[i-1]) / (self.lengths[i] - self.lengths[i-1])
                a, b = self.route[i-1:i+1]
                return (a[0] + t*(b[0]-a[0]), a[1] + t*(b[1]-a[1]))
        return self.route[-1]

    def nearest_route_index(self, x, z):
        return min(range(len(self.route)), key=lambda i: math.hypot(x-self.route[i][0], z-self.route[i][1]))

    def samples(self, spacing=.25):
        count = math.ceil(self.lengths[-1] / spacing)
        return [self.at(i * self.lengths[-1] / count) for i in range(count + 1)]
