import ctypes
import math
import weakref

import numpy as np
from OpenGL import GL as gl
from OpenGL.GL import shaders


def detail_level(distance):
    return 0 if distance < 16 else 1 if distance < 32 else 2


def leaf_spray(size=128):
    import pygame

    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    rng = np.random.default_rng(42)
    for j in range(6):
        for sign in (-1, 1):
            base = np.array((size * 0.5, size * (0.08 + j * 0.135)))
            tip = base + np.array(
                (sign * size * rng.uniform(0.24, 0.46), size * rng.uniform(0.15, 0.27))
            )
            axis = tip - base
            side = np.array((-axis[1], axis[0])) * 0.21
            mid = base + axis * 0.48
            shade = int(rng.integers(185, 255))
            pygame.draw.polygon(
                surface, (shade, shade, shade, 255), [base, mid + side, tip, mid - side]
            )
    return pygame.image.tobytes(surface, "RGBA"), size


def _instance_vao(vbo, offset=0):
    vao = gl.glGenVertexArrays(1)
    gl.glBindVertexArray(vao)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
    for location in range(4):
        gl.glEnableVertexAttribArray(location)
        gl.glVertexAttribPointer(
            location,
            3,
            gl.GL_FLOAT,
            False,
            48,
            ctypes.c_void_p(offset * 48 + location * 12),
        )
        gl.glVertexAttribDivisor(location, 1)
    gl.glBindVertexArray(0)
    return vao


def upload_leaf_tiles(arrays, kind="foliage"):
    from types import SimpleNamespace

    parts = []
    groups = []
    offset = 0
    for data in arrays:
        ranges = []
        bounds = []
        for level, (step, scale) in enumerate(((1, 1.0), (8, 2.2), (24, 3.6))):
            part = (
                data[data[:, 8] <= (2, 1, 0)[level]].copy()
                if kind == "limbs"
                else data[::step].copy()
            )
            if kind == "limbs" and level == 2 and len(part) % 2 == 0:
                first, second = part[::2], part[1::2]
                part = first.copy()
                part[:, 3:6] += second[:, 3:6]
                part[:, 7] = second[:, 7]
            if kind == "foliage":
                part[:, 3:9] *= scale
                if level:
                    part[:, 9] *= -1
            ranges.append((offset, len(part)))
            parts.append(part)
            offset += len(part)
            ends = part[:, :3] + part[:, 3:6]
            extent = part[:, 6:7] if kind == "limbs" else np.abs(part[:, 6:9])
            bounds.extend(
                (
                    (np.minimum(part[:, :3], ends) - extent).min(axis=0),
                    (np.maximum(part[:, :3], ends) + extent).max(axis=0),
                )
            )
        low, high = np.min(bounds, axis=0), np.max(bounds, axis=0)
        groups.append(
            SimpleNamespace(
                kind=kind,
                vertex_count=len(data),
                vaos=[None] * 3,
                lod_ranges=ranges,
                center=tuple(float(v) for v in (low + high) / 2),
                radius=float(np.linalg.norm(high - low) / 2),
            )
        )
    combined = np.concatenate(parts)
    vbo = gl.glGenBuffers(1)
    try:
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER, combined.nbytes, combined, gl.GL_STATIC_DRAW
        )
        vao = _instance_vao(vbo)
    except Exception:
        gl.glDeleteBuffers(1, [vbo])
        raise
    for group in groups:
        group.vbo = vbo
        group.common_vao = vao
    return groups


def upload_leaf_array(data, kind="foliage"):
    return upload_leaf_tiles([data], kind)[0]


def release_leaf_batch(group):
    vaos = set(v for v in (*group.vaos, group.common_vao) if v is not None)
    if vaos:
        gl.glDeleteVertexArrays(len(vaos), list(vaos))
    gl.glDeleteBuffers(1, [group.vbo])


