import math
import random
from functools import lru_cache

from engine.animation import dog_motion, rotate_point, spear_motion
from engine.mesh import Mesh, MeshPose, create_prism, create_pyramid
from engine.worldgen import create_branch


def lathe(profile, colour, sides=16):

    vertices = [
        (r * math.cos(i * math.tau / sides), y, r * math.sin(i * math.tau / sides))
        for y, r in profile
        for i in range(sides)
    ]
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(sides):
            a, b = ring * sides + i, ring * sides + (i + 1) % sides
            faces.extend(((a, a + sides, b), (b, a + sides, b + sides)))
    vertices.extend(((0, profile[0][0], 0), (0, profile[-1][0], 0)))
    bottom, top = len(vertices) - 2, len(vertices) - 1
    for i in range(sides):
        j = (i + 1) % sides
        faces.extend(
            (
                (bottom, i, j),
                (top, (len(profile) - 1) * sides + j, (len(profile) - 1) * sides + i),
            )
        )
    return Mesh(vertices, faces, colour, (0, 0, 0))


CONTAINER_SCALE = 0.6


def scaled_meshes(meshes, scale):
    return [
        Mesh(
            [tuple(value * scale for value in vertex) for vertex in mesh.vertices],
            mesh.faces,
            mesh.colour,
            tuple(value * scale for value in mesh.position),
            texcoords=mesh.texcoords,
            vertex_colours=mesh.vertex_colours,
            alpha=mesh.alpha,
        )
        for mesh in meshes
    ]


def food_can():
    return scaled_meshes(
        [
            lathe(
                [
                    (0.02, 0.23),
                    (0.05, 0.25),
                    (0.08, 0.23),
                    (0.48, 0.23),
                    (0.51, 0.25),
                    (0.54, 0.25),
                ],
                (165, 176, 182),
            ),
            lathe([(0.08, 0.235), (0.16, 0.235)], (80, 111, 91)),
            create_prism(0.11, 0.015, 0.05, (70, 80, 85), (0, 0.555, 0)),
        ],
        CONTAINER_SCALE,
    )


def plastic_bottle():
    return scaled_meshes(
        [
            lathe(
                [
                    (0.02, 0.20),
                    (0.08, 0.23),
                    (0.45, 0.23),
                    (0.56, 0.18),
                    (0.67, 0.085),
                    (0.77, 0.085),
                ],
                (123, 193, 210),
            ),
            lathe([(0.76, 0.10), (0.84, 0.10)], (43, 89, 174)),
            lathe([(0.22, 0.235), (0.39, 0.235)], (204, 226, 214)),
        ],
        CONTAINER_SCALE,
    )


def stick():
    return [
        create_branch((-0.48, 0.10, -0.12), (0.05, 0.13, 0.06), 0.12, (120, 80, 42)),
        create_branch((0.05, 0.13, 0.06), (0.57, 0.09, 0.16), 0.09, (137, 96, 52)),
        create_branch((0.04, 0.12, 0.06), (0.24, 0.14, -0.23), 0.055, (125, 86, 44)),
    ]


def rock(seed=0):
    rng = random.Random(seed)
    verts = [(0, 0.42, 0), (0, 0.03, 0)]
    for i in range(7):
        a = i * math.tau / 7
        r = rng.uniform(0.23, 0.39)
        verts.append((r * math.cos(a), rng.uniform(0.08, 0.20), r * math.sin(a)))
    faces = []
    for i in range(7):
        a, b = 2 + i, 2 + (i + 1) % 7
        faces.extend(((0, b, a), (1, a, b)))
    return [Mesh(verts, faces, (142, 146, 138), (0, 0, 0))]


def spear():
    shaft = create_branch(
        (0.33, -0.45, 0.35), (0.33, -0.30, 1.85), 0.07, (142, 100, 54)
    )
    tip = Mesh(
        [
            (0.33, -0.30, 2.12),
            (0.21, -0.37, 1.80),
            (0.45, -0.37, 1.80),
            (0.33, -0.18, 1.80),
        ],
        [(0, 1, 2), (0, 2, 3), (0, 3, 1), (1, 3, 2)],
        (185, 190, 182),
        (0, 0, 0),
    )
    return [shaft, tip]


