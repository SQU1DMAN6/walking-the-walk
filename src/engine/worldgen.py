import math
import random

from engine.mesh import Mesh


def _hash(x, y, seed):

    h = seed
    h = (h * 374761393 + x * 668265263) & 0xFFFFFFFF
    h = (h * 374761393 + y * 668265263) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFFFF) / 0xFFFFFFFF


def _smooth_noise(x, y, seed):

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

    h = _fbm(x * 0.04, z * 0.04, seed, octaves=4)
    h2 = _smooth_noise(x * 0.01, z * 0.01, seed + 1) * 0.5
    h = h * 0.7 + h2 * 0.3
    h = h * h * 1.5
    return h * height_scale - 2.0


def generate_terrain(
    width,
    depth,
    segments,
    seed,
    height_scale=1.5,
    colour=(180, 120, 60)
):


    hw = width / 2
    hd = depth / 2


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


def _create_foliage_cluster(position, rx, ry, rz, colour):


    verts = [
        (0.0, ry, 0.0),
        (rx * 0.7, ry * 0.3, rx * 0.7),
        (-rx * 0.7, ry * 0.3, rx * 0.7),
        (-rx * 0.7, ry * 0.3, -rx * 0.7),
        (rx * 0.7, ry * 0.3, -rx * 0.7),
        (rx, 0.0, 0.0),
        (0.0, 0.0, rz),
        (-rx, 0.0, 0.0),
        (0.0, 0.0, -rz),
        (rx * 0.5, -ry * 0.3, rx * 0.5),
        (-rx * 0.5, -ry * 0.3, rx * 0.5),
        (-rx * 0.5, -ry * 0.3, -rx * 0.5),
        (rx * 0.5, -ry * 0.3, -rx * 0.5),
        (0.0, -ry * 0.4, 0.0),
    ]

    faces = [

        (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),

        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 8), (3, 8, 4),
        (4, 8, 5), (4, 5, 1),

        (5, 9, 10), (5, 10, 6),
        (6, 10, 11), (6, 11, 7),
        (7, 11, 12), (7, 12, 8),
        (8, 12, 9), (8, 9, 5),

        (9, 13, 10), (10, 13, 11), (11, 13, 12), (12, 13, 9),
    ]

    return Mesh(verts, faces, colour, position)


def create_branch(start, end, width, colour):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 0.001:
        return None


    nx, ny, nz = dx / length, dy / length, dz / length


    if abs(ny) > 0.9:
        px, py, pz = 1.0, 0.0, 0.0
    else:
        px, py, pz = 0.0, 1.0, 0.0


    wx = ny * pz - nz * py
    wy = nz * px - nx * pz
    wz = nx * py - ny * px
    wlen = math.sqrt(wx * wx + wy * wy + wz * wz)
    if wlen < 0.001:
        return None
    wx /= wlen
    wy /= wlen
    wz /= wlen


    vx = ny * wz - nz * wy
    vy = nz * wx - nx * wz
    vz = nx * wy - ny * wx

    hw = width * 0.5


    verts = [
        (start[0] + wx * hw, start[1] + wy * hw, start[2] + wz * hw),
        (start[0] + vx * hw * 0.866 - wx * hw * 0.5,
         start[1] + vy * hw * 0.866 - wy * hw * 0.5,
         start[2] + vz * hw * 0.866 - wz * hw * 0.5),
        (start[0] - vx * hw * 0.866 - wx * hw * 0.5,
         start[1] - vy * hw * 0.866 - wy * hw * 0.5,
         start[2] - vz * hw * 0.866 - wz * hw * 0.5),
        (end[0] + wx * hw, end[1] + wy * hw, end[2] + wz * hw),
        (end[0] + vx * hw * 0.866 - wx * hw * 0.5,
         end[1] + vy * hw * 0.866 - wy * hw * 0.5,
         end[2] + vz * hw * 0.866 - wz * hw * 0.5),
        (end[0] - vx * hw * 0.866 - wx * hw * 0.5,
         end[1] - vy * hw * 0.866 - wy * hw * 0.5,
         end[2] - vz * hw * 0.866 - wz * hw * 0.5),
    ]


    faces = [

        (0, 3, 4), (0, 4, 1),
        (0, 2, 5), (0, 5, 3),
        (1, 4, 5), (1, 5, 2),
    ]

    return Mesh(verts, faces, colour, position=(0, 0, 0))


