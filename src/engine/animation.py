import math

from engine.items import DOG_WINDUP, DOG_RECOVERY, SPEAR_ANIMATION


def ease(value):
    value = max(0.0, min(1.0, value))
    return value*value*(3-2*value)


def envelope(time, start, peak, end):
    if time < peak:
        return ease((time-start)/(peak-start))
    return 1-ease((time-peak)/(end-peak))


def spear_motion(remaining):
    time = SPEAR_ANIMATION-max(0, min(SPEAR_ANIMATION, remaining))
    prepare = envelope(time, 0, .065, .15)
    strike = envelope(time, .065, .15, SPEAR_ANIMATION)
    return (-.08*strike, .045*strike-.025*prepare, .62*strike-.09*prepare,
            -.045*strike, .035*prepare-.055*strike)


def dog_motion(time):
    prepare = envelope(time, 0, DOG_WINDUP*.7, DOG_WINDUP)
    strike = envelope(time, DOG_WINDUP*.7, DOG_WINDUP, DOG_WINDUP+DOG_RECOVERY)
    jaw = envelope(time, .02, DOG_WINDUP*.7, DOG_WINDUP+.10)
    return prepare, strike, jaw


def rotate_point(point, pivot, pitch=0, yaw=0):
    x, y, z = (value-origin for value, origin in zip(point, pivot))
    cp, sp, cy, sy = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    y, z = y*cp-z*sp, y*sp+z*cp
    return x*cy+z*sy+pivot[0], y+pivot[1], -x*sy+z*cy+pivot[2]