@lru_cache(maxsize=1)
def dog():
    fur, dark = (137, 91, 54), (69, 46, 32)
    parts = [
        ("body", create_prism(0.52, 0.42, 0.90, fur, (0, 0.60, 0))),
        ("head", create_prism(0.40, 0.38, 0.38, fur, (0, 0.83, 0.55))),
        ("head", create_prism(0.25, 0.12, 0.32, (174, 126, 79), (0, 0.78, 0.82))),
        ("head", create_prism(0.19, 0.09, 0.04, dark, (0, 0.80, 0.995))),
        ("jaw", create_prism(0.23, 0.08, 0.30, dark, (0, 0.66, 0.82))),
        ("tail", create_branch((0, 0.68, -0.40), (0, 0.95, -0.85), 0.12, fur)),
    ]
    for x in (-0.18, 0.18):
        parts.append(("head", create_pyramid(0.18, 0.30, 0.18, dark, (x, 1.12, 0.50))))
        parts.append(
            ("head", create_prism(0.055, 0.055, 0.045, (20, 18, 16), (x, 0.88, 0.745)))
        )
        for z in (-0.30, 0.31):
            parts.append(("leg", create_prism(0.12, 0.42, 0.14, dark, (x, 0.25, z))))
    for joint, mesh in parts:
        mesh.joint = joint
    return [mesh for _, mesh in parts]


def pose_dog(meshes, time, walk_phase=0, walk_blend=0):
    prepare, strike, jaw = dog_motion(time)
    if not (prepare or strike or jaw) and walk_blend <= 1e-5:
        return meshes
    posed = []
    for mesh in meshes:
        rotations = []
        if mesh.joint == "jaw":
            rotations.append(((0, 0.72, 0.61), jaw * 0.55, 0))
        if mesh.joint in ("head", "jaw"):
            rotations.append(((0, 0.82, 0.45), 0.12 * prepare + 0.10 * strike, 0))
        elif mesh.joint == "leg":
            x, _, z = mesh.position
            angle = math.sin(walk_phase) * walk_blend * 0.35 * (1 if x * z > 0 else -1)
            rotations.append(
                ((x, 0.46, z), angle - 0.25 * strike * (1 if z > 0 else -1), 0)
            )
        elif mesh.joint == "tail":
            rotations.append(
                ((0, 0.68, -0.40), 0, 0.12 * math.sin(walk_phase) * walk_blend)
            )
        rotations.append(((0, 0.60, 0), 0.09 * prepare - 0.08 * strike, 0))
        posed.append(
            MeshPose(
                mesh,
                rotations,
                (0, -0.07 * prepare + 0.06 * strike, -0.10 * prepare + 0.32 * strike),
            )
        )
    return posed


def pose_spear(meshes, remaining):
    dx, dy, dz, pitch, yaw = spear_motion(remaining)
    posed = []
    for mesh in meshes:
        vertices = []
        for vertex in mesh.vertices:
            point = tuple(a + b for a, b in zip(vertex, mesh.position))
            x, y, z = rotate_point(point, (0.33, -0.40, 0.45), pitch, yaw)
            vertices.append((x + dx, y + dy, z + dz))
        posed.append(
            Mesh(
                vertices,
                mesh.faces,
                mesh.colour,
                (0, 0, 0),
                vertex_colours=mesh.vertex_colours,
            )
        )
    return posed


def beacon():
    return [
        lathe([(0, 0.30), (0.20, 0.30), (0.20, 0.13), (1.55, 0.13)], (90, 110, 112)),
        lathe([(1.55, 0.28), (1.90, 0.28)], (100, 228, 211)),
        lathe([(1.90, 0.32), (1.97, 0.32)], (219, 232, 209)),
    ]


def compass():
    case = lathe([(0, 0.27), (0.045, 0.28), (0.065, 0.25)], (158, 132, 70), sides=32)
    dial = lathe([(0.066, 0.235), (0.073, 0.235)], (235, 225, 189), sides=32)
    rim = lathe([(0.066, 0.28), (0.094, 0.28)], (183, 150, 79), sides=32)

    rim.faces = rim.faces[:64]
    marks = []
    for i in range(12):
        angle = math.tau * i / 12
        mark = create_prism(
            0.013,
            0.004,
            0.030 if i % 3 else 0.05,
            (51, 58, 49),
            (0.19 * math.sin(angle), 0.078, 0.19 * math.cos(angle)),
        )
        mark.vertices = [
            (
                x * math.cos(angle) + z * math.sin(angle),
                y,
                -x * math.sin(angle) + z * math.cos(angle),
            )
            for x, y, z in mark.vertices
        ]
        marks.append(mark)
    needle = Mesh(
        [
            (0, 0.09, 0.19),
            (-0.047, 0.09, -0.035),
            (0.047, 0.09, -0.035),
            (0, 0.09, -0.16),
        ],
        [(0, 2, 1), (3, 1, 2)],
        (224, 38, 44),
        (0, 0, 0),
        vertex_colours=[(238, 37, 46), (216, 48, 48), (216, 48, 48), (212, 211, 198)],
    )
    return [case, dial, rim, *marks], needle