def create_tree(position, seed, base_height=4.0):
    rng = random.Random(seed)


    h_var = rng.uniform(1, 3.5)
    height = base_height * h_var
    trunk_h = height * rng.uniform(0.25, 0.40)
    trunk_base_r = rng.uniform(0.15, 0.40)
    trunk_top_r = trunk_base_r * rng.uniform(0.4, 0.7)


    lean_angle = rng.uniform(-0.08, 0.08)
    lean_x = math.sin(lean_angle) * trunk_h
    lean_z = math.cos(lean_angle) * trunk_h - trunk_h

    trunk_colour = (110, 85, 55)
    branch_colour = (120, 90, 60)

    canopy_base = (
        rng.uniform(60, 100),
        rng.uniform(100, 150),
        rng.uniform(40, 70),
    )

    meshes = []


    tb = trunk_base_r
    tt = trunk_top_r
    lx = lean_x
    lz = lean_z

    trunk_verts = [
        (-tb, 0.0, -tb),
        ( tb, 0.0, -tb),
        ( tb, 0.0,  tb),
        (-tb, 0.0,  tb),
        (-tt + lx, trunk_h * 0.5, -tt + lz),
        ( tt + lx, trunk_h * 0.5, -tt + lz),
        ( tt + lx, trunk_h * 0.5,  tt + lz),
        (-tt + lx, trunk_h * 0.5,  tt + lz),
        (-tt * 0.7 + lx, trunk_h, -tt * 0.7 + lz),
        ( tt * 0.7 + lx, trunk_h, -tt * 0.7 + lz),
        ( tt * 0.7 + lx, trunk_h,  tt * 0.7 + lz),
        (-tt * 0.7 + lx, trunk_h,  tt * 0.7 + lz),
    ]
    trunk_faces = [

        (0, 1, 2), (0, 2, 3),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),

        (4, 5, 6), (4, 6, 7),
        (4, 8, 9), (4, 9, 5),
        (5, 9, 10), (5, 10, 6),
        (6, 10, 11), (6, 11, 7),
        (7, 11, 8), (7, 8, 4),

        (8, 9, 10), (8, 10, 11),
    ]

    trunk_mesh = Mesh(trunk_verts, trunk_faces, trunk_colour, position)
    meshes.append(trunk_mesh)


    num_branches = rng.randint(3, 8)
    branch_tips = []

    for i in range(num_branches):

        bh = trunk_h * rng.uniform(0.3, 0.95)


        yaw = rng.uniform(0, 2.0 * math.pi)

        pitch = rng.uniform(0.25, 1.15)


        crown_r = rng.uniform(0.8, 3.0)
        branch_len = crown_r * rng.uniform(0.3, 0.6)


        end_x = position[0] + math.cos(yaw) * math.cos(pitch) * branch_len
        end_y = position[1] + bh + math.sin(pitch) * branch_len
        end_z = position[2] + math.sin(yaw) * math.cos(pitch) * branch_len


        t = bh / trunk_h
        r_at_h = trunk_base_r + (trunk_top_r - trunk_base_r) * t
        start_x = position[0] + math.cos(yaw) * r_at_h * 0.8 + lx * t
        start_y = position[1] + bh
        start_z = position[2] + math.sin(yaw) * r_at_h * 0.8 + lz * t

        start = (start_x, start_y, start_z)
        end = (end_x, end_y, end_z)

        branch_width = rng.uniform(0.06, 0.18)
        branch_mesh = create_branch(start, end, branch_width, branch_colour)
        if branch_mesh:
            meshes.append(branch_mesh)


        branch_tips.append(end)


        if rng.random() < 0.4 and len(branch_tips) < 8:
            fork_yaw = yaw + rng.uniform(-0.6, 0.6)
            fork_pitch = pitch + rng.uniform(-0.3, 0.3)
            fork_len = branch_len * rng.uniform(0.3, 0.7)
            fork_end_x = end_x + math.cos(fork_yaw) * math.cos(fork_pitch) * fork_len
            fork_end_y = end_y + math.sin(fork_pitch) * fork_len
            fork_end_z = end_z + math.sin(fork_yaw) * math.cos(fork_pitch) * fork_len
            fork_end = (fork_end_x, fork_end_y, fork_end_z)
            fork_mesh = create_branch(
                end, fork_end, branch_width * 0.7, branch_colour
            )
            if fork_mesh:
                meshes.append(fork_mesh)
            branch_tips.append(fork_end)


    num_clusters = rng.randint(1, 2)


    cluster_positions = list(branch_tips)


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

        cluster_r = rng.uniform(0.3, 0.9)
        cluster_h = rng.uniform(0.3, 0.7)

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


def create_bush(position, seed):


    rng = random.Random(seed)
    radius = rng.uniform(0.4, 1.0)
    height = rng.uniform(0.3, 0.8)

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


def create_rock(position, seed):

    rng = random.Random(seed)
    w = rng.uniform(0.3, 1.0)
    h = rng.uniform(0.2, 0.6)
    d = rng.uniform(0.3, 0.8)

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


def create_spinifex(position, seed):

    rng = random.Random(seed)
    radius = rng.uniform(0.15, 0.4)
    height = rng.uniform(0.15, 0.4)

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
