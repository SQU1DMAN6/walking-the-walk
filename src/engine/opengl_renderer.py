try:
    import OpenGL.GL as gl
    import OpenGL.GL.shaders as shaders

    HAS_OPENGL = True
    print("Say Hi to OpenGL!")
except Exception:
    HAS_OPENGL = False
    print("No OpenGL :(")

import ctypes
import math
import random

import numpy as np

from engine.foliage_renderer import FoliageRenderer, upload_leaf_tiles
from engine.scene_target import SceneTarget


def _generate_leaf_texture(size=64):

    rng = random.Random(42)
    pixels = bytearray(size * size * 4)

    leaf_colours = [
        (65, 120, 50),
        (80, 140, 55),
        (95, 130, 60),
        (110, 150, 65),
        (140, 160, 70),
        (55, 100, 45),
        (75, 110, 50),
    ]

    blobs = []
    for _ in range(20):
        cx = rng.uniform(0.0, 1.0)
        cy = rng.uniform(0.0, 1.0)
        rx = rng.uniform(0.08, 0.25)
        ry = rng.uniform(0.15, 0.40)
        angle = rng.uniform(0, math.pi * 2)
        ca, sa = math.cos(angle), math.sin(angle)
        colour = rng.choice(leaf_colours)
        crisp = rng.uniform(0.5, 1.5)
        tip_variation = rng.uniform(0.0, 0.3)
        blobs.append(
            (
                cx,
                cy,
                rx,
                ry,
                ca,
                sa,
                colour[0],
                colour[1],
                colour[2],
                crisp,
                tip_variation,
            )
        )

    for py in range(size):
        for px in range(size):
            u = px / size
            v = py / size
            max_coverage = 0.0
            best_r = best_g = best_b = 0

            for cx, cy, rx, ry, ca, sa, lr, lg, lb, crisp, tip_var in blobs:
                dx = u - cx
                dy = v - cy
                lu = dx * ca + dy * sa
                lv = -dx * sa + dy * ca
                dist = (lu / rx) ** 2 + (lv / ry) ** 2
                if dist < 1.0:
                    coverage = max(0.0, 1.0 - dist ** (0.5 / crisp))
                    if coverage > max_coverage:
                        max_coverage = coverage
                        tip_amount = max(0.0, lv / ry) * tip_var
                        best_r = int(min(255, lr + tip_amount * 60))
                        best_g = int(min(255, lg + tip_amount * 30))
                        best_b = int(min(255, lb - tip_amount * 20))

            idx = (py * size + px) * 4
            if max_coverage > 0.08:
                vein = 0.85 + 0.15 * math.sin(u * 15 + v * 12) * math.sin(
                    v * 20 - u * 8
                )
                spot = 0.9 + 0.1 * math.sin(u * 40 + v * 30) * math.cos(v * 25 - u * 35)
                pixels[idx] = int(
                    min(255, best_r * vein * spot * (0.6 + 0.4 * max_coverage))
                )
                pixels[idx + 1] = int(
                    min(255, best_g * vein * spot * (0.6 + 0.4 * max_coverage))
                )
                pixels[idx + 2] = int(
                    min(255, best_b * vein * spot * (0.6 + 0.4 * max_coverage))
                )
                alpha_noise = 0.85 + 0.15 * math.sin(u * 50 + v * 45) * math.cos(
                    v * 35 - u * 40
                )
                pixels[idx + 3] = int(min(255, max_coverage * 255 * alpha_noise))
            else:
                pixels[idx : idx + 4] = b"\x00\x00\x00\x00"

    tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexImage2D(
        gl.GL_TEXTURE_2D,
        0,
        gl.GL_RGBA,
        size,
        size,
        0,
        gl.GL_RGBA,
        gl.GL_UNSIGNED_BYTE,
        bytes(pixels),
    )
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex_id


class BatchGroup:
    __slots__ = (
        "colour",
        "use_texture",
        "vertex_data",
        "vertex_count",
        "vbo",
        "kind",
        "center",
        "radius",
        "vaos",
        "first",
    )

    def __init__(self, colour, use_texture, vertex_data, vertex_count, vbo):
        self.colour = colour
        self.use_texture = use_texture
        self.vertex_data = vertex_data
        self.vertex_count = vertex_count
        self.vbo = vbo
        self.kind, self.center, self.radius, self.vaos, self.first = (
            "mesh",
            (0, 0, 0),
            0,
            [],
            0,
        )


