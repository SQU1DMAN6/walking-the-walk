"""Procedural 3D marker meshes for level guidance."""
import math

from engine.mesh import Mesh


def create_ring(radius=1.6, thickness=0.18, sides=24, colour=(255, 220, 60)):
    verts = []
    faces = []
    for i in range(sides):
        a0 = 2.0 * math.pi * i / sides
        a1 = 2.0 * math.pi * (i + 1) / sides
        r_out = radius + thickness * 0.5
        r_in = radius - thickness * 0.5
        o = len(verts)
        verts.extend([
            (r_out * math.cos(a0), 0.0, r_out * math.sin(a0)),
            (r_in * math.cos(a0), 0.0, r_in * math.sin(a0)),
            (r_in * math.cos(a1), 0.0, r_in * math.sin(a1)),
            (r_out * math.cos(a1), 0.0, r_out * math.sin(a1)),
        ])
        faces.append((o, o + 1, o + 3))      # (out0, in0, out1)
        faces.append((o + 1, o + 2, o + 3))  # (in0, in1, out1)
    return Mesh(verts, faces, colour, (0, 0, 0), alpha=0.5)


def create_arrow(stem_colour=(255, 0, 0), head_colour=(255, 0, 0)):
    # Stem: 0.06 wide, 0.35 long, pointing in +Z (smaller than before)
    r = 0.03
    sl = 0.35
    sv = [
        (-r, 0.0, 0.0), (r, 0.0, 0.0), (r, 0.0, sl), (-r, 0.0, sl),
        (-r, 0.0, 0.0), (r, 0.0, 0.0), (r, 0.0, sl), (-r, 0.0, sl),
    ]
    sf = [
        (0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0),
    ]
    stem = Mesh(sv, sf, stem_colour, (0, 0, 0))

    # Cone head at the tip pointing in +Z: apex at local z=sl+hl, base at z=sl
    hr = 0.12
    hl = 0.25
    sides = 8
    hv = [(0.0, 0.0, sl + hl)]
    for i in range(sides):
        a = 2.0 * math.pi * i / sides
        hv.append((hr * math.cos(a), 0.0, sl))
    hf = []
    for i in range(1, sides + 1):
        j = 1 + (i % sides)
        hf.append((0, i, j))
    for i in range(1, sides - 1):
        hf.append((1, i, i + 1))
    head = Mesh(hv, hf, head_colour, (0, 0, 0))
    return stem, head


def create_target_ring(radius=2, thickness=0.3, sides=24, colour=(255, 200, 50)):
    verts = []
    faces = []
    for i in range(sides):
        a0 = 2.0 * math.pi * i / sides
        a1 = 2.0 * math.pi * (i + 1) / sides
        r_out = radius + thickness * 0.5
        r_in = radius - thickness * 0.5
        o = len(verts)
        verts.extend([
            (r_out * math.cos(a0), 0.0, r_out * math.sin(a0)),
            (r_in * math.cos(a0), 0.0, r_in * math.sin(a0)),
            (r_in * math.cos(a1), 0.0, r_in * math.sin(a1)),
            (r_out * math.cos(a1), 0.0, r_out * math.sin(a1)),
        ])
        faces.append((o, o + 1, o + 3))      # (out0, in0, out1)
        faces.append((o + 1, o + 2, o + 3))  # (in0, in1, out1)
    # Each vertex gets full colour + alpha 0.5 for semi-transparency
    return Mesh(verts, faces, colour, (0, 2, 0), alpha=0.5)
