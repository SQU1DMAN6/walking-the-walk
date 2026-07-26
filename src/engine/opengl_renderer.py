try:
    import OpenGL.GL as gl
    import OpenGL.GL.shaders as shaders
    HAS_OPENGL = True
    print("Say Hi to OpenGL!")
except Exception:
    HAS_OPENGL = False
    print("No OpenGL :(")

import math

from engine.vector import Vec3


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

        uniform float u_focal;
        uniform float u_w;
        uniform float u_h;
        uniform float u_near;
        uniform float u_far;

        out vec3 v_normal;

        void main() {
            float z = max(in_cam_pos.z, 0.001);
            float ndc_x = in_cam_pos.x * u_focal / (u_w * 0.5);
            float ndc_y = in_cam_pos.y * u_focal / (u_h * 0.5);
            float clip_z = u_far * (z - u_near) / (u_far - u_near);
            gl_Position = vec4(ndc_x, ndc_y, clip_z, z);
            v_normal = in_normal;
        }
        """

        fragment_src = """
        #version 330 core
        uniform vec3 u_color;
        uniform vec3 u_light_dir;
        uniform float u_ambient;
        uniform float u_diffuse;

        in vec3 v_normal;

        out vec4 f_col;

        void main() {
            vec3 base = u_color / 255.0;
            vec3 norm = normalize(v_normal);
            float diff = max(dot(norm, -u_light_dir), 0.0);
            float lit = u_ambient + u_diffuse * diff;
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

        self.color_loc = gl.glGetUniformLocation(self.shader, "u_color")
        self.focal_loc = gl.glGetUniformLocation(self.shader, "u_focal")
        self.w_loc = gl.glGetUniformLocation(self.shader, "u_w")
        self.h_loc = gl.glGetUniformLocation(self.shader, "u_h")
        self.near_loc = gl.glGetUniformLocation(self.shader, "u_near")
        self.far_loc = gl.glGetUniformLocation(self.shader, "u_far")
        self.light_dir_loc = gl.glGetUniformLocation(self.shader, "u_light_dir")
        self.ambient_loc = gl.glGetUniformLocation(self.shader, "u_ambient")
        self.diffuse_loc = gl.glGetUniformLocation(self.shader, "u_diffuse")

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

        # Build triangles with normals, applying backface culling.
        triangles = []  # each entry: ((x,y,z,nx,ny,nz) for each of 3 verts)
        for face in mesh.faces:
            i0, i1, i2 = face
            p0 = verts[i0]
            p1 = verts[i1]
            p2 = verts[i2]

            # Compute normal and cull backfaces
            nx, ny, nz = self._compute_normal(p0, p1, p2)

            # In camera space the view direction is +Z.
            # If the normal points away from the camera (nz > 0) the face is a backface.
            if nz > 0:
                continue

            tri = (
                (p0[0], p0[1], p0[2], nx, ny, nz),
                (p1[0], p1[1], p1[2], nx, ny, nz),
                (p2[0], p2[1], p2[2], nx, ny, nz),
            )
            triangles.append(tri)

        return triangles

    def render_mesh(self, camera, framebuffer, mesh):
        triangles = self._mesh_to_vertex_list(camera, mesh)
        if not triangles:
            return

        # Interleave: pos.x, pos.y, pos.z, norm.x, norm.y, norm.z
        data = []
        for tri in triangles:
            for v in tri:
                data.extend(v)
        data_len = len(data)
        if data_len == 0:
            return

        # Per-vertex stride = 6 floats (3 pos + 3 normal)
        float_count = data_len
        vertex_count = float_count // 6

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

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        arr = (gl.GLfloat * float_count)(*data)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STATIC_DRAW)

        stride = 6 * 4  # 6 floats per vertex

        # Position attribute (location = 0)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, stride, ctypes.c_void_p(0))

        # Normal attribute (location = 1)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, False, stride, ctypes.c_void_p(3 * 4))

        colour_array = (gl.GLfloat * 3)(mesh.colour[0], mesh.colour[1], mesh.colour[2])
        gl.glUniform3fv(self.color_loc, 1, colour_array)

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, vertex_count)

        gl.glDisableVertexAttribArray(0)
        gl.glDisableVertexAttribArray(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)