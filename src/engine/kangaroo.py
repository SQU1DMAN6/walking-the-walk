"""Kangaroo wildlife module."""

import math
import random

import pygame

from engine.entity import Entity


class Kangaroo(Entity):
    """A kangaroo that startles and flees when the player approaches."""

    def __init__(self, x, y, z, seed=0):
        super().__init__(x, y, z, speed=4.5, detection_range=10.0)
        self.rng = random.Random(seed)
        self.state = "graze"
        self.timer = self.rng.uniform(2.0, 5.0)
        self.startle_range = 6.0
        self.flee_range = 4.0
        self.aggressive = self.rng.random() < 0.15
        self.kick_range = 2.0
        self.kick_damage = 18.0
        self.attack_timer = 0.0
        self._damage = 0.0
        self.sprite_w = 1.4
        self.sprite_h = 4.0

    def update(self, dt, px, pz):
        d = self.distance_to(px, pz)
        if self.state == "fight":
            self.attack_timer -= dt
            if d > self.kick_range:
                a = math.atan2(pz - self.z, px - self.x)
                self.x += math.cos(a) * self.speed * 0.8 * dt
                self.z += math.sin(a) * self.speed * 0.8 * dt
            if d < self.kick_range and self.attack_timer <= 0.0:
                self._damage = self.kick_damage
                self.attack_timer = 0.8
            if d > 20:
                self.state = "graze"
            return
        if d < self.startle_range:
            if self.aggressive and d < self.flee_range:
                self.state = "fight"
                self.attack_timer = 0.3
            else:
                self.state = "flee"
        self.timer -= dt
        if self.timer <= 0:
            self.timer = self.rng.uniform(2.0, 5.0)
        if self.state == "flee":
            a = math.atan2(pz - self.z, px - self.x) + math.pi
            self.x += math.cos(a) * self.speed * 1.8 * dt
            self.z += math.sin(a) * self.speed * 1.8 * dt
        if abs(self.x) > 50:
            self.x = 50 * (1 if self.x > 0 else -1)
        if abs(self.z) > 50:
            self.z = 50 * (1 if self.z > 0 else -1)

    def take_hit(self):
        d = self._damage
        self._damage = 0.0
        return d

    def billboard(self, cx, cz):
        return (None, self.x, self.y, self.z, self.sprite_w, self.sprite_h)
