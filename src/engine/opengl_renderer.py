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

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)

        vertex_src = """
        #version 330 core
        layout (location = 0) in vec3 in_pos;
        void main() {
            gl_Position = vec4(in_pos.xy, 0.5, 1.0);
        }
        """

        fragment_src = """
        #version 330 core
        uniform vec3 u_color;
        out vec4 f_col;
        void main() {
            f_col = vec4(u_color / 255.0, 1.0);
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

        self.color_loc = gl.glGetUniformLocation(self.shader, "u_color")

    def _project(self, vertex):
        z = vertex.z
        if z <= 0.1:
            return None
        x = vertex.x * self.focal_length / z
        y = vertex.y * self.focal_length / z
        screen_x = self.width / 2 + x
        screen_y = self.height / 2 - y
        return (screen_x, screen_y)

    def _mesh_to_vertex_list(self, camera, mesh):
        cos_yaw = math.cos(camera.yaw)
        sin_yaw = math.sin(camera.yaw)
        cos_pitch = math.cos(camera.pitch)
        sin_pitch = math.sin(camera.pitch)

        verts = []
        valid = []
        for vx, vy, vz in mesh.vertices:
            x = vx + mesh.position[0] - camera.x
            y = vy + mesh.position[1] - camera.y
            z = vz + mesh.position[2] - camera.z

            rx = x * cos_yaw - z * sin_yaw
            rz = x * sin_yaw + z * cos_yaw
            ry = y * cos_pitch - rz * sin_pitch
            rz2 = y * sin_pitch + rz * cos_pitch

            if rz2 <= 0.1:
                valid.append(False)
                verts.append((0.0, 0.0, 0.0))
                continue

            p = self._project(Vec3(rx, ry, rz2))
            if p is None:
                valid.append(False)
                verts.append((0.0, 0.0, 0.0))
                continue

            ndc_x = (p[0] / self.width) * 2.0 - 1.0
            ndc_y = 1.0 - (p[1] / self.height) * 2.0
            ndc_z = 0.5
            valid.append(True)
            verts.append((ndc_x, ndc_y, ndc_z))

        triangles = []
        for face in mesh.faces:
            i0, i1, i2 = face
            if not (valid[i0] and valid[i1] and valid[i2]):
                continue
            p0 = verts[i0]
            p1 = verts[i1]
            p2 = verts[i2]

            cross = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])
            if cross <= 0:
                continue
            triangles.append((p0, p1, p2))
        return triangles

    def render_mesh(self, camera, framebuffer, mesh):
        triangles = self._mesh_to_vertex_list(camera, mesh)
        if not triangles:
            return

        data = []
        for tri in triangles:
            for v in tri:
                data.extend(v)
        data_len = len(data)
        if data_len == 0:
            return

        import ctypes
        gl.glUseProgram(self.shader)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        arr = (gl.GLfloat * data_len)(*data)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STATIC_DRAW)

        stride = 3 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, stride, gl.GLvoidp(0))

        colour_array = (gl.GLfloat * 3)(mesh.colour[0], mesh.colour[1], mesh.colour[2])
        gl.glUniform3fv(self.color_loc, 1, colour_array)

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, data_len // 3)

        gl.glDisableVertexAttribArray(0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)