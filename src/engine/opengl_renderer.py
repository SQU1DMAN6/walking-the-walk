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

from engine.vector import Vec3


def _generate_leaf_texture(size=64):
    """Generate a procedural leaf texture with alpha.

    Returns (tex_id, width, height) — a 2D RGBA texture with leaf-like
    patterns that can be applied to canopy meshes.
    """
    rng = random.Random(42)
    # Base leaf colour: olive/grey-green
    pixels = bytearray(size * size * 4)
    # Generate a few leaf "blobs" scattered across the texture
    blobs = []
    for _ in range(12):
        cx = rng.uniform(0.0, 1.0)
        cy = rng.uniform(0.0, 1.0)
        rx = rng.uniform(0.15, 0.35)
        ry = rng.uniform(0.1, 0.25)
        angle = rng.uniform(0, math.pi * 2)
        ca, sa = math.cos(angle), math.sin(angle)
        # Leaf colour variation
        lr = rng.uniform(50, 100)
        lg = rng.uniform(100, 160)
        lb = rng.uniform(30, 70)
        blobs.append((cx, cy, rx, ry, ca, sa, lr, lg, lb))

    for py in range(size):
        for px in range(size):
            u = px / size
            v = py / size
            # Accumulate leaf coverage
            max_coverage = 0.0
            best_r = 0
            best_g = 0
            best_b = 0
            for (cx, cy, rx, ry, ca, sa, lr, lg, lb) in blobs:
                # Transform to blob-local space
                dx = u - cx
                dy = v - cy
                # Rotate
                lu = dx * ca + dy * sa
                lv = -dx * sa + dy * ca
                # Elliptical distance
                dist = (lu / rx) ** 2 + (lv / ry) ** 2
                if dist < 1.0:
                    coverage = 1.0 - dist * dist
                    if coverage > max_coverage:
                        max_coverage = coverage
                        best_r, best_g, best_b = lr, lg, lb

            idx = (py * size + px) * 4
            if max_coverage > 0.05:
                # Add some vein-like detail
                vein = 0.8 + 0.2 * math.sin(u * 20 + v * 15) * math.sin(v * 25 - u * 10)
                pixels[idx] = int(min(255, best_r * vein * (0.7 + 0.3 * max_coverage)))
                pixels[idx + 1] = int(min(255, best_g * vein * (0.7 + 0.3 * max_coverage)))
                pixels[idx + 2] = int(min(255, best_b * vein * (0.7 + 0.3 * max_coverage)))
                pixels[idx + 3] = int(min(255, max_coverage * 255))
            else:
                # Transparent
                pixels[idx] = 0
                pixels[idx + 1] = 0
                pixels[idx + 2] = 0
                pixels[idx + 3] = 0

    tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexImage2D(
        gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, size, size, 0,
        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, bytes(pixels)
    )
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex_id, size, size


class OpenGLRenderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.focal_length = 400.0
        self.near = 0.1
        self.far = 200.0

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)

        vertex_src = """
        #version 330 core
        layout (location = 0) in vec3 in_cam_pos;
        layout (location = 1) in vec3 in_normal;
        layout (location = 2) in vec2 in_texcoord;

        uniform float u_focal;
        uniform float u_w;
        uniform float u_h;
        uniform float u_near;
        uniform float u_far;

        out vec3 v_normal;
        out vec2 v_texcoord;

        void main() {
            float z = max(in_cam_pos.z, 0.001);
            float ndc_x = in_cam_pos.x * u_focal / (u_w * 0.5);
            float ndc_y = in_cam_pos.y * u_focal / (u_h * 0.5);
            float clip_z = u_far * (z - u_near) / (u_far - u_near);
            gl_Position = vec4(ndc_x, ndc_y, clip_z, z);
            v_normal = in_normal;
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
            vec3 norm = normalize(v_normal);
            float diff = max(dot(norm, -u_light_dir), 0.0);
            float lit = u_ambient + u_diffuse * diff;

            if (u_use_texture) {
                vec4 texel = texture(u_texture, v_texcoord);
                if (texel.a < 0.1) discard;
                // Mix base colour with texture
                base = mix(base, texel.rgb, texel.a);
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

        # Generate procedural leaf texture
        self.leaf_tex_id, self.leaf_tex_w, self.leaf_tex_h = _generate_leaf_texture(64)

    def _compute_normal(self, p0, p1, p2):
        """Compute the normal of a triangle (p0, p1, p2) in camera space."""
        ax = p1[0] - p0[0]
        ay = p1[1] - p0[1]
        az = p1[2] - p0[2]
        bx = p2[0] - p0[0]
        by = p2[1] - p0[1]
        bz = p2[2] - p0[2]
        nx = ay * bz - az * by
        ny = az * bx - ax * bz
        nz = ax * by - ay * bx
        # Normalise
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length == 0:
            return (0.0, 1.0, 0.0)
        return (nx / length, ny / length, nz / length)

    def _mesh_to_vertex_list(self, camera, mesh):
        cos_yaw = math.cos(camera.yaw)
        sin_yaw = math.sin(camera.yaw)
        cos_pitch = math.cos(-camera.pitch)
        sin_pitch = math.sin(-camera.pitch)

        verts = []
        for vx, vy, vz in mesh.vertices:
            x = vx + mesh.position[0] - camera.x
            y = vy + mesh.position[1] - camera.y
            z = vz + mesh.position[2] - camera.z

            rx = x * cos_yaw - z * sin_yaw
            rz = x * sin_yaw + z * cos_yaw
            ry = y * cos_pitch - rz * sin_pitch
            rz2 = y * sin_pitch + rz * cos_pitch
            verts.append((rx, ry, rz2))

        # Build triangles with normals — no backface culling (double-sided)
        triangles = []  # each entry: ((x,y,z,nx,ny,nz,u,v) for each of 3 verts)
        for face in mesh.faces:
            i0, i1, i2 = face
            p0 = verts[i0]
            p1 = verts[i1]
            p2 = verts[i2]

            # Compute normal
            nx, ny, nz = self._compute_normal(p0, p1, p2)

            # Get texcoords if available
            if mesh.texcoords:
                t0 = mesh.texcoords[i0]
                t1 = mesh.texcoords[i1]
                t2 = mesh.texcoords[i2]
            else:
                t0 = (0.0, 0.0)
                t1 = (1.0, 0.0)
                t2 = (0.5, 1.0)

            tri = (
                (p0[0], p0[1], p0[2], nx, ny, nz, t0[0], t0[1]),
                (p1[0], p1[1], p1[2], nx, ny, nz, t1[0], t1[1]),
                (p2[0], p2[1], p2[2], nx, ny, nz, t2[0], t2[1]),
            )
            triangles.append(tri)

        return triangles

    def render_mesh(self, camera, framebuffer, mesh):
        triangles = self._mesh_to_vertex_list(camera, mesh)
        if not triangles:
            return

        # Interleave: pos.x, pos.y, pos.z, norm.x, norm.y, norm.z, tex.u, tex.v
        data = []
        for tri in triangles:
            for v in tri:
                data.extend(v)
        data_len = len(data)
        if data_len == 0:
            return

        # Per-vertex stride = 8 floats (3 pos + 3 normal + 2 texcoord)
        float_count = data_len
        vertex_count = float_count // 8

        import ctypes
        gl.glUseProgram(self.shader)

        gl.glUniform1f(self.focal_loc, self.focal_length)
        gl.glUniform1f(self.w_loc, float(self.width))
        gl.glUniform1f(self.h_loc, float(self.height))
        gl.glUniform1f(self.near_loc, self.near)
        gl.glUniform1f(self.far_loc, self.far)

        # Light direction: pointing down and slightly forward in camera space
        light_dir = (0.0, -0.5, -1.0)
        ld_len = math.sqrt(light_dir[0]**2 + light_dir[1]**2 + light_dir[2]**2)
        ld = (light_dir[0] / ld_len, light_dir[1] / ld_len, light_dir[2] / ld_len)
        gl.glUniform3fv(self.light_dir_loc, 1, (gl.GLfloat * 3)(*ld))
        gl.glUniform1f(self.ambient_loc, 0.35)
        gl.glUniform1f(self.diffuse_loc, 0.65)

        # Determine if this mesh should use the leaf texture
        # Use texture for canopy meshes (identified by greenish colour)
        use_texture = mesh.texcoords is not None
        gl.glUniform1i(self.use_texture_loc, 1 if use_texture else 0)

        if use_texture:
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.leaf_tex_id)
            gl.glUniform1i(self.texture_loc, 0)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        arr = (gl.GLfloat * float_count)(*data)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STATIC_DRAW)

        stride = 8 * 4  # 8 floats per vertex

        # Position attribute (location = 0)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, stride, ctypes.c_void_p(0))

        # Normal attribute (location = 1)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, False, stride, ctypes.c_void_p(3 * 4))

        # Texcoord attribute (location = 2)
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, False, stride, ctypes.c_void_p(6 * 4))

        colour_array = (gl.GLfloat * 3)(mesh.colour[0], mesh.colour[1], mesh.colour[2])
        gl.glUniform3fv(self.color_loc, 1, colour_array)

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, vertex_count)

        gl.glDisableVertexAttribArray(0)
        gl.glDisableVertexAttribArray(1)
        gl.glDisableVertexAttribArray(2)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
