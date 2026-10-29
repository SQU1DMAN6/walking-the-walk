import math
import random

from engine.mesh import Mesh

RINGS={sides:tuple((math.cos(i*math.tau/sides),math.sin(i*math.tau/sides)) for i in range(sides)) for sides in (3,5,7)}

def _merge(parts,colour):
    vertices,faces,colours=[],[],[]
    for points,triangles,tint in parts:
        offset=len(vertices)
        vertices.extend(points)
        faces.extend((a+offset,b+offset,c+offset) for a,b,c in triangles)
        colours.extend([tint]*len(points))
    return Mesh(vertices,faces,colour,(0,0,0),vertex_colours=colours)


def _tube(centres,radii,colour,sides=5):
    points=[]
    for index,(centre,radius) in enumerate(zip(centres,radii)):
        a,b=centres[max(0,index-1)],centres[min(len(centres)-1,index+1)]
        dx,dy,dz=b[0]-a[0],b[1]-a[1],b[2]-a[2]
        length=math.sqrt(dx*dx+dy*dy+dz*dz)
        axis=(dx/length,dy/length,dz/length)
        norm=math.hypot(dx,dz)
        side=(dz/norm,0,-dx/norm) if norm>.00001 else (1,0,0)
        up=(axis[1]*side[2],axis[2]*side[0]-axis[0]*side[2],-axis[1]*side[0])
        for c,s in RINGS[sides]:
            points.append((centre[0]+radius*(c*side[0]+s*up[0]),
                           centre[1]+radius*s*up[1],centre[2]+radius*(c*side[2]+s*up[2])))
    faces=[]
    for ring in range(len(centres)-1):
        for i in range(sides):
            a=ring*sides+i;b=ring*sides+(i+1)%sides
            faces.extend(((a,b,a+sides),(b,b+sides,a+sides)))
    for i in range(1,sides-1):
        end=(len(centres)-1)*sides
        faces.extend(((0,i+1,i),(end,end+i,end+i+1)))
    return points,faces,colour


def _mix(a,b,t):return tuple(x+(y-x)*t for x,y in zip(a,b))


def _leaf(base,angle,lift,length,width,colour):
    dx,dz=math.sin(angle),math.cos(angle)
    x,y,z=base
    mid=(x+dx*length*.48,y+lift*length*.48,z+dz*length*.48)
    points=[base,(mid[0]+dz*width,mid[1],mid[2]-dx*width),
            (x+dx*length,y+lift*length-.06,z+dz*length),
            (mid[0]-dz*width,mid[1]-width*.3,mid[2]+dx*width)]
    return points,[(0,1,2),(0,2,3)],colour


def forest_tree(position,seed,height=6.5,radius=.35,density=.5):
    rng=random.Random(seed)
    bark=(rng.randint(89,114),rng.randint(65,83),rng.randint(40,56))
    turn=rng.uniform(0,math.tau);lean=rng.uniform(.12,.5)
    centres=[(math.sin(turn+t)*lean*t,height*t,math.cos(turn+t)*lean*t)
             for t in (0,.2,.4,.6,.8,1)]
    trunk=_merge([_tube(centres,[radius*v for v in (1,.87,.68,.46,.23,.04)],bark,7)],bark)
    wood,lit,shade=[],[],[]
    spread=rng.uniform(.29,.44)*height
    lift=rng.uniform(.15,.32)*height
    crown_base=rng.uniform(.30,.49);crown_taper=rng.uniform(-.1,.45)
    limbs=rng.randint(6,8)
    for i in range(limbs):
        angle=turn+i*2.399963+rng.uniform(-.4,.4)
        t=min(.92,crown_base+(.9-crown_base)*i/(limbs-1)+rng.uniform(-.025,.025))
        ring=min(4,int(t*5));root=_mix(centres[ring],centres[ring+1],t*5-ring)
        reach=spread*rng.uniform(.7,1.)*(1-crown_taper*(i/(limbs-1)))
        end=(root[0]+math.sin(angle)*reach,root[1]+lift*rng.uniform(.65,1.15),root[2]+math.cos(angle)*reach)
        middle=_mix(root,end,.5);middle=(middle[0],middle[1]-.18,middle[2])
        width=radius*(1-t)*.65
        wood.append(_tube([root,middle,end],[width,width*.57,width*.13],bark,3))
        for sign in (-1,1):
            fork_angle=angle+sign*rng.uniform(.45,.9)
            start=_mix(middle,end,rng.uniform(.35,.65))
            tip=(end[0]+math.sin(fork_angle)*reach*.32,end[1]+rng.uniform(.25,.7),end[2]+math.cos(fork_angle)*reach*.32)
            wood.append(_tube([start,_mix(start,tip,.5),tip],[width*.42,width*.23,width*.05],bark,3))
            for j in range(3):
                base=_mix(start,tip,.4+j*.3)
                heading=fork_angle+(-1 if j%2 else 1)*rng.uniform(.55,1.25)
                shoot=(base[0]+math.sin(heading)*rng.uniform(.45,.7),base[1]+rng.uniform(.15,.45),base[2]+math.cos(heading)*rng.uniform(.45,.7))
                wood.append(_tube([base,shoot],[width*.13,width*.015],bark,3))
                # Leaves grow on shoots. The giant green potato has been evicted.
                for k in range(3):
                    petiole=_mix(base,shoot,.25+k*.35)
                    for side in (-1,1):
                        direction=heading+side*rng.uniform(.65,1.35)
                        colour=(32+int(rng.random()*27),99+int(rng.random()*44)+int(density*8),34+int(rng.random()*30))
                        blade=_leaf(petiole,direction,rng.uniform(-.15,.5),rng.uniform(.48,.8),rng.uniform(.13,.23),colour)
                        (lit if (i+j+k)%2 else shade).append(blade)
    branches=_merge(wood,bark)
    foliage=[_merge(lit,(46,126,49)),_merge(shade,(36,108,43))]
    for mesh in (trunk,branches,*foliage):mesh.position=position
    return [trunk,branches,*foliage]
