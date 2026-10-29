import math
import random

from engine.mesh import Mesh
from engine.models import lathe


def _merge(parts,colour):
    vertices,faces,colours=[],[],[]
    for points,triangles,tint in parts:
        offset=len(vertices)
        vertices.extend(points)
        faces.extend(tuple(i+offset for i in face) for face in triangles)
        colours.extend([tint]*len(points))
    return Mesh(vertices,faces,colour,(0,0,0),vertex_colours=colours)


def _branch(start,end,radius,colour,sides=3):
    dx,dy,dz=(b-a for a,b in zip(start,end));length=math.sqrt(dx*dx+dy*dy+dz*dz)
    axis=(dx/length,dy/length,dz/length)
    sideways=(axis[2],0,-axis[0]);norm=math.hypot(sideways[0],sideways[2])
    sideways=(1,0,0) if norm<1e-8 else tuple(v/norm for v in sideways)
    up=(axis[1]*sideways[2]-axis[2]*sideways[1],axis[2]*sideways[0]-axis[0]*sideways[2],axis[0]*sideways[1]-axis[1]*sideways[0])
    points=[]
    for centre,scale in ((start,1),(end,.28)):
        for i in range(sides):
            angle=i*math.tau/sides
            points.append(tuple(centre[j]+radius*scale*(math.cos(angle)*sideways[j]+math.sin(angle)*up[j]) for j in range(3)))
    faces=[]
    for i in range(sides):
        j=(i+1)%sides
        faces.extend(((i,j,sides+i),(j,sides+j,sides+i)))
    for i in range(1,sides-1):faces.extend(((0,i+1,i),(sides,sides+i,sides+i+1)))
    return points,faces,colour


def _leaves(centre,size,colour):
    x,y,z=centre;rx,ry,rz=size
    points=[(x-rx,y,z),(x+rx,y,z),(x,y-ry,z),(x,y+ry,z),(x,y,z-rz),(x,y,z+rz)]
    faces=[(3,0,4),(3,4,1),(3,1,5),(3,5,0),(2,4,0),(2,1,4),(2,5,1),(2,0,5)]
    return points,faces,colour


def forest_tree(position,seed,height=6.5,radius=.35,density=.5):
    rng=random.Random(seed)
    bark=(rng.randint(98,112),rng.randint(67,80),rng.randint(38,49))
    trunk=lathe([(0,radius),(height*.36,radius*.82),(height*.8,radius*.5),(height,.07)],bark,6)
    crown_width=rng.uniform(2.1,3.05)
    crown=lathe([(height*.60,.25),(height*.72,crown_width*.83),
                 (height*.87,crown_width),(height*.99,crown_width*.62),(height+rng.uniform(.3,.7),0)],
                (34,rng.randint(92,120),49),7)
    turn=rng.random()*math.tau
    crown.vertices=[(x*(1+.13*math.sin(i*1.7+turn)),y,z*rng.uniform(.86,1.12)) for i,(x,y,z) in enumerate(crown.vertices)]
    wood,leaves=[],[]
    for i in range(rng.randint(6,9)):
        angle=turn+i*2.39996+rng.uniform(-.35,.35)
        origin=(0,height*rng.uniform(.43,.77),0)
        reach=crown_width*rng.uniform(.65,1.0)
        end=(math.sin(angle)*reach,height*rng.uniform(.70,.98),math.cos(angle)*reach)
        wood.append(_branch(origin,end,radius*rng.uniform(.24,.39),bark,4))
        for sign in (-1,1):
            fork_angle=angle+sign*rng.uniform(.35,.85)
            tip=(end[0]+math.sin(fork_angle)*rng.uniform(.45,.85),end[1]+rng.uniform(.05,.6),end[2]+math.cos(fork_angle)*rng.uniform(.45,.85))
            wood.append(_branch(end,tip,radius*.14,bark))
            twig=(tip[0]+math.sin(fork_angle+.5)*.38,tip[1]+rng.uniform(.15,.4),tip[2]+math.cos(fork_angle+.5)*.38)
            wood.append(_branch(tip,twig,radius*.055,bark))
            tint=(rng.randint(39,62),rng.randint(105,143),rng.randint(48,72))
            leaves.append(_leaves(twig,(rng.uniform(.35,.65),rng.uniform(.18,.35),rng.uniform(.35,.65)),tint))
            leaves.append(_leaves(tip,(rng.uniform(.5,.8),rng.uniform(.25,.45),rng.uniform(.5,.8)),tint))
    branches=_merge(wood,bark);foliage=_merge(leaves,(48,121,60))
    # Four meshes per tree. The branches get a family tree, not a draw-call army.
    for mesh in (trunk,branches,crown,foliage):mesh.position=position
    return [trunk,branches,crown,foliage]
