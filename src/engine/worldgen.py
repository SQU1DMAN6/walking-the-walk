"""Procedural world generation for the outback environment."""
import math
import random

from engine.mesh import Mesh


# ── Noise helpers ─────────────────────────────────────────────────────

def _hash(x, y, seed):
    """Simple deterministic hash for noise."""
    h = seed
    h = (h * 374761393 + x * 668265263) & 0xFFFFFFFF
    h = (h * 374761393 + y * 668265263) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFFFF) / 0xFFFFFFFF


def _smooth_noise(x, y, seed):
    """Bilinear interpolation of a simple value noise."""
    ix = int(math.floor(x))
    iy = int(math.floor(y))
    fx = x - ix
    fy = y - iy
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)

    n00 = _hash(ix, iy, seed)
    n10 = _hash(ix + 1, iy, seed)
    n01 = _hash(ix, iy + 1, seed)
    n11 = _hash(ix + 1, iy + 1, seed)

    nx0 = n00 + (n10 - n00) * fx
    nx1 = n01 + (n11 - n01) * fx
    return nx0 + (nx1 - nx0) * fy


def _fbm(x, y, seed, octaves=4):
    """Fractional Brownian motion for terrain height."""
    value = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(octaves):
        value += amplitude * _smooth_noise(x * frequency, y * frequency, seed)
        max_val += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    return value / max_val


def get_terrain_height(x, z, seed, height_scale=1.5):
    """Sample terrain height at a given world (x, z) position."""
    h = _fbm(x * 0.04, z * 0.04, seed, octaves=4)
    h2 = _smooth_noise(x * 0.01, z * 0.01, seed + 1) * 0.5
    h = h * 0.7 + h2 * 0.3
    h = h * h * 1.5
    return h * height_scale - 2.0  # offset so player stands on it


# ── Terrain ───────────────────────────────────────────────────────────

def generate_terrain(
    width,
    depth,
    segments,
    seed,
    height_scale=1.5,
    colour=(180, 120, 60)
):
    """Generate a height-mapped terrain mesh with an offset so the
    player stands ON (not in) the terrain."""
    hw = width / 2
    hd = depth / 2

    # Generate heightmap
    heights = []
    for iz in range(segments + 1):
        row = []
        for ix in range(segments + 1):
            wx = -hw + (width * ix / segments)
            wz = -hd + (depth * iz / segments)
            h = get_terrain_height(wx, wz, seed, height_scale)
            row.append(h)
        heights.append(row)

    vertices = []
    for iz in range(segments + 1):
        for ix in range(segments + 1):
            x = -hw + (width * ix / segments)
            z = -hd + (depth * iz / segments)
            y = heights[iz][ix]
            vertices.append((x, y, z))

    faces = []
    for iz in range(segments):
        for ix in range(segments):
            i0 = iz * (segments + 1) + ix
            i1 = iz * (segments + 1) + ix + 1
            i2 = (iz + 1) * (segments + 1) + ix
            i3 = (iz + 1) * (segments + 1) + ix + 1
            faces.append((i0, i1, i2))
            faces.append((i2, i1, i3))

    return Mesh(vertices, faces, colour, (0, 0, 0))


# ── Trees (Eucalyptus-style) ─────────────────────────────────────────

