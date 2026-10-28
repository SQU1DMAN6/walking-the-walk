import math
import random
from functools import lru_cache
from engine.mesh import Mesh, MeshPose, create_prism, create_pyramid
from engine.worldgen import create_branch
from engine.animation import dog_motion, spear_motion, rotate_point


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


@lru_cache(maxsize=1)
def dog():
    fur, dark = (137, 91, 54), (69, 46, 32)
    parts = [('body', create_prism(.52, .42, .90, fur, (0, .60, 0))),
             ('head', create_prism(.40, .38, .38, fur, (0, .83, .55))),
             ('head', create_prism(.25, .12, .32, (174, 126, 79), (0, .78, .82))),
             ('head', create_prism(.19, .09, .04, dark, (0, .80, .995))),
             ('jaw', create_prism(.23, .08, .30, dark, (0, .66, .82))),
             ('tail', create_branch((0, .68, -.40), (0, .95, -.85), .12, fur))]
    for x in (-.18, .18):
        parts.append(('head', create_pyramid(.18, .30, .18, dark, (x, 1.12, .50))))
        parts.append(('head', create_prism(.055, .055, .045, (20, 18, 16), (x, .88, .745))))
        for z in (-.30, .31):
            parts.append(('leg', create_prism(.12, .42, .14, dark, (x, .25, z))))
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
        if mesh.joint=='jaw':rotations.append(((0,.72,.61),jaw*.55,0))
        if mesh.joint in ('head','jaw'):
            rotations.append(((0,.82,.45),.12*prepare+.10*strike,0))
        elif mesh.joint=='leg':
            x,_,z = mesh.position
            angle = math.sin(walk_phase)*walk_blend*.35*(1 if x*z>0 else -1)
            rotations.append(((x,.46,z),angle-.25*strike*(1 if z>0 else -1),0))
        elif mesh.joint=='tail':
            rotations.append(((0,.68,-.40),0,.12*math.sin(walk_phase)*walk_blend))
        rotations.append(((0,.60,0),.09*prepare-.08*strike,0))
        posed.append(MeshPose(mesh,rotations,(0,-.07*prepare+.06*strike,-.10*prepare+.32*strike)))
    return posed


def pose_spear(meshes, remaining):
    dx, dy, dz, pitch, yaw = spear_motion(remaining)
    posed = []
    for mesh in meshes:
        vertices = []
        for vertex in mesh.vertices:
            point = tuple(a+b for a, b in zip(vertex, mesh.position))
            x, y, z = rotate_point(point, (.33, -.40, .45), pitch, yaw)
            vertices.append((x+dx, y+dy, z+dz))
        posed.append(Mesh(vertices, mesh.faces, mesh.colour, (0, 0, 0), vertex_colours=mesh.vertex_colours))
    return posed


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


def axe():
    handle = create_branch((.43,-.65,.72),(.43,.25,1.03),.065,(139,94,46))
    collar = create_prism(.14,.15,.17,(91,101,98),(.43,.23,1.03))
    # Wedge edge faces forward. Hoe era is over.
    outline = [(.43,.34,.98),(.43,.12,.98),(.43,.06,1.45),(.43,.40,1.45)]
    vertices = [(x+side,y,z) for side in (-.075,.075) for x,y,z in outline]
    faces = [(0,1,2),(0,2,3),(4,6,5),(4,7,6),(0,4,5),(0,5,1),
             (1,5,6),(1,6,2),(3,2,6),(3,6,7),(0,3,7),(0,7,4)]
    head = Mesh(vertices,faces,(153,166,168),(0,0,0))
    edge = create_branch((.43,.06,1.45),(.43,.40,1.45),.035,(223,231,221))
    return [handle,collar,head,edge]


def pose_axe(meshes, remaining):
    from engine.animation import envelope
    motion = envelope(.45-max(0, remaining), 0, .18, .45)
    posed = []
    for mesh in meshes:
        points = [rotate_point(tuple(a+b for a, b in zip(v, mesh.position)), (.45, -.55, .65),
                               pitch=motion*1.15, yaw=-motion*.35) for v in mesh.vertices]
        posed.append(Mesh(points, mesh.faces, mesh.colour, (0, 0, motion*.15)))
    return posed


def leaves():
    return [Mesh([(-.25, .08, 0), (0, .16, -.25), (.25, .08, 0), (0, .06, .25)],
                 [(0, 1, 2), (0, 2, 3)], (101, 179, 84), (0, 0, 0))]


def bandage():
    return [create_prism(.30, .17, .23, (222, 218, 186), (0, .10, 0)),
            create_prism(.08, .015, .24, (137, 164, 119), (0, .19, 0))]


def skull_sign():
    meshes = [create_prism(.10, 1.45, .10, (124, 85, 50), (0, .72, 0)),
              create_prism(.78, .64, .09, (53, 38, 28), (0, 1.3, 0)),
              create_prism(.35, .33, .045, (235, 226, 197), (0, 1.35, .065)),
              create_prism(.22, .14, .045, (235, 226, 197), (0, 1.13, .065))]
    for x in (-.09, .09):
        meshes.append(create_prism(.08, .09, .025, (25, 25, 20), (x, 1.36, .10)))
    meshes.append(create_prism(.055, .055, .025, (25, 25, 20), (0, 1.24, .10)))
    for x in (-.06, 0, .06):
        meshes.append(create_prism(.018, .08, .025, (53, 38, 28), (x, 1.10, .10)))
    return meshes


