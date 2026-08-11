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

from engine.vector import Vec3


def _generate_leaf_texture(size=64):
    """Generate a procedural Australian eucalyptus leaf texture."""
    rng = random.Random(42)
    pixels = bytearray(size * size * 4)

    leaf_colours = [
        (65, 120, 50), (80, 140, 55), (95, 130, 60),
        (110, 150, 65), (140, 160, 70), (55, 100, 45), (75, 110, 50),
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
        blobs.append((cx, cy, rx, ry, ca, sa, colour[0], colour[1], colour[2], crisp, tip_variation))

    for py in range(size):
        for px in range(size):
            u = px / size
            v = py / size
            max_coverage = 0.0
            best_r = best_g = best_b = 0

            for (cx, cy, rx, ry, ca, sa, lr, lg, lb, crisp, tip_var) in blobs:
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
                vein = 0.85 + 0.15 * math.sin(u * 15 + v * 12) * math.sin(v * 20 - u * 8)
                spot = 0.9 + 0.1 * math.sin(u * 40 + v * 30) * math.cos(v * 25 - u * 35)
                pixels[idx] = int(min(255, best_r * vein * spot * (0.6 + 0.4 * max_coverage)))
                pixels[idx + 1] = int(min(255, best_g * vein * spot * (0.6 + 0.4 * max_coverage)))
                pixels[idx + 2] = int(min(255, best_b * vein * spot * (0.6 + 0.4 * max_coverage)))
                alpha_noise = 0.85 + 0.15 * math.sin(u * 50 + v * 45) * math.cos(v * 35 - u * 40)
                pixels[idx + 3] = int(min(255, max_coverage * 255 * alpha_noise))
            else:
                pixels[idx:idx + 4] = b'\x00\x00\x00\x00'

    tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, size, size, 0,
                    gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, bytes(pixels))
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex_id


def _face_normal(v0, v1, v2):
    """Compute the normal (in object space) of a triangle."""
    ux = v1[0] - v0[0]
    uy = v1[1] - v0[1]
    uz = v1[2] - v0[2]
    wx = v2[0] - v0[0]
    wy = v2[1] - v0[1]
    wz = v2[2] - v0[2]
    nx = uy * wz - uz * wy
    ny = uz * wx - ux * wz
    nz = ux * wy - uy * wx
    nl = math.sqrt(nx * nx + ny * ny + nz * nz)
    if nl < 1e-9:
        return (0.0, 1.0, 0.0)
    return (nx / nl, ny / nl, nz / nl)


def _build_vertex_data(mesh):
    """Pre-compute flattened, world-space vertex data with real per-face
    normals and per-vertex colours. Cached on the mesh; the world is static
    so this is baked once.

    Layout per vertex: [pos xyz, normal xyz, uv xy, colour rgb] = 11 floats.
    """
    if mesh._vertex_data is not None:
        return mesh._vertex_data, mesh._vertex_count

    data = []
    for face in mesh.faces:
        i0, i1, i2 = face
        n = _face_normal(mesh.vertices[i0], mesh.vertices[i1], mesh.vertices[i2])
        for idx in face:
            vx, vy, vz = mesh.vertices[idx]
            wx = vx + mesh.position[0]
            wy = vy + mesh.position[1]
            wz = vz + mesh.position[2]
            data.extend([wx, wy, wz, n[0], n[1], n[2]])
            if mesh.texcoords:
                data.extend(mesh.texcoords[idx])
            else:
                data.extend([0.0, 0.0])
            # Per-vertex colour (falls back to mesh colour)
            if mesh.vertex_colours is not None:
                c = mesh.vertex_colours[idx]
                data.extend([c[0], c[1], c[2]])
            else:
                data.extend([mesh.colour[0], mesh.colour[1], mesh.colour[2]])

    mesh._vertex_data = data
    mesh._vertex_count = len(data) // 11
    return mesh._vertex_data, mesh._vertex_count


