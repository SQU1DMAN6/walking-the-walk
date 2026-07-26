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

        uniform float u_focal;
        uniform float u_w;
        uniform float u_h;
        uniform float u_near;
        uniform float u_far;

        void main() {
            float z = max(in_cam_pos.z, 0.001);
            float ndc_x = in_cam_pos.x * u_focal / (u_w * 0.5);
            float ndc_y = in_cam_pos.y * u_focal / (u_h * 0.5);
            float clip_z = u_far * (z - u_near) / (u_far - u_near);
            gl_Position = vec4(ndc_x, ndc_y, clip_z, z);
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

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_CULL_FACE)

        self.color_loc = gl.glGetUniformLocation(self.shader, "u_color")
        self.focal_loc = gl.glGetUniformLocation(self.shader, "u_focal")
        self.w_loc = gl.glGetUniformLocation(self.shader, "u_w")
        self.h_loc = gl.glGetUniformLocation(self.shader, "u_h")
        self.near_loc = gl.glGetUniformLocation(self.shader, "u_near")
        self.far_loc = gl.glGetUniformLocation(self.shader, "u_far")

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

            # Send raw camera-space position to the GPU.
            # The vertex shader handles projection and the GPU handles
            # homogeneous clipping for triangles that straddle the near plane.
            verts.append((rx, ry, rz2))

        triangles = []
        for face in mesh.faces:
            i0, i1, i2 = face
            p0 = verts[i0]
            p1 = verts[i1]
            p2 = verts[i2]
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

        gl.glUniform1f(self.focal_loc, self.focal_length)
        gl.glUniform1f(self.w_loc, float(self.width))
        gl.glUniform1f(self.h_loc, float(self.height))
        gl.glUniform1f(self.near_loc, self.near)
        gl.glUniform1f(self.far_loc, self.far)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        arr = (gl.GLfloat * data_len)(*data)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, gl.GL_STATIC_DRAW)

        stride = 3 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, False, stride, gl.GLvoidp(0))

        colour_array = (gl.GLfloat * 3)(mesh.colour[0], mesh.colour[1], mesh.colour[2])
        gl.glUniform3fv(self.color_loc, 1, colour_array)

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, data_len // 3)

        gl.glDisableVertexAttribArray(0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)