def create_tree(position, seed, height=4.0, trunk_radius=0.12):
    """Create a eucalyptus-style tree.

    The trunk is tall and thin. Above the trunk, a crown of
    6 triangle pairs (12 triangles) forms the canopy.
    4 thin branch triangles connect the trunk to the crown.

    Total triangles: trunk (12) + branches (4) + crown (12) = 28
    which is within the 28-triangle limit for the whole tree.

    Returns:
        trunk_mesh, canopy_mesh — two Mesh objects with different colours.
    """
    rng = random.Random(seed)
    h_var = rng.uniform(0.7, 1.3)
    height *= h_var
    trunk_h = height * 0.55
    crown_r = rng.uniform(0.8, 2.5)
    crown_h = rng.uniform(1.0, 3.5)

    trunk_colour = (110, 85, 55)
    # Olive/grey-green eucalyptus foliage
    canopy_colour = (
        int(rng.uniform(60, 100)),
        int(rng.uniform(100, 150)),
        int(rng.uniform(40, 70)),
    )

    tr = trunk_radius
    # Trunk: 4-sided prism
    trunk_verts = [
        (-tr, 0.0, -tr),
        ( tr, 0.0, -tr),
        ( tr, 0.0,  tr),
        (-tr, 0.0,  tr),
        (-tr * 0.7, trunk_h * 0.7, -tr * 0.7),
        ( tr * 0.7, trunk_h * 0.7, -tr * 0.7),
        ( tr * 0.7, trunk_h * 0.7,  tr * 0.7),
        (-tr * 0.7, trunk_h * 0.7,  tr * 0.7),
        (-tr * 0.4, trunk_h, -tr * 0.4),
        ( tr * 0.4, trunk_h, -tr * 0.4),
        ( tr * 0.4, trunk_h,  tr * 0.4),
        (-tr * 0.4, trunk_h,  tr * 0.4),
    ]
    # Two stacked segments for the trunk (8 triangles top + 8 bottom = 16,
    # but we'll use 12 to keep it simple: just 2 open-top segments)
    trunk_faces = [
        # Bottom segment
        (0,1,2),(0,2,3),
        (0,4,5),(0,5,1),
        (1,5,6),(1,6,2),
        (2,6,7),(2,7,3),
        (3,7,4),(3,4,0),
        # Top segment
        (4,5,6),(4,6,7),
        (4,8,9),(4,9,5),
        (5,9,10),(5,10,6),
        (6,10,11),(6,11,7),
        (7,11,8),(7,8,4),
        # Cap the top
        (8,9,10),(8,10,11),
    ]

    # Branches: 4 thin triangles radiating from trunk top
    branch_len = crown_r * 0.6
    branch_h = trunk_h + crown_h * 0.15
    branch_verts = [
        # Branch 1 (positive X)
        (tr * 0.4, trunk_h, 0.0),
        (branch_len, trunk_h + 0.1, 0.0),
        (branch_len * 0.5, trunk_h + 0.3, 0.0),
        # Branch 2 (negative X)
        (-tr * 0.4, trunk_h, 0.0),
        (-branch_len, trunk_h + 0.1, 0.0),
        (-branch_len * 0.5, trunk_h + 0.3, 0.0),
        # Branch 3 (positive Z)
        (0.0, trunk_h, tr * 0.4),
        (0.0, trunk_h + 0.1, branch_len),
        (0.0, trunk_h + 0.3, branch_len * 0.5),
        # Branch 4 (negative Z)
        (0.0, trunk_h, -tr * 0.4),
        (0.0, trunk_h + 0.1, -branch_len),
        (0.0, trunk_h + 0.3, -branch_len * 0.5),
    ]
    branch_faces = [
        (0, 1, 2),
        (3, 5, 4),
        (6, 7, 8),
        (9, 11, 10),
    ]

    # Crown: ~60-triangle canopy with 12 radial segments and 3 rings
    # for a more tree-like, rounded appearance.
    crown_segments = 12
    crown_base_y = trunk_h + crown_h * 0.2
    crown_mid_y = trunk_h + crown_h * 0.55
    crown_top_y = trunk_h + crown_h

    crown_verts = [(0.0, crown_top_y, 0.0)]  # 0: apex
    crown_texcoords = [(0.5, 0.5)]  # apex texcoord

    # Generate rings: upper, lower, skirt
    ring_radii = [0.45, 0.75, 1.0]
    ring_heights = [crown_mid_y, crown_base_y, crown_base_y - 0.4]
    for ri in range(3):
        r = ring_radii[ri] * crown_r
        h = ring_heights[ri]
        for si in range(crown_segments):
            angle = (2.0 * math.pi * si) / crown_segments
            x = r * math.cos(angle)
            z = r * math.sin(angle)
            crown_verts.append((x, h, z))
            crown_texcoords.append((si / crown_segments, 0.2 + 0.8 * (ri / 3)))

    crown_faces = []
    # Apex to upper ring (12 triangles)
    for si in range(crown_segments):
        s0 = 1 + si
        s1 = 1 + (si + 1) % crown_segments
        crown_faces.append((0, s0, s1))

    # Upper ring to lower ring (24 triangles = 12 quads)
    upper_start = 1
    lower_start = 1 + crown_segments
    for si in range(crown_segments):
        s0 = upper_start + si
        s1 = upper_start + (si + 1) % crown_segments
        s2 = lower_start + si
        s3 = lower_start + (si + 1) % crown_segments
        crown_faces.append((s0, s2, s3))
        crown_faces.append((s0, s3, s1))

    # Lower ring to skirt (24 triangles = 12 quads)
    skirt_start = 1 + 2 * crown_segments
    for si in range(crown_segments):
        s0 = lower_start + si
        s1 = lower_start + (si + 1) % crown_segments
        s2 = skirt_start + si
        s3 = skirt_start + (si + 1) % crown_segments
        crown_faces.append((s0, s2, s3))
        crown_faces.append((s0, s3, s1))

    # Combine into separate meshes so colours are correct
    trunk_combined_verts = trunk_verts + branch_verts
    trunk_face_count = len(trunk_faces)
    branch_offset = len(trunk_verts)
    combined_trunk_faces = (
        trunk_faces
        + [(i0 + branch_offset, i1 + branch_offset, i2 + branch_offset)
           for (i0, i1, i2) in branch_faces]
    )

    trunk_mesh = Mesh(trunk_combined_verts, combined_trunk_faces, trunk_colour, position)
    canopy_mesh = Mesh(crown_verts, crown_faces, canopy_colour, position, texcoords=crown_texcoords)
    return trunk_mesh, canopy_mesh


