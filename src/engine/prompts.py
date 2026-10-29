from dataclasses import dataclass
import math


@dataclass(frozen=True)
class WorldPrompt:
    target_id: int
    title: str
    text: str
    position: tuple
    ready: bool = True


def project(camera, position, width, height, focal=None):
    ex, ey, ez = camera.eye_position()
    dx, dy, dz = position[0]-ex, position[1]-ey, position[2]-ez
    cy, sy = math.cos(camera.yaw), math.sin(camera.yaw)
    cp, sp = math.cos(-camera.pitch), math.sin(-camera.pitch)
    rx, rz = dx*cy-dz*sy, dx*sy+dz*cy
    ry, depth = dy*cp-rz*sp, dy*sp+rz*cp
    if depth <= .1:
        return None
    focal = width*.7 if focal is None else focal
    x, y = width/2+rx*focal/depth, height/2-ry*focal/depth
    return (x, y) if 0 <= x <= width and 0 <= y <= height else None


def hovering_rect(camera,position,size,viewport,bottom):
    import pygame
    width,height=viewport
    point=project(camera,position,width,height)
    if point is None:return None
    w,h=size
    rect=pygame.Rect(0,0,w,h)
    rect.centerx=round(point[0])
    rect.bottom=min(round(point[1])-8,bottom-8)
    rect.clamp_ip(pygame.Rect(8,8,width-16,height-16))
    return rect,point
