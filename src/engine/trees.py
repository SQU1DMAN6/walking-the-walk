import math
import random

import numpy as np

from engine.foliage import BranchCloud, LeafCloud
from engine.mesh import Mesh

RINGS = {
    sides: tuple(
        (math.cos(i * math.tau / sides), math.sin(i * math.tau / sides))
        for i in range(sides)
    )
    for sides in (3, 5, 7)
}


def _merge(parts, colour):
    vertices, faces, colours = [], [], []
    for points, triangles, tint in parts:
        offset = len(vertices)
        vertices.extend(points)
        faces.extend((a + offset, b + offset, c + offset) for a, b, c in triangles)
        colours.extend([tint] * len(points))
    return Mesh(vertices, faces, colour, (0, 0, 0), vertex_colours=colours)


def _tube(centres, radii, colour, sides=5):
    points = []
    for index, (centre, radius) in enumerate(zip(centres, radii)):
        a, b = centres[max(0, index - 1)], centres[min(len(centres) - 1, index + 1)]
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        axis = (dx / length, dy / length, dz / length)
        norm = math.hypot(dx, dz)
        side = (dz / norm, 0, -dx / norm) if norm > 0.00001 else (1, 0, 0)
        up = (
            axis[1] * side[2],
            axis[2] * side[0] - axis[0] * side[2],
            -axis[1] * side[0],
        )
        for c, s in RINGS[sides]:
            points.append(
                (
                    centre[0] + radius * (c * side[0] + s * up[0]),
                    centre[1] + radius * s * up[1],
                    centre[2] + radius * (c * side[2] + s * up[2]),
                )
            )
    faces = []
    for ring in range(len(centres) - 1):
        for i in range(sides):
            a = ring * sides + i
            b = ring * sides + (i + 1) % sides
            faces.extend(((a, b, a + sides), (b, b + sides, a + sides)))
    for i in range(1, sides - 1):
        end = (len(centres) - 1) * sides
        faces.extend(((0, i + 1, i), (end, end + i, end + i + 1)))
    return points, faces, colour


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def forest_tree(position, seed, height=6.5, radius=0.35, density=0.5):
    rng = random.Random(seed)
    bark = (rng.randint(89, 114), rng.randint(65, 83), rng.randint(40, 56))
    turn = rng.uniform(0, math.tau)
    lean = rng.uniform(0.12, 0.5)
    centres = [
        (math.sin(turn + t) * lean * t, height * t, math.cos(turn + t) * lean * t)
        for t in (0, 0.2, 0.4, 0.6, 0.8, 1)
    ]
    trunk = _merge(
        [
            _tube(
                centres,
                [radius * v for v in (1, 0.87, 0.68, 0.46, 0.23, 0.04)],
                bark,
                7,
            )
        ],
        bark,
    )
    wood, shoots = [], []

    def limb(points, radii, tier):
        for a, b, r0, r1 in zip(points, points[1:], radii, radii[1:]):
            wood.append((*a, *(y - x for x, y in zip(a, b)), r0, r1, tier, *bark))

    spread = rng.uniform(0.29, 0.44) * height
    lift = rng.uniform(0.15, 0.32) * height
    crown_base = rng.uniform(0.30, 0.49)
    crown_taper = rng.uniform(-0.1, 0.45)
    limbs = rng.randint(6, 8)
    for i in range(limbs):
        angle = turn + i * 2.399963 + rng.uniform(-0.4, 0.4)
        t = min(
            0.92,
            crown_base
            + (0.9 - crown_base) * i / (limbs - 1)
            + rng.uniform(-0.025, 0.025),
        )
        ring = min(4, int(t * 5))
        root = _mix(centres[ring], centres[ring + 1], t * 5 - ring)
        reach = spread * rng.uniform(0.7, 1.0) * (1 - crown_taper * (i / (limbs - 1)))
        end = (
            root[0] + math.sin(angle) * reach,
            root[1] + lift * rng.uniform(0.65, 1.15),
            root[2] + math.cos(angle) * reach,
        )
        middle = _mix(root, end, 0.5)
        middle = (middle[0], middle[1] - 0.18, middle[2])
        width = radius * (1 - t) * 0.65
        limb([root, middle, end], [width, width * 0.57, width * 0.13], 0)
        for sign in (-1, 0, 1):
            fork_angle = angle + sign * rng.uniform(0.45, 0.9)
            start = (
                _mix(root, middle, 0.8)
                if sign == 0
                else _mix(middle, end, rng.uniform(0.35, 0.65))
            )
            hub = middle if sign == 0 else end
            tip = (
                hub[0] + math.sin(fork_angle) * reach * 0.32,
                hub[1] + rng.uniform(0.25, 0.7),
                hub[2] + math.cos(fork_angle) * reach * 0.32,
            )
            limb(
                [start, _mix(start, tip, 0.5), tip],
                [width * 0.42, width * 0.23, width * 0.05],
                1,
            )
            for j in range(4):
                base = _mix(start, tip, 0.25 + j * 0.25)
                heading = fork_angle + (-1 if j % 2 else 1) * rng.uniform(0.55, 1.25)
                shoot = (
                    base[0] + math.sin(heading) * rng.uniform(0.45, 0.7),
                    base[1] + rng.uniform(0.15, 0.45),
                    base[2] + math.cos(heading) * rng.uniform(0.45, 0.7),
                )
                limb([base, shoot], [width * 0.13, width * 0.015], 2)
                shoots.append((base, shoot, heading))
    branches = BranchCloud(wood, position)
    # One instance per leaf. The GPU handles the origami.
    leaf_rng = np.random.default_rng(seed & 0xFFFFFFFFFFFFFFFF)
    count = len(shoots) * 10
    starts = np.repeat(np.array([v[0] for v in shoots]), 10, axis=0)
    ends = np.repeat(np.array([v[1] for v in shoots]), 10, axis=0)
    headings = np.repeat(np.array([v[2] for v in shoots]), 10)
    t = np.tile(np.repeat(np.linspace(0.15, 0.95, 5), 2), len(shoots))
    bases = starts + (ends - starts) * t[:, None]
    angles = headings + np.tile([-1, 1], count // 2) * leaf_rng.uniform(0.5, 1.5, count)
    lengths = leaf_rng.uniform(0.5, 0.85, count)
    axes = np.column_stack(
        (
            np.sin(angles) * lengths,
            leaf_rng.uniform(-0.15, 0.5, count) * lengths,
            np.cos(angles) * lengths,
        )
    )
    widths = leaf_rng.uniform(0.16, 0.27, count)
    sides = np.column_stack(
        (
            np.cos(angles) * widths,
            leaf_rng.uniform(-0.2, 0.2, count) * widths,
            -np.sin(angles) * widths,
        )
    )
    colours = leaf_rng.uniform(
        (32, 105 + int(density * 8), 34), (62, 155 + int(density * 8), 67), (count, 3)
    )
    instances = np.column_stack((bases, axes, sides, colours)).astype(np.float32)
    instances = instances[leaf_rng.permutation(count)]
    foliage = [
        LeafCloud(instances[::2], position),
        LeafCloud(instances[1::2], position),
    ]
    trunk.position = position
    return [trunk, branches, *foliage]
