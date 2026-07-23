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
        self.focal_length = 400

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)

        vertex_src = """
        #version 330 core
        uniform mat4 u_mvp;
        in vec2 in_pos;
        in vec3 in_col;
        out vec3 v_col;
        void main() {
            gl_Position = u_mvp * vec4(in_pos, 0.0, 1.0);
            v_col = in_col;
        }
        """

        fragment_src = """
        #version 330 core
        in vec3 v_col;
        out vec4 f_col;
        void main() {
            f_col = vec4(v_col / 255.0, 1.0);
        }
        """

        if not HAS_OPENGL:
            raise RuntimeError("PyOpenGL is not available")

        self.shader = shaders.compileProgram(
            shaders.compileShader(vertex_src, gl.GL_VERTEX_SHADER),
            shaders.compileShader(fragment_src, gl.GL_FRAGMENT_SHADER),
        )

        self.pos_loc = gl.glGetAttribLocation(self.shader, "in_pos")
        self.col_loc = gl.glGetAttribLocation(self.shader, "in_col")
        self.mvp_loc = gl.glGetUniformLocation(self.shader, "u_mvp")

    def _project(self, vertex):
        z = vertex.z

        if z <= 0.1:
            return None

        x = vertex.x * self.focal_length / z
        y = vertex.y * self.focal_length / z

        screen_x = self.width / 2 + x
        screen_y = self.height / 2 - y

        return (screen_x, screen_y)

    def _build_triangle_data(self, camera, mesh):
        cos_yaw = math.cos(camera.yaw)
        sin_yaw = math.sin(camera.yaw)

        cos_pitch = math.cos(camera.pitch)
        sin_pitch = math.sin(camera.pitch)

        verts = []

        for vx, vy, vz in mesh.vertices:
            x = vx + mesh.position[0]
            y = vy + mesh.position[1]
            z = vz + mesh.position[2]

            x -= camera.x
            y -= camera.y
            z -= camera.z

            rx = x * cos_yaw - z * sin_yaw
            rz = x * sin_yaw + z * cos_yaw

            ry = y * cos_pitch - rz * sin_pitch
            rz2 = y * sin_pitch + rz * cos_pitch

            p = self._project(Vec3(rx, ry, rz2))
            if p is None:
                return None

            ndc_x = (p[0] / self.width) * 2.0 - 1.0
            ndc_y = 1.0 - (p[1] / self.height) * 2.0
            verts.append((ndc_x, ndc_y, mesh.colour[0], mesh.colour[1], mesh.colour[2]))

        triangles = []

        for face in mesh.faces:
            i0, i1, i2 = face
            p0 = verts[i0]
            p1 = verts[i1]
            p2 = verts[i2]

            cross = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])
            if cross >= 0:
                continue

            triangles.append((p0, p1, p2))

        return triangles

    def render_mesh(self, camera, framebuffer, mesh):
        triangles = self._build_triangle_data(camera, mesh)

        if not triangles:
            return

        data = []

        for tri in triangles:
            for v in tri:
                data.extend(v)

        gl.glUseProgram(self.shader)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, bytes(gl.GLfloat * len(data))(*data), gl.GL_STATIC_DRAW)

        stride = 5 * 4
        gl.glEnableVertexAttribArray(self.pos_loc)
        gl.glVertexAttribPointer(self.pos_loc, 2, gl.GL_FLOAT, False, stride, gl.GLvoidp(0))
        gl.glEnableVertexAttribArray(self.col_loc)
        gl.glVertexAttribPointer(self.col_loc, 3, gl.GL_FLOAT, False, stride, gl.GLvoidp(2 * 4))

        gl.glUniformMatrix4fv(self.mvp_loc, 1, False, (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1))

        gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(data) // 5)

        gl.glDisableVertexAttribArray(self.pos_loc)
        gl.glDisableVertexAttribArray(self.col_loc)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)