def _mesh_bake(mesh):
    """Return flattened object-space per-triangle arrays for dynamic meshes:
    (vertices, normals, texcoords, colours). Cached on the mesh."""
    cache = getattr(mesh, '_bake_cache', None)
    if cache is not None:
        return cache

    verts = []
    norms = []
    uvs = []
    cols = []
    for face in mesh.faces:
        i0, i1, i2 = face
        n = _face_normal(mesh.vertices[i0], mesh.vertices[i1], mesh.vertices[i2])
        for idx in face:
            verts.extend(mesh.vertices[idx])
            norms.extend(n)
            if mesh.texcoords:
                uvs.extend(mesh.texcoords[idx])
            else:
                uvs.extend((0.0, 0.0))
            if mesh.vertex_colours is not None:
                cols.extend(mesh.vertex_colours[idx])
            else:
                cols.extend(mesh.colour)

    cache = (verts, norms, uvs, cols)
    mesh._bake_cache = cache
    return cache


def _transform_dynamic(mesh, x, y, z, yaw=0.0):
    """Build world-space flattened data from an object-space mesh bake,
    applying a Y-axis rotation (yaw) and translation. Result layout:
    [pos xyz, normal xyz, uv xy, colour rgb] per vertex."""
    verts, norms, uvs, cols = _mesh_bake(mesh)
    cy = math.cos(yaw)
    sy = math.sin(yaw)

    out = []
    vcount = len(verts) // 3
    for i in range(vcount):
        vx = verts[i * 3]
        vy = verts[i * 3 + 1]
        vz = verts[i * 3 + 2]
        # rotate around Y
        rx = vx * cy + vz * sy
        rz = -vx * sy + vz * cy
        out.extend([rx + x, vy + y, rz + z])

        nx, ny, nz = norms[i * 3], norms[i * 3 + 1], norms[i * 3 + 2]
        nrx = nx * cy + nz * sy
        nrz = -nx * sy + nz * cy
        out.extend([nrx, ny, nrz])

        out.extend([uvs[i * 2], uvs[i * 2 + 1]])
        out.extend([cols[i * 3], cols[i * 3 + 1], cols[i * 3 + 2]])
    return out


class BatchGroup:
    """A group of meshes with the same colour, combined into one persistent VBO.
    The vertex data is uploaded to the GPU exactly once at build time."""
    __slots__ = ('colour', 'use_texture', 'vertex_data', 'vertex_count', 'vbo')

    def __init__(self, colour, use_texture, vertex_data, vertex_count, vbo):
        self.colour = colour
        self.use_texture = use_texture
        self.vertex_data = vertex_data
        self.vertex_count = vertex_count
        self.vbo = vbo