def held_prop(meshes, scale=0.65):
    return [
        Mesh(
            [
                (
                    (x + mesh.position[0]) * scale + 0.62,
                    (y + mesh.position[1]) * scale - 0.24,
                    (z + mesh.position[2]) * scale + 1.2,
                )
                for x, y, z in mesh.vertices
            ],
            mesh.faces,
            mesh.colour,
            (0, 0, 0),
            vertex_colours=mesh.vertex_colours,
        )
        for mesh in meshes
    ]


def pose_compass(mesh, yaw=0):
    vertices = []
    cy, sy = math.cos(yaw), math.sin(yaw)
    ct, st = math.cos(-1.0), math.sin(-1.0)
    for x, y, z in mesh.vertices:
        x, y, z = x + mesh.position[0], y + mesh.position[1], z + mesh.position[2]
        x, z = x * cy + z * sy, -x * sy + z * cy
        vertices.append(
            (
                x * 0.65 + 0.66,
                (y * ct - z * st) * 0.65 + 0.02,
                (y * st + z * ct) * 0.65 + 1.35,
            )
        )
    return Mesh(
        vertices, mesh.faces, mesh.colour, (0, 0, 0), vertex_colours=mesh.vertex_colours
    )


RESOURCE_MODELS = {
    "can": food_can,
    "bottle": plastic_bottle,
    "stick": stick,
    "rock": rock,
}


def axe():
    handle = create_branch(
        (0.43, -0.65, 0.72), (0.43, 0.25, 1.03), 0.065, (139, 94, 46)
    )
    collar = create_prism(0.14, 0.15, 0.17, (91, 101, 98), (0.43, 0.23, 1.03))
    # Actual edge, zero fridge-door energy.
    vertices = [
        (0.355, 0.12, 0.98),
        (0.505, 0.12, 0.98),
        (0.43, 0.06, 1.45),
        (0.355, 0.34, 0.98),
        (0.505, 0.34, 0.98),
        (0.43, 0.40, 1.45),
    ]
    faces = [
        (0, 1, 2),
        (3, 5, 4),
        (0, 4, 1),
        (0, 3, 4),
        (1, 5, 2),
        (1, 4, 5),
        (2, 3, 0),
        (2, 5, 3),
    ]
    head = Mesh(vertices, faces, (153, 166, 168), (0, 0, 0))
    edge = Mesh(
        [
            (0.413, 0.06, 1.41),
            (0.447, 0.06, 1.41),
            (0.43, 0.06, 1.45),
            (0.413, 0.40, 1.41),
            (0.447, 0.40, 1.41),
            (0.43, 0.40, 1.45),
        ],
        faces,
        (223, 231, 221),
        (0, 0, 0),
    )
    return [handle, collar, head, edge]


def world_axe():
    return [
        Mesh(
            [
                (
                    x + mesh.position[0] - 0.43,
                    y + mesh.position[1] + 0.72,
                    z + mesh.position[2] - 0.9,
                )
                for x, y, z in mesh.vertices
            ],
            mesh.faces,
            mesh.colour,
            (0, 0, 0),
        )
        for mesh in axe()
    ]


def pose_axe(meshes, remaining):
    from engine.animation import envelope

    motion = envelope(0.45 - max(0, remaining), 0, 0.18, 0.45)
    return [
        MeshPose(
            mesh,
            (((0.45, -0.55, 0.65), motion * 1.15, -motion * 0.35),),
            (0, 0, motion * 0.15),
        )
        for mesh in meshes
    ]


def pose_chop(meshes, remaining):
    from engine.animation import envelope

    elapsed = 0.45 - max(0.0, min(0.45, remaining))
    prepare = envelope(elapsed, 0, 0.07, 0.18)
    strike = envelope(elapsed, 0.07, 0.18, 0.45)
    pivot = (0.45, -0.55, 0.65)
    return [
        MeshPose(
            mesh,
            ((pivot, -0.06 * prepare + 0.10 * strike, 0.38 * prepare - 0.95 * strike),),
            (0, -0.16 * strike, 0.12 * strike),
        )
        for mesh in meshes
    ]