@lru_cache(maxsize=1)
def spider():
    meshes = [lathe([(-.22, .05), (0, .48), (.22, .25), (.26, 0)], (66, 46, 40), 12),
              create_prism(.46, .25, .48, (83, 55, 42), (0, .44, .36))]
    meshes[0].position = (0, .46, -.25)
    for side in (-1, 1):
        for i in range(4):
            hip = (side*.20, .42, .38-i*.20)
            knee = (side*(.85+.12*math.sin(i)), .65, .8-i*.48)
            foot = (side*1.18, .06, 1.0-i*.60)
            for a, b in ((hip, knee), (knee, foot)):
                mesh = create_branch(a, b, .085, (56, 41, 34))
                mesh.leg = (side, i, hip)
                meshes.append(mesh)
        meshes.append(create_prism(.07, .055, .045, (200, 60, 39), (side*.12, .53, .615)))
    return meshes


def pose_spider(meshes, phase, moving, attack_time):
    from engine.animation import envelope
    from engine.run_config import SURVIVAL_SPIDER
    lunge = envelope(attack_time,.07,SURVIVAL_SPIDER['windup'],SURVIVAL_SPIDER['cooldown'])
    posed = []
    for mesh in meshes:
        rotations = []
        if hasattr(mesh,'leg'):
            side,index,hip = mesh.leg
            rotations.append((hip,0,math.sin(phase+index*math.pi/2)*moving*.20*side))
        posed.append(MeshPose(mesh,rotations,(0,.05*lunge,.25*lunge)))
    return posed


@lru_cache(maxsize=1)
def viper():
    parts = []
    for i in range(5):
        x = math.sin(i*.9)*.15
        mesh = create_branch((x,.16,-.65+i*.21),(math.sin((i+1)*.9)*.15,.19,-.44+i*.21),.11,(93,126,43))
        parts.append(mesh)
    parts.append(create_prism(.28,.17,.30,(105,151,50),(0,.22,.55)))
    for side in (-1,1):
        parts.append(create_prism(.045,.04,.025,(223,104,239),(side*.09,.27,.71)))
        parts.append(create_branch((side*.07,.17,.66),(side*.07,.08,.75),.018,(235,222,192)))
    return parts


def pose_viper(meshes,phase,time):
    from engine.animation import envelope
    from engine.run_config import VENOM
    strike = envelope(time,0,VENOM['windup'],VENOM['cooldown'])
    return [MeshPose(m,[((0,.16,0),0,math.sin(phase+i*.6)*.08)],(0,.03*strike,.3*strike))
            for i,m in enumerate(meshes)]


@lru_cache(maxsize=2)
def demon(phase=1):
    skin = (111,39,36) if phase==1 else (172,53,30)
    parts = [create_prism(1.25,1.55,.85,skin,(0,1.65,0)),
             create_prism(.75,.70,.65,(70,34,38),(0,2.77,.12)),
             create_prism(.62,.18,.20,(42,25,26),(0,2.56,.51))]
    for side in (-1,1):
        parts.extend([create_branch((side*.3,3.03,.05),(side*.65,3.82,-.12),.16,(222,196,140)),
                      create_prism(.16,.08,.04,(255,155 if phase==1 else 232,42),(side*.19,2.85,.46)),
                      create_branch((side*.4,1.0,0),(side*.45,.1,.22),.25,(64,38,38))])
        arm = create_branch((side*.65,2.1,0),(side*.9,1.4,.8),.24,skin)
        arm.arm = side
        parts.append(arm)
        claw = create_branch((side*.9,1.4,.8),(side*.6,1.25,2.7),.11,(199,178,139))
        claw.arm = side
        parts.append(claw)
    return parts


def pose_demon(meshes,state,time,phase,moving):
    from engine.animation import envelope
    from engine.run_config import BOSS
    sweep = envelope(time,0,BOSS['cleave']['windup'],BOSS['cleave']['windup']+BOSS['cleave']['active']) if state=='cleave' else 0
    raise_arms = envelope(time,0,BOSS['slam']['windup'],BOSS['slam']['windup']+BOSS['slam']['active']) if state=='slam' else 0
    result = []
    for mesh in meshes:
        rotations = []
        if hasattr(mesh,'arm'):
            rotations = [((mesh.arm*.65,2.1,0),-.8*raise_arms,-mesh.arm*.55*sweep)]
        result.append(MeshPose(mesh,rotations,(0,math.sin(phase)*moving*.035,0)))
    return result


def boss_omen():
    parts = []
    for side in (-1,1):
        parts.extend([create_branch((side*.65,0,0),(side*.65,2.1,0),.13,(58,42,38)),
                      create_prism(.60,.85,.06,(151,46,38),(side*.65,1.45,.05))])
    parts.append(create_prism(1.8,.18,.15,(52,37,33),(0,2.0,0)))
    return parts
