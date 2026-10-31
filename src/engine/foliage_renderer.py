import ctypes
import math
import weakref

import numpy as np
from OpenGL import GL as gl
from OpenGL.GL import shaders


def leaf_spray(size=128):
    import pygame

    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    rng = np.random.default_rng(42)
    pygame.draw.line(
        surface, (180, 100, 50, 255), (size * 0.5, 0), (size * 0.5, size * 0.92), 3
    )
    for j in range(7):
        for sign in (-1, 1):
            base = np.array((size * 0.5, size * (0.05 + j * 0.11)))
            tip = base + np.array(
                (sign * size * rng.uniform(0.30, 0.46), size * rng.uniform(0.18, 0.27))
            )
            pygame.draw.line(surface, (180, 100, 50, 255), base, tip, 1)
            axis = tip - base
            side = np.array((-axis[1], axis[0])) * 0.26
            mid = base + axis * 0.48
            shade = int(rng.integers(185, 255))
            pygame.draw.polygon(
                surface, (shade, shade, shade, 255), [base, mid + side, tip, mid - side]
            )
    return pygame.image.tobytes(surface, "RGBA"), size


def _instance_vao(vbo, offset=0, kind="foliage"):
    vao = gl.glGenVertexArrays(1)
    gl.glBindVertexArray(vao)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
    stride = 84 if kind != "foliage" else 48
    for location in range(7 if kind != "foliage" else 4):
        gl.glEnableVertexAttribArray(location)
        gl.glVertexAttribPointer(
            location,
            3,
            gl.GL_FLOAT,
            False,
            stride,
            ctypes.c_void_p(offset * stride + location * 12),
        )
        gl.glVertexAttribDivisor(location, 1)
    gl.glBindVertexArray(0)
    return vao


def static_geometry(data, kind):
    light_direction = np.array((-0.4, 0.8, -0.4), dtype=np.float32)
    light_direction /= np.linalg.norm(light_direction)
    if kind == "limbs":
        base, axis, side, up, end_side, end_up, tint = np.split(data, 7, axis=1)
        cosine = np.array((1.0, -0.5, -0.5, 1.0, -0.5, -0.5))
        sine = np.array((0.0, 0.8660254, -0.8660254, 0.0, 0.8660254, -0.8660254))
        along = np.array((0, 0, 0, 1, 1, 1))
        sides = np.where(
            along[None, :, None] == 0, side[:, None, :], end_side[:, None, :]
        )
        ups = np.where(along[None, :, None] == 0, up[:, None, :], end_up[:, None, :])
        radial = sides * cosine[None, :, None] + ups * sine[None, :, None]
        points = base[:, None, :] + axis[:, None, :] * along[None, :, None] + radial
        normals = radial / np.maximum(
            np.linalg.norm(radial, axis=2, keepdims=True), 1e-9
        )
        uv = np.zeros((*points.shape[:2], 3))
        pattern = np.array(
            (0, 1, 3, 1, 4, 3, 1, 2, 4, 2, 5, 4, 2, 0, 5, 0, 3, 5, 0, 2, 1, 3, 4, 5)
        )
    else:
        base, axis, side, tint = np.split(data, 4, axis=1)
        along, across = np.array((0, 0, 1, 1)), np.array((-1, 1, 1, -1))
        points = (
            base[:, None, :]
            + axis[:, None, :] * along[None, :, None]
            + side[:, None, :] * across[None, :, None]
        )
        normal = np.cross(side, axis)
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-9)
        normals = np.broadcast_to(normal[:, None, :], points.shape)
        uv = np.broadcast_to(
            np.column_stack(((across + 1) / 2, along, np.zeros(4))), points.shape
        )
        pattern = np.array((0, 1, 2, 0, 2, 3))
    light = 0.5 + 0.5 * np.abs(normals @ light_direction)
    colours = tint[:, None, :] / 255 * light[:, :, None]
    vertices = (
        np.concatenate((points, colours, uv), axis=2).reshape(-1, 9).astype(np.float32)
    )
    indices = (
        (np.arange(len(data))[:, None] * points.shape[1] + pattern)
        .astype(np.uint32)
        .ravel()
    )
    return vertices, indices