def leaves():
    return [
        Mesh(
            [(-0.25, 0.08, 0), (0, 0.16, -0.25), (0.25, 0.08, 0), (0, 0.06, 0.25)],
            [(0, 1, 2), (0, 2, 3)],
            (101, 179, 84),
            (0, 0, 0),
        )
    ]


def bandage():
    return [
        create_prism(0.30, 0.17, 0.23, (222, 218, 186), (0, 0.10, 0)),
        create_prism(0.08, 0.015, 0.24, (137, 164, 119), (0, 0.19, 0)),
    ]


def skull_sign():
    meshes = [
        create_prism(0.10, 1.45, 0.10, (124, 85, 50), (0, 0.72, 0)),
        create_prism(0.78, 0.64, 0.09, (53, 38, 28), (0, 1.3, 0)),
        create_prism(0.35, 0.33, 0.045, (235, 226, 197), (0, 1.35, 0.065)),
        create_prism(0.22, 0.14, 0.045, (235, 226, 197), (0, 1.13, 0.065)),
    ]
    for x in (-0.09, 0.09):
        meshes.append(create_prism(0.08, 0.09, 0.025, (25, 25, 20), (x, 1.36, 0.10)))
    meshes.append(create_prism(0.055, 0.055, 0.025, (25, 25, 20), (0, 1.24, 0.10)))
    for x in (-0.06, 0, 0.06):
        meshes.append(create_prism(0.018, 0.08, 0.025, (53, 38, 28), (x, 1.10, 0.10)))
    return meshes


@lru_cache(maxsize=1)
def spider():
    meshes = [
        lathe([(-0.22, 0.05), (0, 0.48), (0.22, 0.25), (0.26, 0)], (66, 46, 40), 12),
        create_prism(0.46, 0.25, 0.48, (83, 55, 42), (0, 0.44, 0.36)),
    ]
    meshes[0].position = (0, 0.46, -0.25)
    for side in (-1, 1):
        for i in range(4):
            hip = (side * 0.20, 0.42, 0.38 - i * 0.20)
            knee = (side * (0.85 + 0.12 * math.sin(i)), 0.65, 0.8 - i * 0.48)
            foot = (side * 1.18, 0.06, 1.0 - i * 0.60)
            for a, b in ((hip, knee), (knee, foot)):
                mesh = create_branch(a, b, 0.085, (56, 41, 34))
                mesh.leg = (side, i, hip)
                meshes.append(mesh)
        meshes.append(
            create_prism(0.07, 0.055, 0.045, (200, 60, 39), (side * 0.12, 0.53, 0.615))
        )
    return meshes


def pose_spider(meshes, phase, moving, attack_time):
    from engine.animation import envelope
    from engine.run_config import SURVIVAL_SPIDER

    lunge = envelope(
        attack_time, 0.07, SURVIVAL_SPIDER["windup"], SURVIVAL_SPIDER["cooldown"]
    )
    posed = []
    for mesh in meshes:
        rotations = []
        if hasattr(mesh, "leg"):
            side, index, hip = mesh.leg
            rotations.append(
                (hip, 0, math.sin(phase + index * math.pi / 2) * moving * 0.20 * side)
            )
        posed.append(MeshPose(mesh, rotations, (0, 0.05 * lunge, 0.25 * lunge)))
    return posed


@lru_cache(maxsize=1)
def viper():
    parts = []
    for i in range(5):
        x = math.sin(i * 0.9) * 0.15
        mesh = create_branch(
            (x, 0.16, -0.65 + i * 0.21),
            (math.sin((i + 1) * 0.9) * 0.15, 0.19, -0.44 + i * 0.21),
            0.11,
            (93, 126, 43),
        )
        parts.append(mesh)
    parts.append(create_prism(0.28, 0.17, 0.30, (105, 151, 50), (0, 0.22, 0.55)))
    for side in (-1, 1):
        parts.append(
            create_prism(0.045, 0.04, 0.025, (223, 104, 239), (side * 0.09, 0.27, 0.71))
        )
        parts.append(
            create_branch(
                (side * 0.07, 0.17, 0.66),
                (side * 0.07, 0.08, 0.75),
                0.018,
                (235, 222, 192),
            )
        )
    return parts


def pose_viper(meshes, phase, time):
    from engine.animation import envelope
    from engine.run_config import VENOM

    strike = envelope(time, 0, VENOM["windup"], VENOM["cooldown"])
    return [
        MeshPose(
            m,
            [((0, 0.16, 0), 0, math.sin(phase + i * 0.6) * 0.08)],
            (0, 0.03 * strike, 0.3 * strike),
        )
        for i, m in enumerate(meshes)
    ]