# ── Bushes ────────────────────────────────────────────────────────────

def create_bush(position, seed):
    """Create a low-poly bush mesh — spinifex-style tussock.

    Uses 3 crossed quads (6 triangles) for a rounded bush look.
    Colours are yellow-green / tan for dry outback vegetation.
    """
    rng = random.Random(seed)
    radius = rng.uniform(0.4, 1.0)
    height = rng.uniform(0.3, 0.8)
    # Tan / yellow-green for dry spinifex
    colour = (
        int(rng.uniform(100, 160)),
        int(rng.uniform(130, 180)),
        int(rng.uniform(40, 80)),
    )

    verts = [
        (-radius, 0.0, 0.0),
        ( radius, 0.0, 0.0),
        (0.0, height, 0.0),
        (0.0, 0.0, -radius),
        (0.0, 0.0,  radius),
        (-radius * 0.7, 0.0, -radius * 0.7),
        ( radius * 0.7, 0.0,  radius * 0.7),
    ]
    faces = [
        (0, 1, 2),
        (3, 4, 2),
        (5, 6, 2),
    ]

    return Mesh(verts, faces, colour, position)


# ── Rocks ─────────────────────────────────────────────────────────────

def create_rock(position, seed):
    """Create a low-poly rock mesh — red/orange for outback."""
    rng = random.Random(seed)
    w = rng.uniform(0.3, 1.0)
    h = rng.uniform(0.2, 0.6)
    d = rng.uniform(0.3, 0.8)
    # Reddish-grey for outback rocks
    r_col = int(rng.uniform(100, 180))
    g_col = int(rng.uniform(60, 120))
    b_col = int(rng.uniform(40, 80))
    colour = (r_col, g_col, b_col)

    hw = w / 2
    hd = d / 2
    verts = [
        (-hw, -h/2, -hd),
        ( hw, -h/2, -hd),
        ( hw, -h/2,  hd),
        (-hw, -h/2,  hd),
        (rng.uniform(-hw*0.3, hw*0.3), h/2, rng.uniform(-hd*0.3, hd*0.3)),
    ]
    faces = [
        (0, 1, 4),
        (1, 2, 4),
        (2, 3, 4),
        (3, 0, 4),
        (0, 3, 2),
        (0, 2, 1),
    ]

    return Mesh(verts, faces, colour, position)