class FoliageRenderer:
    def __init__(self, parent):
        self.parent = parent
        self.cache = {}
        self.frame = 0
        version = gl.glGetString(gl.GL_VERSION).decode().split()[0].split(".")
        self.indirect_supported = tuple(map(int, version[:2])) >= (4, 3) and bool(
            gl.glMultiDrawArraysIndirect
        )
        self.commands = gl.glGenBuffers(1)
        pixels, size = leaf_spray()
        self.spray = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.spray)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGBA8,
            size,
            size,
            0,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            pixels,
        )
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        vertex = """#version 330 core
        layout(location=0) in vec3 base;
        layout(location=1) in vec3 axis;
        layout(location=2) in vec3 side;
        layout(location=3) in vec3 colour;
        uniform mat4 view_projection;
        uniform mat4 model;
        uniform float blade_scale;
        uniform bool is_branch;
        out vec3 leaf_colour;
        out float depth;
        out vec2 uv;
        flat out int spray;
        void main(){
            vec3 p,n;
            spray=0;uv=vec2(0);
            if(is_branch){
                int indices[24]=int[](0,1,3,1,4,3,1,2,4,2,5,4,2,0,5,0,3,5,0,2,1,3,4,5);
                int i=indices[gl_VertexID];
                vec3 direction=normalize(axis);
                vec3 tangent=length(axis.xz)>0.00001?normalize(vec3(axis.z,0,-axis.x)):vec3(1,0,0);
                vec3 up=cross(direction,tangent);
                float cosine[3]=float[](1.0,-0.5,-0.5);
                float sine[3]=float[](0.0,0.8660254,-0.8660254);
                n=tangent*cosine[i%3]+up*sine[i%3];
                p=base+axis*float(i/3)+n*(i<3?side.x:side.y);
            }else{
                int indices[6]=int[](0,1,2,0,2,3);
                int i=indices[gl_VertexID];
                spray=colour.r<0.0?1:0;
                float along=spray==1?(i<2?0.0:1.0):(i==0?0.0:(i==2?1.0:0.48));
                float across=spray==1?(i==0||i==3?-1.0:1.0):(i==1?1.0:(i==3?-1.0:0.0));
                uv=vec2(across*.5+.5,along);
                p=base+(axis*along+side*across)*blade_scale;
                if(i==2)p.y-=0.06*blade_scale;
                if(i==3)p.y-=length(side)*0.3*blade_scale;
                n=normalize(cross(side,axis));
            }
            gl_Position=view_projection*model*vec4(p,1.0);
            depth=gl_Position.w;
            n=normalize(mat3(model)*n);
            float light=0.5+0.5*abs(dot(n,normalize(vec3(-0.4,0.8,-0.4))));
            leaf_colour=abs(colour)/255.0*light;
        }"""
        fragment = """#version 330 core
        in vec3 leaf_colour;
        in float depth;
        in vec2 uv;
        flat in int spray;
        uniform sampler2D leaf_spray;
        uniform vec3 fog_colour;
        uniform vec2 fog_range;
        uniform float opacity;
        out vec4 result;
        void main(){
            vec4 mask=spray==1?texture(leaf_spray,uv):vec4(1);
            if(mask.a<0.5)discard;
            float fog=clamp((depth-fog_range.x)/(fog_range.y-fog_range.x),0.0,1.0);
            result=vec4(mix(leaf_colour*mask.rgb,fog_colour,fog),opacity);
        }"""
        self.program = shaders.compileProgram(
            shaders.compileShader(vertex, gl.GL_VERTEX_SHADER),
            shaders.compileShader(fragment, gl.GL_FRAGMENT_SHADER),
        )
        self.locations = {
            name: gl.glGetUniformLocation(self.program, name)
            for name in (
                "view_projection",
                "model",
                "blade_scale",
                "fog_colour",
                "fog_range",
                "opacity",
                "is_branch",
                "leaf_spray",
            )
        }

    def begin_frame(self):
        self.frame += 1
        for key, (ref, batch, last) in tuple(self.cache.items()):
            if ref() is None or self.frame - last > 2:
                release_leaf_batch(batch)
                del self.cache[key]

    def camera_matrix(self, camera):
        c, s = math.cos(camera.yaw), math.sin(camera.yaw)
        cp, sp = math.cos(camera.pitch), math.sin(camera.pitch)
        view = np.array(
            (
                (c, 0, -s, 0),
                (s * sp, cp, c * sp, 0),
                (s * cp, -sp, c * cp, 0),
                (0, 0, 0, 1),
            ),
            dtype=np.float32,
        )
        view[:3, 3] = -view[:3, :3] @ np.asarray(
            camera.eye_position(), dtype=np.float32
        )
        p = self.parent
        n, f = p.near, p.far
        projection = np.array(
            (
                (2 * p.focal_length / p.width, 0, 0, 0),
                (0, 2 * p.focal_length / p.height, 0, 0),
                (0, 0, (f + n) / (f - n), -2 * f * n / (f - n)),
                (0, 0, 1, 0),
            ),
            dtype=np.float32,
        )
        return projection @ view

    def draw(self, camera, groups, alpha=None):
        if not groups:
            return
        gl.glUseProgram(self.program)
        loc = self.locations
        p = self.parent
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.spray)
        gl.glUniform1i(loc["leaf_spray"], 0)
        gl.glUniformMatrix4fv(
            loc["view_projection"], 1, True, self.camera_matrix(camera)
        )
        gl.glUniform3f(loc["fog_colour"], *p.fog_color)
        gl.glUniform2f(loc["fog_range"], p.fog_near, p.fog_far)
        gl.glUniform1f(loc["opacity"], 1.0 if alpha is None else alpha)
        gl.glDisable(gl.GL_BLEND) if alpha is None or alpha >= 1 else gl.glEnable(
            gl.GL_BLEND
        )
        identity = np.eye(4, dtype=np.float32)
        buckets = {}
        moving = []
        gl.glUniform1f(loc["blade_scale"], 1.0)
        for group, model in groups:
            centre = (
                group.center
                if model is None
                else tuple(
                    float(v)
                    for v in (model @ np.array((*group.center, 1), dtype=np.float32))[
                        :3
                    ]
                )
            )
            if not p.visible(camera, *centre, group.radius):
                continue
            lod = detail_level(
                math.hypot(centre[0] - camera.x, centre[2] - camera.z)
                / self.parent.resolution_scale
            )
            if model is None:
                buckets.setdefault(group.common_vao, []).append((group, lod))
            else:
                moving.append((group, lod, model))
        gl.glUniformMatrix4fv(loc["model"], 1, True, identity)
        for vao, entries in buckets.items():
            self._submit(vao, entries)
        for group, lod, model in moving:
            gl.glUniformMatrix4fv(loc["model"], 1, True, model)
            self._submit(group.common_vao, [(group, lod)])
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
        gl.glEnable(gl.GL_BLEND)

    def _submit(self, vao, entries):
        if self.indirect_supported:
            vertices = 24 if entries[0][0].kind == "limbs" else 6
            gl.glUniform1i(self.locations["is_branch"], int(vertices == 24))
            commands = np.asarray(
                [
                    (vertices, group.lod_ranges[lod][1], 0, group.lod_ranges[lod][0])
                    for group, lod in entries
                ],
                dtype=np.uint32,
            )
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_DRAW_INDIRECT_BUFFER, self.commands)
            gl.glBufferData(
                gl.GL_DRAW_INDIRECT_BUFFER, commands.nbytes, commands, gl.GL_STREAM_DRAW
            )
            gl.glMultiDrawArraysIndirect(
                gl.GL_TRIANGLES, ctypes.c_void_p(0), len(commands), 0
            )
            gl.glBindBuffer(gl.GL_DRAW_INDIRECT_BUFFER, 0)
        else:
            for group, lod in entries:
                first, count = group.lod_ranges[lod]
                if group.vaos[lod] is None:
                    group.vaos[lod] = _instance_vao(group.vbo, first)
                vertices = 24 if group.kind == "limbs" else 6
                gl.glUniform1i(self.locations["is_branch"], int(vertices == 24))
                gl.glBindVertexArray(group.vaos[lod])
                gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)

    def draw_models(self, camera, instances, alpha=None):
        groups = []
        for mesh, x, y, z, yaw in instances:
            source = getattr(mesh, "source", mesh)
            key = id(source)
            if key not in self.cache:
                kind = "foliage" if hasattr(source, "leaf_instances") else "limbs"
                data = (
                    source.leaf_instances
                    if kind == "foliage"
                    else source.branch_instances
                ).copy()
                data[:, :3] += source.position
                self.cache[key] = (
                    weakref.ref(source),
                    upload_leaf_array(data, kind),
                    self.frame,
                )
            ref, group, _ = self.cache[key]
            self.cache[key] = (ref, group, self.frame)
            model = np.eye(4, dtype=np.float32)
            if source is not mesh:
                for pivot, pitch, turn in mesh.rotations:
                    cp, sp, c, s = (
                        math.cos(pitch),
                        math.sin(pitch),
                        math.cos(turn),
                        math.sin(turn),
                    )
                    rotation = np.array(
                        ((c, s * sp, s * cp), (0, cp, -sp), (-s, c * sp, c * cp)),
                        dtype=np.float32,
                    )
                    pivot = np.asarray(pivot, dtype=np.float32)
                    transform = np.eye(4, dtype=np.float32)
                    transform[:3, :3] = rotation
                    transform[:3, 3] = pivot - rotation @ pivot
                    model = transform @ model
                model[:3, 3] += mesh.translation
            model[:3, 3] -= mesh.position
            c, s = math.cos(yaw), math.sin(yaw)
            rotation = np.array(
                ((c, 0, s, 0), (0, 1, 0, 0), (-s, 0, c, 0), (0, 0, 0, 1)),
                dtype=np.float32,
            )
            model = rotation @ model
            model[:3, 3] += (x, y, z)
            groups.append((group, model))
        self.draw(camera, groups, alpha)

    def close(self):
        for _, group, _ in self.cache.values():
            release_leaf_batch(group)
        self.cache.clear()
        gl.glDeleteTextures([self.spray])
        gl.glDeleteBuffers(1, [self.commands])
        gl.glDeleteProgram(self.program)