@lru_cache(maxsize=2)
def demon(phase=1):
    skin = (111, 39, 36) if phase == 1 else (172, 53, 30)
    parts = [
        create_prism(1.25, 1.55, 0.85, skin, (0, 1.65, 0)),
        create_prism(0.75, 0.70, 0.65, (70, 34, 38), (0, 2.77, 0.12)),
        create_prism(0.62, 0.18, 0.20, (42, 25, 26), (0, 2.56, 0.51)),
    ]
    for side in (-1, 1):
        parts.extend(
            [
                create_branch(
                    (side * 0.3, 3.03, 0.05),
                    (side * 0.65, 3.82, -0.12),
                    0.16,
                    (222, 196, 140),
                ),
                create_prism(
                    0.16,
                    0.08,
                    0.04,
                    (255, 155 if phase == 1 else 232, 42),
                    (side * 0.19, 2.85, 0.46),
                ),
                create_branch(
                    (side * 0.4, 1.0, 0), (side * 0.45, 0.1, 0.22), 0.25, (64, 38, 38)
                ),
            ]
        )
        parts[-1].leg = side
        arm = create_branch((side * 0.65, 2.1, 0), (side * 0.9, 1.4, 0.8), 0.24, skin)
        arm.arm = side
        parts.append(arm)
        claw = create_branch(
            (side * 0.9, 1.4, 0.8), (side * 0.6, 1.25, 2.7), 0.11, (199, 178, 139)
        )
        claw.arm = side
        parts.append(claw)
    return parts


def pose_demon(
    meshes, state, time, phase, moving, recovery_duration=1.0, last_attack="cleave"
):
    from engine.animation import ease
    from engine.run_config import BOSS

    prepare = strike = 0.0
    if state in ("cleave", "slam", "spin", "charge"):
        profile = BOSS[state]
        prepare = ease(time / profile["windup"])
        strike = ease((time - profile["windup"]) / profile["active"])
    recover = (
        1 - ease(time / max(0.01, recovery_duration)) if state == "recover" else 0.0
    )
    result = []
    for mesh in meshes:
        rotations = []
        if hasattr(mesh, "arm"):
            side = mesh.arm
            pitch, turn = 0.0, 0.0
            if recover:
                pitch = {"cleave": 0.0, "slam": 0.7, "spin": -0.55, "charge": -0.5}[
                    last_attack
                ] * recover
                turn = (
                    side
                    * {"cleave": -0.7, "slam": 0.0, "spin": 0.9, "charge": 0.45}[
                        last_attack
                    ]
                    * recover
                )
            if state == "slam":
                pitch = -1.8 * prepare + 2.5 * strike
            elif state == "cleave":
                turn = side * (0.65 * prepare - 1.35 * strike)
            elif state == "spin":
                pitch, turn = -0.55 * prepare, side * 0.9 * prepare
            elif state == "charge":
                pitch, turn = -0.5 * prepare, side * 0.45 * prepare
            rotations.append(((side * 0.65, 2.1, 0), pitch, turn))
        if hasattr(mesh, "leg"):
            rotations.append(
                (
                    (mesh.leg * 0.4, 1.0, 0),
                    math.sin(phase + (math.pi if mesh.leg < 0 else 0)) * moving * 0.20,
                    0,
                )
            )
        if state == "spin":
            rotations.append(((0, 1.0, 0), -0.08 * prepare, math.tau * strike))
        elif state == "charge":
            rotations.append(((0, 0.7, 0), 0.28 * prepare, 0))
        elif recover:
            rotations.append(
                (
                    (0, 1.0 if last_attack == "spin" else 0.7, 0),
                    {"cleave": 0.0, "slam": 0.0, "spin": -0.08, "charge": 0.28}[
                        last_attack
                    ]
                    * recover,
                    0,
                )
            )
        result.append(
            MeshPose(mesh, rotations, (0, math.sin(phase) * moving * 0.035, 0))
        )
    return result


def boss_omen():
    parts = []
    for side in (-1, 1):
        parts.extend(
            [
                create_branch(
                    (side * 0.65, 0, 0), (side * 0.65, 2.1, 0), 0.13, (58, 42, 38)
                ),
                create_prism(
                    0.60, 0.85, 0.06, (151, 46, 38), (side * 0.65, 1.45, 0.05)
                ),
            ]
        )
    parts.append(create_prism(1.8, 0.18, 0.15, (52, 37, 33), (0, 2.0, 0)))
    return parts
