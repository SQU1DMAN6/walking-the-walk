"""Procedural world generation for the outback environment."""
import math
import random

from engine.mesh import Mesh


# Noise helpers

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


# Terrain

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


# Trees (Eucalyptus-style)

def _create_foliage_cluster(position, rx, ry, rz, colour):
    """Create a single foliage cluster as a low-poly blob (14 triangles).

    Uses an octahedron with randomised axis lengths so each cluster
    has a slightly different shape. Adds extra detail faces for
    a more organic look.
    """
    verts = [
        (0.0, ry, 0.0),         # 0: top
        (rx * 0.7, ry * 0.3, rx * 0.7),  # 1: upper quadrant
        (-rx * 0.7, ry * 0.3, rx * 0.7), # 2
        (-rx * 0.7, ry * 0.3, -rx * 0.7),# 3
        (rx * 0.7, ry * 0.3, -rx * 0.7), # 4
        (rx, 0.0, 0.0),         # 5: mid ring
        (0.0, 0.0, rz),         # 6
        (-rx, 0.0, 0.0),        # 7
        (0.0, 0.0, -rz),        # 8
        (rx * 0.5, -ry * 0.3, rx * 0.5), # 9: lower ring
        (-rx * 0.5, -ry * 0.3, rx * 0.5),# 10
        (-rx * 0.5, -ry * 0.3, -rx * 0.5),# 11
        (rx * 0.5, -ry * 0.3, -rx * 0.5),# 12
        (0.0, -ry * 0.4, 0.0),  # 13: bottom
    ]

    faces = [
        # Apex to upper ring (4 triangles)
        (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
        # Upper ring to mid ring (8 triangles = 4 quads)
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 8), (3, 8, 4),
        (4, 8, 5), (4, 5, 1),
        # Mid ring to lower ring (8 triangles = 4 quads)
        (5, 9, 10), (5, 10, 6),
        (6, 10, 11), (6, 11, 7),
        (7, 11, 12), (7, 12, 8),
        (8, 12, 9), (8, 9, 5),
        # Lower ring to bottom (4 triangles)
        (9, 13, 10), (10, 13, 11), (11, 13, 12), (12, 13, 9),
    ]

    return Mesh(verts, faces, colour, position)