def _mesh_array(mesh):
    faces = np.asarray(mesh.faces, dtype=np.int32)
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    points = vertices[faces]
    normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
    data = np.empty((len(faces), 3, 11), dtype=np.float32)
    data[:, :, :3] = points + mesh.position
    data[:, :, 3:6] = normals[:, None, :]
    data[:, :, 6:8] = np.asarray(mesh.texcoords)[faces] if mesh.texcoords else 0
    data[:, :, 8:11] = (
        np.asarray(mesh.vertex_colours)[faces] if mesh.vertex_colours else mesh.colour
    )
    return data.reshape(-1, 11)


def pack_meshes(meshes, spatial=True):
    groups = {}
    for mesh in meshes:
        tile = (math.floor(mesh.position[0] / 8), math.floor(mesh.position[2] / 8))
        if hasattr(mesh, "leaf_instances") or hasattr(mesh, "branch_instances"):
            kind = "foliage" if hasattr(mesh, "leaf_instances") else "limbs"
            data = (
                mesh.leaf_instances if kind == "foliage" else mesh.branch_instances
            ).copy()
            data[:, :3] += mesh.position
            groups.setdefault((kind, *tile), []).append(data)
        elif mesh.faces:
            key = (
                ("mesh", mesh.texcoords is not None, *tile)
                if spatial
                else mesh.texcoords is not None
            )
            groups.setdefault(key, []).append(_mesh_array(mesh))
    return [(kind, np.concatenate(parts)) for kind, parts in groups.items()]


def release_batches(batches):
    vaos = set()
    vbos = set()
    for batch in batches:
        vaos.update(v for v in batch.vaos if v is not None)
        if batch.kind in ("foliage", "limbs"):
            vaos.add(batch.common_vao)
        vbos.add(batch.vbo)
        if hasattr(batch, "element_vbo"):
            vbos.add(batch.element_vbo)
    if vaos:
        gl.glDeleteVertexArrays(len(vaos), list(vaos))
    if vbos:
        gl.glDeleteBuffers(len(vbos), list(vbos))