# ── Spinifex grass ────────────────────────────────────────────────────

def create_spinifex(position, seed):
    """Small tufts of dry grass — 2 crossed quads (4 triangles)."""
    rng = random.Random(seed)
    radius = rng.uniform(0.15, 0.4)
    height = rng.uniform(0.15, 0.4)
    # Yellow-tan for dry grass
    colour = (
        int(rng.uniform(140, 200)),
        int(rng.uniform(140, 190)),
        int(rng.uniform(60, 100)),
    )

    verts = [
        (-radius, 0.0, 0.0),
        ( radius, 0.0, 0.0),
        (0.0, height, 0.0),
        (0.0, 0.0, -radius),
        (0.0, 0.0,  radius),
    ]
    faces = [
        (0, 1, 2),
        (3, 4, 2),
    ]

    return Mesh(verts, faces, colour, position)


# ── World generation ──────────────────────────────────────────────────

def generate_world(seed=42, terrain_size=100, terrain_segments=30):
    """Generate a complete outback world scene."""
    rng = random.Random(seed)

    # Terrain colours: bright red/orange Australian outback palette
    r_base = rng.randint(200, 240)
    g_base = rng.randint(130, 170)
    b_base = rng.randint(50, 90)
    terrain_colour = (r_base, g_base, b_base)

    terrain = generate_terrain(
        terrain_size, terrain_size, terrain_segments,
        seed, height_scale=1.5,
        colour=terrain_colour,
    )

    meshes = [terrain]

    # Spawn trees
    tree_positions = []
    for i in range(60):
        tx = rng.uniform(-terrain_size/2 + 3, terrain_size/2 - 3)
        tz = rng.uniform(-terrain_size/2 + 3, terrain_size/2 - 3)
        ty = get_terrain_height(tx, tz, seed, 1.5)

        # Don't place trees in very low areas (creek beds)
        if ty < -1.5:
            continue

        # Avoid placing trees too close to each other
        too_close = False
        for ex, ez in tree_positions:
            if (tx - ex) ** 2 + (tz - ez) ** 2 < 16.0:
                too_close = True
                break
        if too_close:
            continue

        tree_positions.append((tx, tz))
        trunk, canopy = create_tree((tx, ty, tz), seed + i * 7)
        meshes.append(trunk)
        meshes.append(canopy)

    # Spawn bushes
    for i in range(80):
        bx = rng.uniform(-terrain_size/2 + 1, terrain_size/2 - 1)
        bz = rng.uniform(-terrain_size/2 + 1, terrain_size/2 - 1)
        by = get_terrain_height(bx, bz, seed, 1.5)

        # Avoid placing bushes on trees
        too_close = False
        for tx, tz in tree_positions:
            if (bx - tx) ** 2 + (bz - tz) ** 2 < 4.0:
                too_close = True
                break
        if too_close:
            continue

        meshes.append(create_bush((bx, by, bz), seed + i * 13 + 1000))

    # Spawn rocks
    for i in range(40):
        rx = rng.uniform(-terrain_size/2 + 1, terrain_size/2 - 1)
        rz = rng.uniform(-terrain_size/2 + 1, terrain_size/2 - 1)
        ry = get_terrain_height(rx, rz, seed, 1.5)

        meshes.append(create_rock((rx, ry, rz), seed + i * 19 + 2000))

    # Spawn spinifex grass tufts
    for i in range(120):
        sx = rng.uniform(-terrain_size/2 + 1, terrain_size/2 - 1)
        sz = rng.uniform(-terrain_size/2 + 1, terrain_size/2 - 1)
        sy = get_terrain_height(sx, sz, seed, 1.5)

        # Avoid placing on trees
        too_close = False
        for tx, tz in tree_positions:
            if (sx - tx) ** 2 + (sz - tz) ** 2 < 4.0:
                too_close = True
                break
        if too_close:
            continue

        meshes.append(create_spinifex((sx, sy, sz), seed + i * 31 + 3000))

    return meshes