def _create_branch(start, end, width, colour):
    """Create a 6-triangle branch from start to end.

    Uses a triangular prism cross-section for thickness and visible
    branch structure. The branch has a top edge and two bottom edges
    so it looks like a rounded/angular stick.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 0.001:
        return None

    # Direction of the branch (normalised)
    nx, ny, nz = dx / length, dy / length, dz / length

    # Compute two perpendicular vectors for the triangular cross-section
    # First perpendicular: cross with world up (or X if vertical)
    if abs(ny) > 0.9:
        px, py, pz = 1.0, 0.0, 0.0
    else:
        px, py, pz = 0.0, 1.0, 0.0

    # perp1 = dir × up
    wx = ny * pz - nz * py
    wy = nz * px - nx * pz
    wz = nx * py - ny * px
    wlen = math.sqrt(wx * wx + wy * wy + wz * wz)
    if wlen < 0.001:
        return None
    wx /= wlen
    wy /= wlen
    wz /= wlen

    # perp2 = dir × perp1  (creates a triangle cross-section)
    vx = ny * wz - nz * wy
    vy = nz * wx - nx * wz
    vz = nx * wy - ny * wx

    hw = width * 0.5
    # Three vertices at start, three at end (triangular prism)
    # Triangle points: one top, two bottom
    verts = [
        (start[0] + wx * hw, start[1] + wy * hw, start[2] + wz * hw),       # 0: start top
        (start[0] + vx * hw * 0.866 - wx * hw * 0.5,                          # 1: start bottom-left
         start[1] + vy * hw * 0.866 - wy * hw * 0.5,
         start[2] + vz * hw * 0.866 - wz * hw * 0.5),
        (start[0] - vx * hw * 0.866 - wx * hw * 0.5,                          # 2: start bottom-right
         start[1] - vy * hw * 0.866 - wy * hw * 0.5,
         start[2] - vz * hw * 0.866 - wz * hw * 0.5),
        (end[0] + wx * hw, end[1] + wy * hw, end[2] + wz * hw),               # 3: end top
        (end[0] + vx * hw * 0.866 - wx * hw * 0.5,                            # 4: end bottom-left
         end[1] + vy * hw * 0.866 - wy * hw * 0.5,
         end[2] + vz * hw * 0.866 - wz * hw * 0.5),
        (end[0] - vx * hw * 0.866 - wx * hw * 0.5,                            # 5: end bottom-right
         end[1] - vy * hw * 0.866 - wy * hw * 0.5,
         end[2] - vz * hw * 0.866 - wz * hw * 0.5),
    ]

    # 6 triangles: 3 side faces + 2 end caps (not rendered) + tube quads split
    faces = [
        # Side faces (3 quads = 6 triangles)
        (0, 3, 4), (0, 4, 1),  # top side
        (0, 2, 5), (0, 5, 3),  # bottom side 1
        (1, 4, 5), (1, 5, 2),  # bottom side 2
    ]

    return Mesh(verts, faces, colour, position=(0, 0, 0))


def create_tree(position, seed, base_height=4.0):
    """Create an Australian eucalyptus-style tree.

    Structure:
        trunk (thick, dominant, 25-40% of total height)
        + 5-10 major branches extending outward
        + 6-14 foliage clusters at branch tips

    Design principles (per SPEC_2026-07-27.md):
        - irregular silhouette
        - sparse canopy with 30-60% negative space
        - visible trunk structure
        - asymmetrical branch distribution
        - flattened/rounded crown (not a cone)

    Returns:
        list of Mesh objects: [trunk, branch_1, ..., branch_n,
                               cluster_1, ..., cluster_n]
    """
    rng = random.Random(seed)

    # Tree dimensions
    # Larger size variation: some trees massive, some small
    h_var = rng.uniform(1, 3.5)
    height = base_height * h_var
    trunk_h = height * rng.uniform(0.25, 0.40)  # 25-40% of total
    trunk_base_r = rng.uniform(0.15, 0.40)       # thicker trunk
    trunk_top_r = trunk_base_r * rng.uniform(0.4, 0.7)

    # Slight lean for the trunk
    lean_angle = rng.uniform(-0.08, 0.08)
    lean_x = math.sin(lean_angle) * trunk_h
    lean_z = math.cos(lean_angle) * trunk_h - trunk_h

    trunk_colour = (110, 85, 55)
    branch_colour = (120, 90, 60)
    # Olive/grey-green eucalyptus foliage
    canopy_base = (
        rng.uniform(60, 100),
        rng.uniform(100, 150),
        rng.uniform(40, 70),
    )

    meshes = []

    # Trunk: 4-sided prism, tapered
    tb = trunk_base_r
    tt = trunk_top_r
    lx = lean_x
    lz = lean_z

    trunk_verts = [
        (-tb, 0.0, -tb),   # 0
        ( tb, 0.0, -tb),   # 1
        ( tb, 0.0,  tb),   # 2
        (-tb, 0.0,  tb),   # 3
        (-tt + lx, trunk_h * 0.5, -tt + lz),  # 4: mid ring
        ( tt + lx, trunk_h * 0.5, -tt + lz),  # 5
        ( tt + lx, trunk_h * 0.5,  tt + lz),  # 6
        (-tt + lx, trunk_h * 0.5,  tt + lz),  # 7
        (-tt * 0.7 + lx, trunk_h, -tt * 0.7 + lz),  # 8: top ring
        ( tt * 0.7 + lx, trunk_h, -tt * 0.7 + lz),  # 9
        ( tt * 0.7 + lx, trunk_h,  tt * 0.7 + lz),  # 10
        (-tt * 0.7 + lx, trunk_h,  tt * 0.7 + lz),  # 11
    ]
    trunk_faces = [
        # Bottom segment
        (0, 1, 2), (0, 2, 3),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
        # Top segment
        (4, 5, 6), (4, 6, 7),
        (4, 8, 9), (4, 9, 5),
        (5, 9, 10), (5, 10, 6),
        (6, 10, 11), (6, 11, 7),
        (7, 11, 8), (7, 8, 4),
        # Cap the top
        (8, 9, 10), (8, 10, 11),
    ]

    trunk_mesh = Mesh(trunk_verts, trunk_faces, trunk_colour, position)
    meshes.append(trunk_mesh)

    # Branches
    num_branches = rng.randint(3, 8)
    branch_tips = []

    for i in range(num_branches):
        # Branch height on trunk (spread from low-mid to top)
        bh = trunk_h * rng.uniform(0.3, 0.95)

        # Random horizontal direction
        yaw = rng.uniform(0, 2.0 * math.pi)
        # Upward angle (15-65 degrees from horizontal)
        pitch = rng.uniform(0.25, 1.15)

        # Branch length relative to crown size
        crown_r = rng.uniform(0.8, 3.0)
        branch_len = crown_r * rng.uniform(0.3, 0.6)

        # Calculate end position
        end_x = position[0] + math.cos(yaw) * math.cos(pitch) * branch_len
        end_y = position[1] + bh + math.sin(pitch) * branch_len
        end_z = position[2] + math.sin(yaw) * math.cos(pitch) * branch_len

        # Start position (on trunk surface)
        t = bh / trunk_h
        r_at_h = trunk_base_r + (trunk_top_r - trunk_base_r) * t
        start_x = position[0] + math.cos(yaw) * r_at_h * 0.8 + lx * t
        start_y = position[1] + bh
        start_z = position[2] + math.sin(yaw) * r_at_h * 0.8 + lz * t

        start = (start_x, start_y, start_z)
        end = (end_x, end_y, end_z)

        branch_width = rng.uniform(0.06, 0.18)  # thicker branches
        branch_mesh = _create_branch(start, end, branch_width, branch_colour)
        if branch_mesh:
            meshes.append(branch_mesh)

        # Store tip for foliage
        branch_tips.append(end)

        # Occasionally add a secondary branch fork (more often)
        if rng.random() < 0.4 and len(branch_tips) < 8:
            fork_yaw = yaw + rng.uniform(-0.6, 0.6)
            fork_pitch = pitch + rng.uniform(-0.3, 0.3)
            fork_len = branch_len * rng.uniform(0.3, 0.7)
            fork_end_x = end_x + math.cos(fork_yaw) * math.cos(fork_pitch) * fork_len
            fork_end_y = end_y + math.sin(fork_pitch) * fork_len
            fork_end_z = end_z + math.sin(fork_yaw) * math.cos(fork_pitch) * fork_len
            fork_end = (fork_end_x, fork_end_y, fork_end_z)
            fork_mesh = _create_branch(
                end, fork_end, branch_width * 0.7, branch_colour
            )
            if fork_mesh:
                meshes.append(fork_mesh)
            branch_tips.append(fork_end)

    # Foliage clusters
    num_clusters = rng.randint(1, 2)

    # Place clusters at branch tips, plus extras scattered in canopy volume
    cluster_positions = list(branch_tips)

    # Add extra clusters
    crown_radius = rng.uniform(0.8, 3.0)
    for _ in range(num_clusters - len(cluster_positions)):
        ca = rng.uniform(0, 2.0 * math.pi)
        cd = rng.uniform(0, crown_radius * 0.8)
        ch = rng.uniform(0, trunk_h * 0.6)
        cx = position[0] + math.cos(ca) * cd
        cy = position[1] + trunk_h * 0.4 + ch
        cz = position[2] + math.sin(ca) * cd
        cluster_positions.append((cx, cy, cz))

    for cpos in cluster_positions:
        # Larger clusters
        cluster_r = rng.uniform(0.3, 0.9)
        cluster_h = rng.uniform(0.3, 0.7)
        # Slight colour variation per cluster
        c_colour = (
            int(canopy_base[0] + rng.uniform(-15, 15)),
            int(canopy_base[1] + rng.uniform(-20, 20)),
            int(canopy_base[2] + rng.uniform(-10, 10)),
        )
        cluster = _create_foliage_cluster(
            cpos, cluster_r, cluster_h, cluster_r * rng.uniform(0.7, 1.3), c_colour
        )
        meshes.append(cluster)

    return meshes


# Bushes

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


# Rocks

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


# Spinifex grass

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


# Discovery markers (exploration landmarks)

def create_discovery(position, colour=(200, 180, 80)):
    """A small glowing marker placed at a point of interest. The player
    can stand near one and press E to collect it (ties into the journal)."""
    r = 0.35
    h = 0.9
    verts = [
        (0.0, h, 0.0),      # 0 top
        (r, 0.0, 0.0),      # 1
        (0.0, 0.0, r),      # 2
        (-r, 0.0, 0.0),     # 3
        (0.0, 0.0, -r),     # 4
        (0.0, 0.05, 0.0),   # 5 base
    ]
    faces = [
        (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
        (1, 5, 2), (2, 5, 3), (3, 5, 4), (4, 5, 1),
    ]
    return Mesh(verts, faces, colour, position)


# Chunk terrain (world-space height sampling so seams match)

def _terrain_vertex_colour(wx, wz, seed, base):
    """Compute a per-vertex terrain colour from a low-frequency world-space
    noise field. This makes colour vary organically and continuously across
    chunk borders (no square seams)."""
    # Low-frequency colour noise (0..1)
    n = _smooth_noise(wx * 0.02, wz * 0.02, seed + 777)
    n2 = _smooth_noise(wx * 0.05 + 100, wz * 0.05 + 100, seed + 888)
    # Blend two octaves for organic variation
    t = n * 0.6 + n2 * 0.4
    # Narrow variation so chunks feel interconnected
    r = base[0] + (t - 0.5) * 18
    g = base[1] + (t - 0.5) * 14
    b = base[2] + (t - 0.5) * 10
    return (int(r), int(g), int(b))


def _generate_chunk_terrain(cx, cz, chunk_size, segments, seed, colour):
    """Build a terrain mesh for a chunk, sampling the noise at WORLD
    coordinates so adjacent chunks share identical edge heights and
    per-vertex colours blend smoothly across chunk borders."""
    x0 = cx * chunk_size
    z0 = cz * chunk_size

    vertices = []
    vertex_colours = []
    for iz in range(segments + 1):
        for ix in range(segments + 1):
            wx = x0 + (chunk_size * ix / segments)
            wz = z0 + (chunk_size * iz / segments)
            y = get_terrain_height(wx, wz, seed, 1.5)
            vertices.append((wx, y, wz))
            vertex_colours.append(_terrain_vertex_colour(wx, wz, seed, colour))

    faces = []
    for iz in range(segments):
        for ix in range(segments):
            i0 = iz * (segments + 1) + ix
            i1 = iz * (segments + 1) + ix + 1
            i2 = (iz + 1) * (segments + 1) + ix
            i3 = (iz + 1) * (segments + 1) + ix + 1
            faces.append((i0, i1, i2))
            faces.append((i2, i1, i3))

    return Mesh(vertices, faces, colour, (0, 0, 0), vertex_colours=vertex_colours)


# Chunk generation

def generate_chunk(cx, cz, seed, chunk_size=40, segments=12):
    """Generate a single deterministic terrain tile (chunk).

    Args:
        cx, cz: chunk grid coordinates (integers).
        seed: global world seed.
        chunk_size: world-space size of one chunk edge.
        segments: terrain grid resolution per chunk.

    Returns a dict with:
        meshes     - list of Mesh objects for this chunk
        obstacles  - list of (cx, cz, radius, height) collision circles
        discoveries - list of dicts describing collectible landmarks
    """
    rng = random.Random(seed * 7919 + cx * 104729 + cz * 1299709)
    result = {"meshes": [], "obstacles": [], "discoveries": []}
    meshes = result["meshes"]
    obstacles = result["obstacles"]
    discoveries = result["discoveries"]

    # World-space bounds of this chunk
    x0 = cx * chunk_size
    z0 = cz * chunk_size
    x1 = x0 + chunk_size
    z1 = z0 + chunk_size

    r_base = rng.randint(205, 225)
    g_base = rng.randint(140, 155)
    b_base = rng.randint(60, 75)
    terrain_colour = (r_base, g_base, b_base)

    # Terrain mesh covering the chunk tile (world-space heights)
    terrain = _generate_chunk_terrain(
        cx, cz, chunk_size, segments, seed, terrain_colour,
    )
    meshes.append(terrain)

    # Trees
    tree_positions = []
    num_trees = rng.randint(4, 8)
    for i in range(num_trees):
        tx = rng.uniform(x0 + 2, x1 - 2)
        tz = rng.uniform(z0 + 2, z1 - 2)
        ty = get_terrain_height(tx, tz, seed, 1.5)
        if ty < -1.5:
            continue
        too_close = False
        for ex, ez in tree_positions:
            if (tx - ex) ** 2 + (tz - ez) ** 2 < 16.0:
                too_close = True
                break
        if too_close:
            continue
        tree_positions.append((tx, tz))
        tree_meshes = create_tree((tx, ty, tz), seed + i * 7 + cx * 31 + cz * 17)
        meshes.extend(tree_meshes)
        obstacles.append((tx, tz, 0.7, 4.0))

    # Bushes
    num_bushes = rng.randint(12, 24)
    for i in range(num_bushes):
        bx = rng.uniform(x0 + 1, x1 - 1)
        bz = rng.uniform(z0 + 1, z1 - 1)
        by = get_terrain_height(bx, bz, seed, 1.5)
        too_close = False
        for tx, tz in tree_positions:
            if (bx - tx) ** 2 + (bz - tz) ** 2 < 4.0:
                too_close = True
                break
        if too_close:
            continue
        meshes.append(create_bush((bx, by, bz), seed + i * 13 + 1000 + cx * 7 + cz * 11))

    # Rocks
    num_rocks = rng.randint(3, 6)
    for i in range(num_rocks):
        rx = rng.uniform(x0 + 1, x1 - 1)
        rz = rng.uniform(z0 + 1, z1 - 1)
        ry = get_terrain_height(rx, rz, seed, 1.5)
        meshes.append(create_rock((rx, ry, rz), seed + i * 19 + 2000 + cx * 13 + cz * 29))
        obstacles.append((rx, rz, 0.5, 1.2))

    # Spinifex grass
    num_spinifex = rng.randint(8, 16)
    for i in range(num_spinifex):
        sx = rng.uniform(x0 + 1, x1 - 1)
        sz = rng.uniform(z0 + 1, z1 - 1)
        sy = get_terrain_height(sx, sz, seed, 1.5)
        too_close = False
        for tx, tz in tree_positions:
            if (sx - tx) ** 2 + (sz - tz) ** 2 < 4.0:
                too_close = True
                break
        if too_close:
            continue
        meshes.append(create_spinifex((sx, sy, sz), seed + i * 31 + 3000 + cx * 19 + cz * 23))

    # Discovery landmarks (sparse, deterministic)
    # Only some chunks contain a discovery, so they feel special.
    # The origin chunk always has one so the game is playable immediately.
    if (cx == 0 and cz == 0) or rng.random() < 0.35:
        dx = rng.uniform(x0 + 4, x1 - 4)
        dz = rng.uniform(z0 + 4, z1 - 4)
        dy = get_terrain_height(dx, dz, seed, 1.5)
        name = rng.choice([
            "Uluru Rock",
            "River Red Gum",
            "Spinifex Grass",
            "Coolabah Tree",
            "Desert Oak",
        ])
        category = "Landmark" if name == "Uluru Rock" else "Flora"
        description = {
            "Uluru Rock": "A weathered sandstone monolith sacred to the "
                          "Anangu people of Central Australia.",
            "River Red Gum": "A massive eucalyptus that grows beside "
                             "watercourses across the outback.",
            "Spinifex Grass": "A hardy, drought-resistant grass that covers "
                              "vast areas of inland Australia.",
            "Coolabah Tree": "A tree of the arid interior, often found "
                             "growing in claypans and near waterholes.",
            "Desert Oak": "A slow-growing tree with needle-like foliage, "
                          "common to the spinifex country of the outback.",
        }[name]
        colour = rng.choice([
            (210, 190, 80), (170, 220, 90), (200, 200, 60),
            (120, 180, 120), (160, 200, 110),
        ])
        meshes.append(create_discovery((dx, dy, dz), colour=colour))
        discoveries.append({
            "x": dx,
            "z": dz,
            "y": dy,
            "name": name,
            "category": category,
            "description": description,
        })

    return result


# World generation

def generate_world(seed=42, terrain_size=100, terrain_segments=30):
    """Generate a complete outback world scene.

    Returns a dict with:
        meshes     - list of Mesh objects to render
        obstacles  - list of (cx, cz, radius, height) collision circles
                    (tree trunks and rocks the player cannot walk through)
        discoveries - list of dicts describing collectible landmarks
                    {x, z, y, name, category, description}
    """
    rng = random.Random(seed)
    result = {"meshes": [], "obstacles": [], "discoveries": []}
    meshes = result["meshes"]
    obstacles = result["obstacles"]
    discoveries = result["discoveries"]

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

    meshes.append(terrain)

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
        tree_meshes = create_tree((tx, ty, tz), seed + i * 7)
        meshes.extend(tree_meshes)

        # Trunk collision circle for the tree
        obstacles.append((tx, tz, 0.7, 4.0))

    # Spawn bushes
    for i in range(240):
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
    for i in range(60):
        rx = rng.uniform(-terrain_size/2 + 1, terrain_size/2 - 1)
        rz = rng.uniform(-terrain_size/2 + 1, terrain_size/2 - 1)
        ry = get_terrain_height(rx, rz, seed, 1.5)

        meshes.append(create_rock((rx, ry, rz), seed + i * 19 + 2000))
        obstacles.append((rx, rz, 0.5, 1.2))

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

    # Discovery landmarks (exploration objective)
    discovery_defs = [
        {
            "name": "Uluru Rock",
            "category": "Landmark",
            "description": "A weathered sandstone monolith sacred to the "
                           "Anangu people of Central Australia.",
        },
        {
            "name": "River Red Gum",
            "category": "Flora",
            "description": "A massive eucalyptus that grows beside "
                           "watercourses across the outback.",
        },
        {
            "name": "Spinifex Grass",
            "category": "Flora",
            "description": "A hardy, drought-resistant grass that covers "
                           "vast areas of inland Australia.",
        },
        {
            "name": "Coolabah Tree",
            "category": "Flora",
            "description": "A tree of the arid interior, often found "
                           "growing in claypans and near waterholes.",
        },
        {
            "name": "Desert Oak",
            "category": "Flora",
            "description": "A slow-growing tree with needle-like foliage, "
                           "common to the spinifex country of the outback.",
        },
    ]

    discovery_colours = [
        (210, 190, 80),
        (170, 220, 90),
        (200, 200, 60),
        (120, 180, 120),
        (160, 200, 110),
    ]

    for i, ddef in enumerate(discovery_defs):
        # Place each discovery at a distinct, reachable spot
        dx = rng.uniform(-terrain_size/2 + 6, terrain_size/2 - 6)
        dz = rng.uniform(-terrain_size/2 + 6, terrain_size/2 - 6)
        dy = get_terrain_height(dx, dz, seed, 1.5)
        meshes.append(
            create_discovery(
                (dx, dy, dz),
                colour=discovery_colours[i % len(discovery_colours)],
            )
        )
        discoveries.append({
            "x": dx,
            "z": dz,
            "y": dy,
            "name": ddef["name"],
            "category": ddef["category"],
            "description": ddef["description"],
        })

    return result
