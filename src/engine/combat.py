import math

from engine.run_config import PERCEPTION


def turn_towards(yaw,target,rate,dt):
    delta = (target-yaw+math.pi)%math.tau-math.pi
    return yaw+max(-rate*dt,min(rate*dt,delta))


def attack_hits(actor,camera,world,reach,half_arc=PERCEPTION['attack_half_arc'],vertical=2.1):
    dx,dz = camera.x-actor.x,camera.z-actor.z
    distance = math.hypot(dx,dz)
    body_y = camera.y-camera.eye_height+.8
    facing = (dx*math.sin(actor.yaw)+dz*math.cos(actor.yaw))/max(.001,distance)
    return (distance<=reach and facing>=math.cos(math.radians(half_arc))
            and abs(body_y-actor.y-.6)<=vertical
            and world.line_clear(actor.x,actor.z,camera.x,camera.z,.1))
