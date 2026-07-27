try:
    import OpenGL.GL as gl
    import OpenGL.GL.shaders as shaders
    HAS_OPENGL = True
    print("Say Hi to OpenGL!")
except Exception:
    HAS_OPENGL = False
    print("No OpenGL :(")

import math
import random
import struct

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
                pixels[idx:idx+4] = b'\x00\x00\x00\x00'

    tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, size, size, 0,
                    gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, bytes(pixels))
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex_id, size, size


def _build_vertex_data(mesh):
    """Pre-compute flattened vertex data for a mesh.

    This is called once at creation time, not every frame.
    Result is cached on mesh._vertex_data.
    """
    if mesh._vertex_data is not None:
        return mesh._vertex_data, mesh._vertex_count

    data = []
    for face in mesh.faces:
        for idx in face:
            vx, vy, vz = mesh.vertices[idx]
            wx = vx + mesh.position[0]
            wy = vy + mesh.position[1]
            wz = vz + mesh.position[2]
            data.extend([wx, wy, wz, 0.0, 1.0, 0.0])
            if mesh.texcoords:
                data.extend(mesh.texcoords[idx])
            else:
                data.extend([0.0, 0.0])

    mesh._vertex_data = data
    mesh._vertex_count = len(data) // 8
    return mesh._vertex_data, mesh._vertex_count


class OpenGLRenderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.focal_length = 400.0
        self.near = 0.1
        self.far = 200.0

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)

        # Cache of camera rotation values to avoid recomputing per mesh
        self._cos_yaw = 1.0
        self._sin_yaw = 0.0
        self._cos_pitch = 1.0
        self._sin_pitch = 0.0
        self._ld = (0.0, -0.8, 0.4)

        vertex_src = """
        #version 330 core
        layout (location = 0) in vec3 in_pos;
        layout (location = 1) in vec3 in_normal;
        layout (location = 2) in vec2 in_texcoord;

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

        in vec3 v_normal;
        in vec2 v_texcoord;

        out vec4 f_col;

        void main() {
            vec3 base = u_color / 255.0;
            float diff = max(dot(normalize(v_normal), -u_light_dir), 0.0);
            float lit = u_ambient + u_diffuse * diff;

            if (u_use_texture) {
                vec4 texel = texture(u_texture, v_texcoord);
                if (texel.a < 0.05) discard;
                base = mix(base, texel.rgb, texel.a * 0.8);
            }

            f_col = vec4(base * lit, 1.0);
            if (f_col.r < 0.01 && f_col.g < 0.01 && f_col.b < 0.01) discard;
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

        self.leaf_tex_id, _, _ = _generate_leaf_texture(64)

        # World-space sun direction (normalised)
        sun_dir = (0.4, -0.8, 0.4)
        sd_len = math.sqrt(sun_dir[0]**2 + sun_dir[1]**2 + sun_dir[2]**2)
        self.sun_world = (sun_dir[0] / sd_len, sun_dir[1] / sd_len, sun_dir[2] / sd_len)

    def _update_camera_uniforms(self, camera):
        """Update camera rotation uniforms (called once per frame, not per mesh)."""
        cy = math.cos(camera.yaw)
        sy = math.sin(camera.yaw)
        cp = math.cos(-camera.pitch)
        sp = math.sin(-camera.pitch)

        self._cos_yaw = cy
        self._sin_yaw = sy
        self._cos_pitch = cp
        self._sin_pitch = sp

        gl.glUniform3f(self.cam_pos_loc, camera.x, camera.y, camera.z)
        gl.glUniform1f(self.cos_yaw_loc, cy)
        gl.glUniform1f(self.sin_yaw_loc, sy)
        gl.glUniform1f(self.cos_pitch_loc, cp)
        gl.glUniform1f(self.sin_pitch_loc, sp)

        # Update light direction in camera space
        lx, ly, lz = self.sun_world
        rx = lx * cy + lz * sy
        rz = -lx * sy + lz * cy
        ry = ly * cp - rz * sp
        rz2 = ly * sp + rz * cp
        self._ld = (rx, ry, rz2)
        gl.glUniform3f(self.light_dir_loc, rx, ry, rz2)

    def render_mesh(self, camera, framebuffer, mesh):
        vertex_data, vertex_count = _build_vertex_data(mesh)
        if vertex_count == 0:
            return

        import ctypes
        gl.glUseProgram(self.shader)

        # Update camera uniforms (idempotent per frame — only first call matters)
        self._update_camera_uniforms(camera)

        gl.glUniform1f(self.focal_loc, self.focal_length)
        gl.glUniform1f(self.w_loc, float(self.width))
        gl.glUniform1f(self.h_loc, float(self.height))
        gl.glUniform1f(self.near_loc, self.near)
        gl.glUniform1f(self.far_loc, self.far)

        gl.glUniform1f(self.ambient_loc, 0.35)
        gl.glUniform1f(self.diffuse_loc, 0.65)

        use_texture = mesh.texcoords is not None
        gl.glUniform1i(self.use_texture_loc, 1 if use_texture else 0)
        if use_texture:
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.leaf_tex_id)
            gl.glUniform1i(self.texture_loc, 0)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        arr = (gl.GLfloat * len(vertex_data))(*vertex_data)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STREAM_DRAW)

        stride = 8 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, False, stride, ctypes.c_void_p(3 * 4))
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, False, stride, ctypes.c_void_p(6 * 4))

        colour_array = (gl.GLfloat * 3)(mesh.colour[0], mesh.colour[1], mesh.colour[2])
        gl.glUniform3fv(self.color_loc, 1, colour_array)

        gl.glDrawArrays(gl.GL_TRIANGLES, 0, vertex_count)

        gl.glDisableVertexAttribArray(0)
        gl.glDisableVertexAttribArray(1)
        gl.glDisableVertexAttribArray(2)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)