def upload_batches(packed):
    batches = []
    try:
        for material in ("foliage", "limbs"):
            arrays = [
                data
                for kind, data in packed
                if isinstance(kind, tuple) and kind[0] == material
            ]
            if arrays:
                batches.extend(upload_leaf_tiles(arrays, material))
        entries = [
            (kind, data)
            for kind, data in packed
            if not (isinstance(kind, tuple) and kind[0] in ("foliage", "limbs"))
        ]
        if not entries:
            return batches
        combined = np.concatenate([data for _, data in entries])
        vbo = gl.glGenBuffers(1)
        batch = BatchGroup((255, 255, 255), False, None, 0, vbo)
        batches.append(batch)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER, combined.nbytes, combined, gl.GL_STATIC_DRAW
        )
        vao = gl.glGenVertexArrays(1)
        batch.vaos = [vao]
        gl.glBindVertexArray(vao)
        for location, size, offset in ((0, 3, 0), (1, 3, 12), (2, 2, 24), (3, 3, 32)):
            gl.glEnableVertexAttribArray(location)
            gl.glVertexAttribPointer(
                location, size, gl.GL_FLOAT, False, 44, ctypes.c_void_p(offset)
            )
        offset = 0
        for index, (kind, data) in enumerate(entries):
            group = (
                batch
                if index == 0
                else BatchGroup((255, 255, 255), False, None, 0, vbo)
            )
            if index:
                batches.append(group)
            group.vaos = [vao]
            group.first = offset
            group.vertex_count = len(data)
            offset += len(data)
            group.use_texture = (
                kind
                if isinstance(kind, bool)
                else kind[1]
                if kind[0] == "mesh"
                else False
            )
            if isinstance(kind, tuple):
                group.center = tuple(
                    float(v)
                    for v in (data[:, :3].min(axis=0) + data[:, :3].max(axis=0)) / 2
                )
                group.radius = float(
                    np.linalg.norm(data[:, :3].max(axis=0) - data[:, :3].min(axis=0))
                    / 2
                )
    except Exception:
        release_batches(batches)
        raise
    finally:
        gl.glBindVertexArray(0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
    return batches


def build_batches(meshes):
    return upload_batches(pack_meshes(meshes))


class OpenGLRenderer:
    def visible(self, camera, x, y, z, radius):
        key = (
            camera.x,
            camera.y,
            camera.z,
            camera.yaw,
            camera.pitch,
            camera.pivot_offset,
            camera.bob_offset,
            self.width,
            self.height,
            self.focal_length,
        )
        if key != getattr(self, "_clip_key", None):
            cy, sy = math.cos(camera.yaw), math.sin(camera.yaw)
            cp, sp = math.cos(camera.pitch), math.sin(camera.pitch)
            horizontal, vertical = (
                self.width / (2 * self.focal_length),
                self.height / (2 * self.focal_length),
            )
            self._clip_key = key
            self._clip_basis = (
                *camera.eye_position(),
                cy,
                sy,
                cp,
                sp,
                horizontal,
                vertical,
                math.hypot(1, horizontal),
                math.hypot(1, vertical),
            )
        ex, ey, ez, cy, sy, cp, sp, horizontal, vertical_limit, h_radius, v_radius = (
            self._clip_basis
        )
        dx, dy, dz = x - ex, y - ey, z - ez
        rx, forward = dx * cy - dz * sy, dx * sy + dz * cy
        vertical, depth = dy * cp + forward * sp, -dy * sp + forward * cp
        return (
            depth + radius > self.near
            and depth - radius < self.fog_far + 8
            and abs(rx) < depth * horizontal + radius * h_radius
            and abs(vertical) < depth * vertical_limit + radius * v_radius
        )

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.focal_length = 400.0
        self.near = 0.1
        self.far = 200.0

        self.vao = gl.glGenVertexArrays(1)
        self.dynamic_vbo = gl.glGenBuffers(1)
        self._dynamic_capacity = 0

        self._sprite_tex_cache = {}

        self._batch_data = []

        vertex_src = """
        #version 330 core
        layout (location = 0) in vec3 in_pos;
        layout (location = 1) in vec3 in_normal;
        layout (location = 2) in vec2 in_texcoord;
        layout (location = 3) in vec3 in_color;

        uniform vec3 u_cam_pos;
        uniform float u_cos_yaw;
        uniform float u_sin_yaw;
        uniform float u_cos_pitch;
        uniform float u_sin_pitch;
        uniform float u_focal;
        uniform float u_w;
        uniform float u_h;
        uniform float u_near;
        uniform float u_far;

        out vec3 v_normal;
        out vec2 v_texcoord;
        out vec3 v_color;
        out float v_viewz;

        void main() {
            vec3 rel = in_pos - u_cam_pos;
            float rx = rel.x * u_cos_yaw - rel.z * u_sin_yaw;
            float rz = rel.x * u_sin_yaw + rel.z * u_cos_yaw;
            float ry = rel.y * u_cos_pitch - rz * u_sin_pitch;
            float rz2 = rel.y * u_sin_pitch + rz * u_cos_pitch;

            float ndc_x = rx * u_focal / (u_w * 0.5);
            float ndc_y = ry * u_focal / (u_h * 0.5);


            float clip_z = (u_far + u_near) * rz2 / (u_far - u_near)
                         - 2.0 * u_far * u_near / (u_far - u_near);
            // Keep real depth so stuff behind you gets clipped.
            gl_Position = vec4(ndc_x, ndc_y, clip_z, rz2);
            v_normal = in_normal;
            v_texcoord = in_texcoord;
            v_color = in_color;
            v_viewz = rz2;
        }
        """

        fragment_src = """
        #version 330 core
        uniform vec3 u_color;
        uniform vec3 u_light_dir;
        uniform float u_ambient;
        uniform float u_diffuse;
        uniform bool u_use_texture;
        uniform sampler2D u_texture;


        uniform vec3 u_fog_color;
        uniform float u_fog_near;
        uniform float u_fog_far;
        uniform float u_alpha;

        in vec3 v_normal;
        in vec2 v_texcoord;
        in vec3 v_color;
        in float v_viewz;

        out vec4 f_col;

        void main() {

            vec3 base = v_color / 255.0;
            float diff = max(dot(normalize(v_normal), -u_light_dir), 0.0);
            float lit = u_ambient + u_diffuse * diff;

            if (u_use_texture) {
                vec4 texel = texture(u_texture, v_texcoord);
                if (texel.a < 0.05) discard;
                base = mix(base, texel.rgb, texel.a * 0.8);
            }

            vec3 final_col = base * lit;
            if (final_col.r < 0.01 && final_col.g < 0.01 && final_col.b < 0.01) discard;


            float fog = clamp((v_viewz - u_fog_near) / (u_fog_far - u_fog_near), 0.0, 1.0);
            final_col = mix(final_col, u_fog_color, fog);
            f_col = vec4(final_col, u_alpha);
        }
        """

        if not HAS_OPENGL:
            raise RuntimeError("PyOpenGL is not available")

        try:
            self.shader = shaders.compileProgram(
                shaders.compileShader(vertex_src, gl.GL_VERTEX_SHADER),
                shaders.compileShader(fragment_src, gl.GL_FRAGMENT_SHADER),
            )
        except Exception as e:
            print("Shader compile error:", e)
            raise

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        self.color_loc = gl.glGetUniformLocation(self.shader, "u_color")
        self.focal_loc = gl.glGetUniformLocation(self.shader, "u_focal")
        self.w_loc = gl.glGetUniformLocation(self.shader, "u_w")
        self.h_loc = gl.glGetUniformLocation(self.shader, "u_h")
        self.near_loc = gl.glGetUniformLocation(self.shader, "u_near")
        self.far_loc = gl.glGetUniformLocation(self.shader, "u_far")
        self.light_dir_loc = gl.glGetUniformLocation(self.shader, "u_light_dir")
        self.ambient_loc = gl.glGetUniformLocation(self.shader, "u_ambient")
        self.diffuse_loc = gl.glGetUniformLocation(self.shader, "u_diffuse")
        self.use_texture_loc = gl.glGetUniformLocation(self.shader, "u_use_texture")
        self.texture_loc = gl.glGetUniformLocation(self.shader, "u_texture")
        self.cam_pos_loc = gl.glGetUniformLocation(self.shader, "u_cam_pos")
        self.cos_yaw_loc = gl.glGetUniformLocation(self.shader, "u_cos_yaw")
        self.sin_yaw_loc = gl.glGetUniformLocation(self.shader, "u_sin_yaw")
        self.cos_pitch_loc = gl.glGetUniformLocation(self.shader, "u_cos_pitch")
        self.sin_pitch_loc = gl.glGetUniformLocation(self.shader, "u_sin_pitch")
        self.fog_color_loc = gl.glGetUniformLocation(self.shader, "u_fog_color")
        self.fog_near_loc = gl.glGetUniformLocation(self.shader, "u_fog_near")
        self.fog_far_loc = gl.glGetUniformLocation(self.shader, "u_fog_far")
        self.alpha_loc = gl.glGetUniformLocation(self.shader, "u_alpha")

        self.leaf_tex_id = _generate_leaf_texture(64)

        sun_dir = (0.4, -0.8, 0.4)
        sd_len = math.sqrt(sun_dir[0] ** 2 + sun_dir[1] ** 2 + sun_dir[2] ** 2)
        self.sun_world = (sun_dir[0] / sd_len, sun_dir[1] / sd_len, sun_dir[2] / sd_len)

        self.fog_color = (0.82, 0.66, 0.48)

        self.fog_near = 25.0
        self.fog_far = 70.0

        # Vertex layout: position(3), normal(3), uv(2), colour(3).
        self._stride = 11 * 4
        self.foliage = FoliageRenderer(self)
        self.scene_target = SceneTarget(self)

    def _set_camera_uniforms(self, camera):
        cy = math.cos(camera.yaw)
        sy = math.sin(camera.yaw)
        cp = math.cos(-camera.pitch)
        sp = math.sin(-camera.pitch)

        ex, ey, ez = camera.eye_position()
        gl.glUniform3f(self.cam_pos_loc, ex, ey, ez)
        gl.glUniform1f(self.cos_yaw_loc, cy)
        gl.glUniform1f(self.sin_yaw_loc, sy)
        gl.glUniform1f(self.cos_pitch_loc, cp)
        gl.glUniform1f(self.sin_pitch_loc, sp)

        gl.glUniform3f(self.light_dir_loc, *self.sun_world)

        gl.glUniform1f(self.focal_loc, self.focal_length)
        gl.glUniform1f(self.w_loc, float(self.width))
        gl.glUniform1f(self.h_loc, float(self.height))
        gl.glUniform1f(self.near_loc, self.near)
        gl.glUniform1f(self.far_loc, self.far)

        gl.glUniform1f(self.ambient_loc, 0.45)
        gl.glUniform1f(self.diffuse_loc, 0.55)

        gl.glUniform3f(
            self.fog_color_loc, self.fog_color[0], self.fog_color[1], self.fog_color[2]
        )
        gl.glUniform1f(self.fog_near_loc, self.fog_near)
        gl.glUniform1f(self.fog_far_loc, self.fog_far)
        gl.glUniform1f(self.alpha_loc, 1.0)

    def _define_attribs(self, vbo):

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(
            0, 3, gl.GL_FLOAT, False, self._stride, ctypes.c_void_p(0)
        )
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(
            1, 3, gl.GL_FLOAT, False, self._stride, ctypes.c_void_p(3 * 4)
        )
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(
            2, 2, gl.GL_FLOAT, False, self._stride, ctypes.c_void_p(6 * 4)
        )
        gl.glEnableVertexAttribArray(3)
        gl.glVertexAttribPointer(
            3, 3, gl.GL_FLOAT, False, self._stride, ctypes.c_void_p(8 * 4)
        )

    def render_frame(self, camera, batches):
        self.foliage.begin_frame()
        gl.glUseProgram(self.shader)
        self._set_camera_uniforms(camera)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.leaf_tex_id)
        gl.glUniform1i(self.texture_loc, 0)
        leaves = []
        draws = {}
        for batch in batches:
            if batch.kind in ("foliage", "limbs"):
                leaves.append((batch, None))
                continue
            if batch.radius and not self.visible(camera, *batch.center, batch.radius):
                continue
            if not batch.vertex_count:
                continue
            draws.setdefault((batch.vaos[0], batch.use_texture), []).append(
                (batch.first, batch.vertex_count)
            )
        for (vao, texture), entries in draws.items():
            gl.glBindVertexArray(vao)
            gl.glUniform1i(self.use_texture_loc, int(texture))
            first, count = np.asarray(entries, dtype=np.int32).T.copy()
            gl.glMultiDrawArrays(gl.GL_TRIANGLES, first, count, len(entries))
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
        leaves.sort(
            key=lambda entry: math.dist(entry[0].center, (camera.x, camera.y, camera.z))
        )
        self.foliage.draw(camera, leaves)

    def _surface_to_gl_texture(self, surface):

        import pygame

        key = id(surface)
        tex_id = self._sprite_tex_cache.get(key)
        if tex_id is not None:
            return tex_id

        data = pygame.image.tostring(
            pygame.transform.flip(surface, False, True), "RGBA", False
        )
        tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGBA,
            surface.get_width(),
            surface.get_height(),
            0,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            data,
        )
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        self._sprite_tex_cache[key] = tex_id
        return tex_id

    def render_billboard(self, camera, surface, x, y, z, width, height):

        import pygame

        tex_id = self._surface_to_gl_texture(surface)

        cy = math.cos(camera.yaw)
        sy = math.sin(camera.yaw)

        rx = cy
        rz = -sy

        hw = width * 0.5
        hh = height * 0.5

        corners = [
            (x - rx * hw, y, z - rz * hw),
            (x + rx * hw, y, z + rz * hw),
            (x + rx * hw, y + hh, z + rz * hw),
            (x - rx * hw, y + hh, z - rz * hw),
        ]

        data = []

        for tri in ((0, 1, 2), (0, 2, 3)):
            for idx in tri:
                cx, cyy, cz = corners[idx]
                data.extend([cx, cyy, cz, 0.0, 1.0, 0.0])
                if idx == 0:
                    data.extend([0.0, 0.0])
                elif idx == 1:
                    data.extend([1.0, 0.0])
                elif idx == 2:
                    data.extend([1.0, 1.0])
                else:
                    data.extend([0.0, 1.0])
                data.extend([255.0, 255.0, 255.0])

        gl.glUseProgram(self.shader)
        self._set_camera_uniforms(camera)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glUniform1i(self.texture_loc, 0)

        gl.glBindVertexArray(self.vao)
        self._define_attribs(self.dynamic_vbo)

        arr = (gl.GLfloat * len(data))(*data)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STREAM_DRAW)
        self._dynamic_capacity = ctypes.sizeof(arr)

        colour_array = (gl.GLfloat * 3)(255.0, 255.0, 255.0)
        gl.glUniform3fv(self.color_loc, 1, colour_array)
        gl.glUniform1i(self.use_texture_loc, 1)

        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)

        gl.glDisableVertexAttribArray(0)
        gl.glDisableVertexAttribArray(1)
        gl.glDisableVertexAttribArray(2)
        gl.glDisableVertexAttribArray(3)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

    def render_mesh_dynamic(self, camera, mesh, x, y, z, yaw=0.0, alpha=None):
        self.render_models(camera, [(mesh, x, y, z, yaw)], alpha)

    def render_models(self, camera, instances, alpha=None):
        groups = {}
        leaves = []
        for mesh, x, y, z, yaw in instances:
            if hasattr(getattr(mesh, "source", mesh), "leaf_instances") or hasattr(
                getattr(mesh, "source", mesh), "branch_instances"
            ):
                leaves.append((mesh, x, y, z, yaw))
                continue
            if not mesh.faces:
                continue
            source = getattr(mesh, "source", mesh)
            cached = getattr(source, "_packed_dynamic", None)
            if cached is None:
                cached = pack_meshes([source], spatial=False)[0][1]
                source._packed_dynamic = cached
            data = cached.copy()
            if source is not mesh:
                rotation, offset = (
                    np.eye(3, dtype=np.float32),
                    np.zeros(3, dtype=np.float32),
                )
                for pivot, pitch, turn in mesh.rotations:
                    cp, sp, ct, st = (
                        math.cos(pitch),
                        math.sin(pitch),
                        math.cos(turn),
                        math.sin(turn),
                    )
                    matrix = np.array(
                        ((ct, st * sp, st * cp), (0, cp, -sp), (-st, ct * sp, ct * cp)),
                        dtype=np.float32,
                    )
                    pivot = np.asarray(pivot, dtype=np.float32)
                    offset = matrix @ offset + pivot - matrix @ pivot
                    rotation = matrix @ rotation
                data[:, :3] = data[:, :3] @ rotation.T + offset + mesh.translation
                data[:, 3:6] = data[:, 3:6] @ rotation.T
            cy, sy = math.cos(yaw), math.sin(yaw)
            # Placement is already supplied by the caller, including mesh.position.
            vertices = data[:, :3] - mesh.position
            data[:, 0] = vertices[:, 0] * cy + vertices[:, 2] * sy + x
            data[:, 1] = vertices[:, 1] + y
            data[:, 2] = -vertices[:, 0] * sy + vertices[:, 2] * cy + z
            nx, nz = data[:, 3].copy(), data[:, 5].copy()
            data[:, 3], data[:, 5] = nx * cy + nz * sy, -nx * sy + nz * cy
            groups.setdefault(mesh.texcoords is not None, []).append(data)
        if not groups:
            self.foliage.draw_models(camera, leaves, alpha)
            return
        gl.glUseProgram(self.shader)
        self._set_camera_uniforms(camera)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.leaf_tex_id)
        gl.glUniform1i(self.texture_loc, 0)
        gl.glUniform1f(self.alpha_loc, 1 if alpha is None else alpha)
        gl.glBindVertexArray(self.vao)
        self._define_attribs(self.dynamic_vbo)
        for texture, parts in groups.items():
            data = np.concatenate(parts)
            if data.nbytes > self._dynamic_capacity:
                self._dynamic_capacity = 1 << max(10, (data.nbytes - 1).bit_length())
                gl.glBufferData(
                    gl.GL_ARRAY_BUFFER, self._dynamic_capacity, None, gl.GL_STREAM_DRAW
                )
            gl.glBufferSubData(gl.GL_ARRAY_BUFFER, 0, data.nbytes, data)
            gl.glUniform1i(self.use_texture_loc, int(texture))
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(data))
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
        self.foliage.draw_models(camera, leaves, alpha)

    def close(self):
        self.scene_target.close()
        self.foliage.close()

        gl.glDeleteBuffers(1, [self.dynamic_vbo])
        gl.glDeleteVertexArrays(1, [self.vao])
        gl.glDeleteTextures([self.leaf_tex_id, *self._sprite_tex_cache.values()])
        gl.glDeleteProgram(self.shader)