def build_batches(meshes):
    """Group meshes by colour, compute real per-face normals and bake each
    group into a single persistent VBO. Returns a list of BatchGroup objects,
    one per unique colour. This makes all static geometry GPU-resident."""
    groups = {}

    for mesh in meshes:
        vd, vc = _build_vertex_data(mesh)
        if vc == 0:
            continue
        key = (mesh.colour, mesh.texcoords is not None)
        if key not in groups:
            groups[key] = []
        groups[key].append(vd)

    batches = []
    for (colour, use_texture), data_list in groups.items():
        total_len = sum(len(d) for d in data_list)
        combined = [0.0] * total_len
        offset = 0
        for d in data_list:
            combined[offset:offset + len(d)] = d
            offset += len(d)

        # Upload once to a dedicated VBO (static draw)
        vbo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        arr = (gl.GLfloat * len(combined))(*combined)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STATIC_DRAW)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)

        batches.append(BatchGroup(colour, use_texture, combined, len(combined) // 11, vbo))

    return batches


class OpenGLRenderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.focal_length = 400.0
        self.near = 0.1
        self.far = 200.0

        # One VBO used for dynamic (moving) geometry uploads
        self.vao = gl.glGenVertexArrays(1)
        self.dynamic_vbo = gl.glGenBuffers(1)

        # Cache of uploaded sprite textures keyed by id(surface)
        self._sprite_tex_cache = {}

        # Per-batch uniform block location caching
        self._batch_data = []  # (vbo, vertex_count)

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

            float nrx = in_normal.x * u_cos_yaw - in_normal.z * u_sin_yaw;
            float nrz = in_normal.x * u_sin_yaw + in_normal.z * u_cos_yaw;
            float nry = in_normal.y * u_cos_pitch - nrz * u_sin_pitch;
            float nrz2 = in_normal.y * u_sin_pitch + nrz * u_cos_pitch;

            float z = max(rz2, 0.001);
            float ndc_x = rx * u_focal / (u_w * 0.5);
            float ndc_y = ry * u_focal / (u_h * 0.5);
            float clip_z = u_far * (z - u_near) / (u_far - u_near);
            gl_Position = vec4(ndc_x / z, ndc_y / z, clip_z / z, 1.0);
            v_normal = normalize(vec3(nrx, nry, nrz2));
            v_texcoord = in_texcoord;
            v_color = in_color;
            v_viewz = z;
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

        // Distance fog (atmospheric depth, outback haze)
        uniform vec3 u_fog_color;
        uniform float u_fog_near;
        uniform float u_fog_far;

        in vec3 v_normal;
        in vec2 v_texcoord;
        in vec3 v_color;
        in float v_viewz;

        out vec4 f_col;

        void main() {
            // Per-vertex colour (baked into the VBO) overrides the uniform
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

            // Blend into the warm outback haze with distance
            float fog = clamp((v_viewz - u_fog_near) / (u_fog_far - u_fog_near), 0.0, 1.0);
            final_col = mix(final_col, u_fog_color, fog);
            f_col = vec4(final_col, 1.0);
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

        self.leaf_tex_id = _generate_leaf_texture(64)

        # Warm outback sun direction (world space, normalised)
        sun_dir = (0.4, -0.8, 0.4)
        sd_len = math.sqrt(sun_dir[0] ** 2 + sun_dir[1] ** 2 + sun_dir[2] ** 2)
        self.sun_world = (sun_dir[0] / sd_len, sun_dir[1] / sd_len, sun_dir[2] / sd_len)

        # Warm outback haze colour
        self.fog_color = (0.82, 0.66, 0.48)
        # Faint fog that fully fades before the chunk boundary (render
        # distance 2 x chunk 40 = 80 units) to hide chunk pop-in.
        self.fog_near = 25.0
        self.fog_far = 70.0

        self._stride = 11 * 4

    def _set_camera_uniforms(self, camera):
        cy = math.cos(camera.yaw)
        sy = math.sin(camera.yaw)
        cp = math.cos(-camera.pitch)
        sp = math.sin(-camera.pitch)

        # Use the effective eye position (pivot + forward offset + head-bob)
        ex, ey, ez = camera.eye_position()
        gl.glUniform3f(self.cam_pos_loc, ex, ey, ez)
        gl.glUniform1f(self.cos_yaw_loc, cy)
        gl.glUniform1f(self.sin_yaw_loc, sy)
        gl.glUniform1f(self.cos_pitch_loc, cp)
        gl.glUniform1f(self.sin_pitch_loc, sp)

        # Light direction in camera space
        lx, ly, lz = self.sun_world
        rx = lx * cy + lz * sy
        rz = -lx * sy + lz * cy
        ry = ly * cp - rz * sp
        rz2 = ly * sp + rz * cp
        gl.glUniform3f(self.light_dir_loc, rx, ry, rz2)

        gl.glUniform1f(self.focal_loc, self.focal_length)
        gl.glUniform1f(self.w_loc, float(self.width))
        gl.glUniform1f(self.h_loc, float(self.height))
        gl.glUniform1f(self.near_loc, self.near)
        gl.glUniform1f(self.far_loc, self.far)

        gl.glUniform1f(self.ambient_loc, 0.45)
        gl.glUniform1f(self.diffuse_loc, 0.55)

        # Fog
        gl.glUniform3f(self.fog_color_loc, self.fog_color[0], self.fog_color[1], self.fog_color[2])
        gl.glUniform1f(self.fog_near_loc, self.fog_near)
        gl.glUniform1f(self.fog_far_loc, self.fog_far)

    def _define_attribs(self, vbo):
        """Bind a VBO and set the four vertex attribute pointers."""
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, self._stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, False, self._stride, ctypes.c_void_p(3 * 4))
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, False, self._stride, ctypes.c_void_p(6 * 4))
        gl.glEnableVertexAttribArray(3)
        gl.glVertexAttribPointer(3, 3, gl.GL_FLOAT, False, self._stride, ctypes.c_void_p(8 * 4))

    def render_frame(self, camera, batches):
        """Render all static batches. Camera uniforms are set once; each batch
        is a persistent VBO that only needs binding + a colour uniform + a draw
        call. All geometry is GPU-resident."""
        gl.glUseProgram(self.shader)
        self._set_camera_uniforms(camera)

        # Bind leaf texture once
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.leaf_tex_id)
        gl.glUniform1i(self.texture_loc, 0)

        gl.glBindVertexArray(self.vao)

        for batch in batches:
            if batch.vertex_count == 0:
                continue

            self._define_attribs(batch.vbo)

            colour_array = (gl.GLfloat * 3)(batch.colour[0], batch.colour[1], batch.colour[2])
            gl.glUniform3fv(self.color_loc, 1, colour_array)
            gl.glUniform1i(self.use_texture_loc, 1 if batch.use_texture else 0)

            gl.glDrawArrays(gl.GL_TRIANGLES, 0, batch.vertex_count)

        gl.glDisableVertexAttribArray(0)
        gl.glDisableVertexAttribArray(1)
        gl.glDisableVertexAttribArray(2)
        gl.glDisableVertexAttribArray(3)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

    def _surface_to_gl_texture(self, surface):
        """Convert a pygame surface to an OpenGL texture (cached by id).

        pygame Surfaces don't allow arbitrary attributes (they use __slots__),
        so we cache the texture id in a dict keyed by id(surface) instead.
        """
        import pygame
        key = id(surface)
        tex_id = self._sprite_tex_cache.get(key)
        if tex_id is not None:
            return tex_id

        data = pygame.image.tostring(
            pygame.transform.flip(surface, False, True), "RGBA", False)
        tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                        surface.get_width(), surface.get_height(), 0,
                        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        self._sprite_tex_cache[key] = tex_id
        return tex_id

    def render_billboard(self, camera, surface, x, y, z, width, height):
        """Render a camera-facing textured quad (billboard) at (x, y, z).

        The quad always faces the camera (billboarded around the Y axis).
        """
        import pygame
        tex_id = self._surface_to_gl_texture(surface)

        # Camera-facing orientation: the quad's normal points at the camera.
        # We build the quad in camera space so it always faces the viewer.
        # Compute the right vector in world space from the camera yaw.
        cy = math.cos(camera.yaw)
        sy = math.sin(camera.yaw)
        # Right vector (perpendicular to forward, in the XZ plane)
        rx = cy
        rz = -sy

        # Half extents
        hw = width * 0.5
        hh = height * 0.5

        # Quad corners in world space (centred at x, y, z, facing camera)
        # Bottom-left, bottom-right, top-right, top-left
        corners = [
            (x - rx * hw, y, z - rz * hw),
            (x + rx * hw, y, z + rz * hw),
            (x + rx * hw, y + hh, z + rz * hw),
            (x - rx * hw, y + hh, z - rz * hw),
        ]

        # Build vertex data: pos xyz, normal (0,1,0), uv xy, colour rgb (white)
        data = []
        # Two triangles: (0,1,2) and (0,2,3)
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

        # Bind the sprite texture
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glUniform1i(self.texture_loc, 0)

        gl.glBindVertexArray(self.vao)
        self._define_attribs(self.dynamic_vbo)

        arr = (gl.GLfloat * len(data))(*data)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STREAM_DRAW)

        # White base colour so the texture shows through fully
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

    def render_mesh_dynamic(self, camera, mesh, x, y, z, yaw=0.0):
        """Render a single moving mesh (e.g. an emu) by transforming it in
        Python (rotating around Y and translating), uploading to the dynamic
        VBO, and drawing. Used for a small number of animated entities."""
        data = _transform_dynamic(mesh, x, y, z, yaw)
        if not data:
            return

        gl.glUseProgram(self.shader)
        self._set_camera_uniforms(camera)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.leaf_tex_id)
        gl.glUniform1i(self.texture_loc, 0)

        gl.glBindVertexArray(self.vao)
        self._define_attribs(self.dynamic_vbo)

        arr = (gl.GLfloat * len(data))(*data)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STREAM_DRAW)

        colour = mesh.colour
        colour_array = (gl.GLfloat * 3)(colour[0], colour[1], colour[2])
        gl.glUniform3fv(self.color_loc, 1, colour_array)
        gl.glUniform1i(self.use_texture_loc, 1 if (mesh.texcoords is not None) else 0)

        gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(data) // 11)

        gl.glDisableVertexAttribArray(0)
        gl.glDisableVertexAttribArray(1)
        gl.glDisableVertexAttribArray(2)
        gl.glDisableVertexAttribArray(3)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