def upload_leaf_tiles(arrays, kind="foliage", instanced=False):
    from types import SimpleNamespace

    groups, offset = [], 0
    for data in arrays:
        ends = data[:, :3] + data[:, 3:6]
        extent = data[:, 6:7] if kind == "limbs" else np.abs(data[:, 6:9])
        low = (np.minimum(data[:, :3], ends) - extent).min(axis=0)
        high = (np.maximum(data[:, :3], ends) + extent).max(axis=0)
        groups.append(
            SimpleNamespace(
                kind=kind,
                vertex_count=len(data),
                instanced=instanced,
                vaos=[None],
                instance_range=(offset, len(data)),
                center=tuple(float(v) for v in (low + high) / 2),
                radius=float(np.linalg.norm(high - low) / 2 + 0.1),
            )
        )
        offset += len(data)
    combined = np.concatenate(arrays)
    if kind == "limbs":
        axis = combined[:, 3:6]
        direction = axis / np.linalg.norm(axis, axis=1)[:, None]
        tangent = np.column_stack((axis[:, 2], np.zeros(len(axis)), -axis[:, 0]))
        length = np.linalg.norm(tangent, axis=1)
        tangent[length < 1e-6] = (1, 0, 0)
        tangent /= np.maximum(np.linalg.norm(tangent, axis=1), 1e-6)[:, None]
        up = np.cross(direction, tangent)
        combined = np.column_stack(
            (
                combined[:, :6],
                tangent * combined[:, 6:7],
                up * combined[:, 6:7],
                tangent * combined[:, 7:8],
                up * combined[:, 7:8],
                combined[:, 9:12],
            )
        ).astype(np.float32)
    if not instanced:
        vertices, indices = static_geometry(combined, kind)
        vbo, elements = gl.glGenBuffers(2)
        vao = gl.glGenVertexArrays(1)
        try:
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW
            )
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, elements)
            gl.glBufferData(
                gl.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, gl.GL_STATIC_DRAW
            )
            for location in range(3):
                gl.glEnableVertexAttribArray(location)
                gl.glVertexAttribPointer(
                    location, 3, gl.GL_FLOAT, False, 36, ctypes.c_void_p(location * 12)
                )
        except Exception:
            gl.glDeleteBuffers(2, [vbo, elements])
            gl.glDeleteVertexArrays(1, [vao])
            raise
        count = 24 if kind == "limbs" else 6
        for group in groups:
            group.element_vbo = elements
            group.index_range = (
                group.instance_range[0] * count,
                group.instance_range[1] * count,
            )
    else:
        vbo = gl.glGenBuffers(1)
        try:
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER, combined.nbytes, combined, gl.GL_STATIC_DRAW
            )
            vao = _instance_vao(vbo, kind=kind)
        except Exception:
            gl.glDeleteBuffers(1, [vbo])
            raise
    for group in groups:
        group.vbo, group.common_vao = vbo, vao
    return groups


def upload_leaf_array(data, kind="foliage"):
    return upload_leaf_tiles([data], kind, instanced=True)


def release_leaf_batch(groups):
    if not isinstance(groups, list):
        groups = [groups]
    vaos = {
        v for group in groups for v in (*group.vaos, group.common_vao) if v is not None
    }
    buffers = {group.vbo for group in groups}
    buffers.update(
        group.element_vbo for group in groups if hasattr(group, "element_vbo")
    )
    if vaos:
        gl.glDeleteVertexArrays(len(vaos), list(vaos))
    if buffers:
        gl.glDeleteBuffers(len(buffers), list(buffers))


