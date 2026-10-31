from OpenGL import GL as gl


class SceneTarget:
    def __init__(self, renderer):
        self.renderer = renderer
        self.framebuffer = self.texture = self.depth = None
        self.size = None
        driver = gl.glGetString(gl.GL_RENDERER).decode().lower()
        self.software = any(
            name in driver for name in ("llvmpipe", "softpipe", "software", "swrast")
        )
        self.saved = None

    def begin(self, width, height):
        r = self.renderer
        scale = min(1.0, 288 / width, 162 / height) if self.software else 1.0
        size = max(1, round(width * scale)), max(1, round(height * scale))
        self.saved = r.width, r.height, r.focal_length
        r.width, r.height = size
        r.focal_length *= scale
        if self.size != size:
            self.close()
            self.size = size
            self.framebuffer = gl.glGenFramebuffers(1)
            self.texture = gl.glGenTextures(1)
            self.depth = gl.glGenRenderbuffers(1)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.framebuffer)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D,
                0,
                gl.GL_RGBA8,
                *size,
                0,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
                None,
            )
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER,
                gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D,
                self.texture,
                0,
            )
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.depth)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, *size)
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER,
                gl.GL_DEPTH_ATTACHMENT,
                gl.GL_RENDERBUFFER,
                self.depth,
            )
            if (
                gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
                != gl.GL_FRAMEBUFFER_COMPLETE
            ):
                raise RuntimeError("Scene framebuffer is incomplete")
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.framebuffer)
        gl.glViewport(0, 0, *size)

    def end(self, width, height):
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self.framebuffer)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, 0)
        gl.glBlitFramebuffer(
            0,
            0,
            *self.size,
            0,
            0,
            width,
            height,
            gl.GL_COLOR_BUFFER_BIT,
            gl.GL_NEAREST if self.software else gl.GL_LINEAR,
        )
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glViewport(0, 0, width, height)
        r = self.renderer
        r.width, r.height, r.focal_length = self.saved

    def close(self):
        if self.framebuffer:
            gl.glDeleteFramebuffers(1, [self.framebuffer])
        if self.texture:
            gl.glDeleteTextures([self.texture])
        if self.depth:
            gl.glDeleteRenderbuffers(1, [self.depth])
        self.framebuffer = self.texture = self.depth = None
        self.size = None
