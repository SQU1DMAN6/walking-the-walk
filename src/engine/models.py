import math
import random
from engine.mesh import Mesh, create_prism, create_pyramid
from engine.worldgen import create_branch


def lathe(profile, colour, sides=16):

    vertices = [(r * math.cos(i * math.tau / sides), y, r * math.sin(i * math.tau / sides))
                for y, r in profile for i in range(sides)]
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(sides):
            a, b = ring * sides + i, ring * sides + (i + 1) % sides
            faces.extend(((a, a + sides, b), (b, a + sides, b + sides)))
    vertices.extend(((0, profile[0][0], 0), (0, profile[-1][0], 0)))
    bottom, top = len(vertices) - 2, len(vertices) - 1
    for i in range(sides):
        j = (i + 1) % sides
        faces.extend(((bottom, i, j), (top, (len(profile) - 1) * sides + j,
                                     (len(profile) - 1) * sides + i)))
    return Mesh(vertices, faces, colour, (0, 0, 0))


CONTAINER_SCALE = .6


def scaled_meshes(meshes, scale):
    return [Mesh([tuple(value*scale for value in vertex) for vertex in mesh.vertices],
                 mesh.faces, mesh.colour, tuple(value*scale for value in mesh.position),
                 texcoords=mesh.texcoords, vertex_colours=mesh.vertex_colours, alpha=mesh.alpha)
            for mesh in meshes]


def food_can():
    return scaled_meshes([lathe([(0.02, .23), (.05, .25), (.08, .23), (.48, .23),
                   (.51, .25), (.54, .25)], (165, 176, 182)),
            lathe([(.08, .235), (.16, .235)], (80, 111, 91)),
            create_prism(.11, .015, .05, (70, 80, 85), (0, .555, 0))], CONTAINER_SCALE)


def plastic_bottle():
    return scaled_meshes([lathe([(.02, .20), (.08, .23), (.45, .23), (.56, .18),
                   (.67, .085), (.77, .085)], (123, 193, 210)),
            lathe([(.76, .10), (.84, .10)], (43, 89, 174)),
            lathe([(.22, .235), (.39, .235)], (204, 226, 214))], CONTAINER_SCALE)


def stick():
    return [create_branch((-.48, .10, -.12), (.05, .13, .06), .12, (120, 80, 42)),
            create_branch((.05, .13, .06), (.57, .09, .16), .09, (137, 96, 52)),
            create_branch((.04, .12, .06), (.24, .14, -.23), .055, (125, 86, 44))]


def rock(seed=0):
    rng = random.Random(seed)
    verts = [(0, .42, 0), (0, .03, 0)]
    for i in range(7):
        a = i * math.tau / 7
        r = rng.uniform(.23, .39)
        verts.append((r * math.cos(a), rng.uniform(.08, .20), r * math.sin(a)))
    faces = []
    for i in range(7):
        a, b = 2 + i, 2 + (i + 1) % 7
        faces.extend(((0, b, a), (1, a, b)))
    return [Mesh(verts, faces, (142, 146, 138), (0, 0, 0))]


def spear():
    shaft = create_branch((.33, -.45, .35), (.33, -.30, 1.85), .07, (142, 100, 54))
    tip = Mesh([(.33, -.30, 2.12), (.21, -.37, 1.80), (.45, -.37, 1.80),
                (.33, -.18, 1.80)], [(0, 1, 2), (0, 2, 3), (0, 3, 1), (1, 3, 2)],
               (185, 190, 182), (0, 0, 0))
    return [shaft, tip]


def dog():

    fur, dark = (137, 91, 54), (69, 46, 32)
    meshes = [create_prism(.52, .42, .90, fur, (0, .60, 0)),
              create_prism(.40, .38, .38, fur, (0, .83, .55)),
              create_prism(.25, .18, .32, (174, 126, 79), (0, .74, .82)),
              create_prism(.19, .09, .04, dark, (0, .76, .995)),
              create_branch((0, .68, -.40), (0, .95, -.85), .12, fur)]
    for x in (-.18, .18):
        meshes.append(create_pyramid(.18, .30, .18, dark, (x, 1.12, .50)))
        meshes.append(create_prism(.055, .055, .045, (20, 18, 16), (x, .88, .745)))
        for z in (-.30, .31):
            meshes.append(create_prism(.12, .42, .14, dark, (x, .25, z)))
    return meshes


def beacon():
    return [lathe([(0, .30), (.20, .30), (.20, .13), (1.55, .13)], (90, 110, 112)),
            lathe([(1.55, .28), (1.90, .28)], (100, 228, 211)),
            lathe([(1.90, .32), (1.97, .32)], (219, 232, 209))]


def compass():
    case = lathe([(0, .27), (.045, .28), (.065, .25)], (158, 132, 70), sides=32)
    dial = lathe([(.066, .235), (.073, .235)], (235, 225, 189), sides=32)
    rim = lathe([(.066, .28), (.094, .28)], (183, 150, 79), sides=32)

    rim.faces = rim.faces[:64]
    marks = []
    for i in range(12):
        angle = math.tau*i/12
        mark = create_prism(.013, .004, .030 if i % 3 else .05, (51, 58, 49),
                            (.19*math.sin(angle), .078, .19*math.cos(angle)))
        mark.vertices = [(x*math.cos(angle)+z*math.sin(angle), y,
                          -x*math.sin(angle)+z*math.cos(angle)) for x, y, z in mark.vertices]
        marks.append(mark)
    needle = Mesh([(0, .09, .19), (-.047, .09, -.035), (.047, .09, -.035),
                   (0, .09, -.16)], [(0, 2, 1), (3, 1, 2)], (224, 38, 44), (0, 0, 0),
                  vertex_colours=[(238, 37, 46), (216, 48, 48), (216, 48, 48), (212, 211, 198)])
    return [case, dial, rim, *marks], needle


def held_prop(meshes, scale=.65):
    return [Mesh([((x+mesh.position[0])*scale+.62, (y+mesh.position[1])*scale-.24,
                   (z+mesh.position[2])*scale+1.2) for x, y, z in mesh.vertices],
                 mesh.faces, mesh.colour, (0, 0, 0), vertex_colours=mesh.vertex_colours)
            for mesh in meshes]


def pose_compass(mesh, yaw=0):
    vertices = []
    cy, sy = math.cos(yaw), math.sin(yaw)
    ct, st = math.cos(-1.0), math.sin(-1.0)
    for x, y, z in mesh.vertices:
        x, y, z = x+mesh.position[0], y+mesh.position[1], z+mesh.position[2]
        x, z = x*cy+z*sy, -x*sy+z*cy
        vertices.append((x*.65+.66, (y*ct-z*st)*.65+.02, (y*st+z*ct)*.65+1.35))
    return Mesh(vertices, mesh.faces, mesh.colour, (0, 0, 0), vertex_colours=mesh.vertex_colours)


RESOURCE_MODELS = {"can": food_can, "bottle": plastic_bottle, "stick": stick, "rock": rock}