class FoliageRenderer:
    def __init__(self, parent):
        self.parent = parent
        self.cache = {}
        self.frame = 0
        version = gl.glGetString(gl.GL_VERSION).decode().split()[0].split(".")
        self.indirect_supported = tuple(map(int, version[:2])) >= (4, 3) and bool(
            gl.glMultiDrawElementsIndirect
        )
        self.commands = gl.glGenBuffers(1)
        self.indices = {}
        for kind, indices in (
            ("foliage", (0, 1, 2, 0, 2, 3)),
            (
                "limbs",
                (
                    0,
                    1,
                    3,
                    1,
                    4,
                    3,
                    1,
                    2,
                    4,
                    2,
                    5,
                    4,
                    2,
                    0,
                    5,
                    0,
                    3,
                    5,
                    0,
                    2,
                    1,
                    3,
                    4,
                    5,
                ),
            ),
        ):
            data = np.asarray(indices, dtype=np.uint32)
            buffer = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, buffer)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_STATIC_DRAW)
            self.indices[kind] = buffer, len(indices)
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
        for direction in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, direction, gl.GL_LINEAR)
        for direction in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, direction, gl.GL_CLAMP_TO_EDGE)
        vertex = """#version 330 core
        layout(location=0) in vec3 base;
        layout(location=1) in vec3 axis;
        layout(location=2) in vec3 side;
        layout(location=3) in vec3 colour;
        layout(location=4) in vec3 end_side;
        layout(location=5) in vec3 end_up;
        layout(location=6) in vec3 bark;
        uniform mat4 view_projection;
        uniform mat4 model;
        uniform bool is_branch;
        uniform bool is_static;
        out vec3 leaf_colour;
        out float depth;
        out vec2 uv;
        void main(){
            vec3 p,n,tint=colour;
            uv=vec2(0);
            if(is_static){
                gl_Position=view_projection*model*vec4(base,1);
                depth=gl_Position.w;leaf_colour=axis;uv=side.xy;return;
            }
            if(is_branch){
                int i=gl_VertexID;
                float cosine[3]=float[](1.0,-0.5,-0.5);
                float sine[3]=float[](0.0,0.8660254,-0.8660254);
                n=normalize(side*cosine[i%3]+colour*sine[i%3]);
                p=base+axis*float(i/3)+(i<3?side:end_side)*cosine[i%3]+(i<3?colour:end_up)*sine[i%3];
                tint=bark;
            }else{
                int i=gl_VertexID;
                float along=i<2?0.0:1.0;
                float across=i==0||i==3?-1.0:1.0;
                uv=vec2(across*.5+.5,along);
                p=base+axis*along+side*across;
                n=normalize(cross(side,axis));
            }
            gl_Position=view_projection*model*vec4(p,1.0);
            depth=gl_Position.w;
            n=normalize(mat3(model)*n);
            float light=0.5+0.5*abs(dot(n,normalize(vec3(-0.4,0.8,-0.4))));
            leaf_colour=tint/255.0*light;
        }"""
        fragment = """#version 330 core
        in vec3 leaf_colour;
        in float depth;
        in vec2 uv;
        uniform bool is_branch;
        uniform sampler2D leaf_spray;
        uniform vec3 fog_colour;
        uniform vec2 fog_range;
        uniform float opacity;
        out vec4 result;
        void main(){
            vec4 mask=is_branch?vec4(1):texture(leaf_spray,uv);
            if(mask.a<.5)discard;
            float fog=clamp((depth-fog_range.x)/(fog_range.y-fog_range.x),0.0,1.0);
            vec3 tint=mask.r>mask.g+.1?vec3(.36,.24,.12):leaf_colour*mask.rgb;
            result=vec4(mix(tint,fog_colour,fog),opacity);
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
                "fog_colour",
                "fog_range",
                "opacity",
                "is_branch",
                "is_static",
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
            if model is None:
                buckets.setdefault(group.common_vao, []).append(group)
            else:
                moving.append((group, model))
        passes = [(vao, entries, None) for vao, entries in buckets.items()]
        passes.extend((group.common_vao, [group], model) for group, model in moving)
        passes.sort(key=lambda item: item[1][0].kind != "limbs")
        if self.indirect_supported:
            commands = np.asarray(
                [
                    (
                        24 if group.kind == "limbs" else 6,
                        group.instance_range[1],
                        0,
                        0,
                        group.instance_range[0],
                    )
                    if group.instanced
                    else (group.index_range[1], 1, group.index_range[0], 0, 0)
                    for _, entries, _ in passes
                    for group in entries
                ],
                dtype=np.uint32,
            )
            gl.glBindBuffer(gl.GL_DRAW_INDIRECT_BUFFER, self.commands)
            gl.glBufferData(
                gl.GL_DRAW_INDIRECT_BUFFER, commands.nbytes, commands, gl.GL_STREAM_DRAW
            )
        gl.glUniformMatrix4fv(loc["model"], 1, True, identity)
        offset = 0
        previous_model = last_branch = last_static = None
        gl.glFrontFace(gl.GL_CW)
        gl.glCullFace(gl.GL_BACK)
        for vao, entries, model in passes:
            branch = entries[0].kind == "limbs"
            static = not entries[0].instanced
            if branch != last_branch:
                gl.glUniform1i(loc["is_branch"], int(branch))
                gl.glEnable(gl.GL_CULL_FACE) if branch else gl.glDisable(
                    gl.GL_CULL_FACE
                )
                last_branch = branch
            if static != last_static:
                gl.glUniform1i(loc["is_static"], int(static))
                last_static = static
            if model is not None:
                gl.glUniformMatrix4fv(loc["model"], 1, True, model)
            elif previous_model is not None:
                gl.glUniformMatrix4fv(loc["model"], 1, True, identity)
            previous_model = model
            self._submit(vao, entries, offset)
            offset += len(entries) * 20
        if self.indirect_supported:
            gl.glBindBuffer(gl.GL_DRAW_INDIRECT_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
        gl.glEnable(gl.GL_BLEND)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glFrontFace(gl.GL_CCW)

    def _submit(self, vao, entries, offset=0):
        kind = entries[0].kind
        index_buffer, count = self.indices[kind]
        instanced = entries[0].instanced
        if not instanced:
            index_buffer = entries[0].element_vbo
        if self.indirect_supported:
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, index_buffer)
            gl.glMultiDrawElementsIndirect(
                gl.GL_TRIANGLES,
                gl.GL_UNSIGNED_INT,
                ctypes.c_void_p(offset),
                len(entries),
                0,
            )
        else:
            for group in entries:
                if instanced:
                    first, instances = group.instance_range
                    if group.vaos[0] is None:
                        group.vaos[0] = _instance_vao(group.vbo, first, kind)
                    gl.glBindVertexArray(group.vaos[0])
                    gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, index_buffer)
                    gl.glDrawElementsInstanced(
                        gl.GL_TRIANGLES,
                        count,
                        gl.GL_UNSIGNED_INT,
                        ctypes.c_void_p(0),
                        instances,
                    )
                else:
                    gl.glBindVertexArray(group.common_vao)
                    gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, group.element_vbo)
                    first, length = group.index_range
                    gl.glDrawElements(
                        gl.GL_TRIANGLES,
                        length,
                        gl.GL_UNSIGNED_INT,
                        ctypes.c_void_p(first * 4),
                    )

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
            ref, batches, _ = self.cache[key]
            self.cache[key] = (ref, batches, self.frame)
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
            groups.extend((group, model) for group in batches)
        self.draw(camera, groups, alpha)

    def close(self):
        for _, group, _ in self.cache.values():
            release_leaf_batch(group)
        self.cache.clear()
        gl.glDeleteTextures([self.spray])
        gl.glDeleteBuffers(
            len(self.indices), [buffer for buffer, _ in self.indices.values()]
        )
        gl.glDeleteBuffers(1, [self.commands])
        gl.glDeleteProgram(self.program)
