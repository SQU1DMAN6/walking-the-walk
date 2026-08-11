"""Procedural chunk streaming.

The world is divided into fixed-size tiles (chunks). A ChunkManager keeps
only the chunks within a render distance of the player loaded, baking each
chunk's meshes into persistent GPU VBOs once on load and freeing them on
unload. This keeps memory/CPU bounded while allowing an effectively
infinite explorable world.
"""
import math

from engine.worldgen import generate_chunk
from engine.opengl_renderer import build_batches


class Chunk:
    """A loaded chunk: its grid coords, meshes, obstacles, discoveries and
    the GPU batches (VBOs) baked from its meshes."""

    __slots__ = ('cx', 'cz', 'meshes', 'obstacles', 'discoveries', 'resources', 'batches')

    def __init__(self, cx, cz, meshes, obstacles, discoveries, resources, batches):
        self.cx = cx
        self.cz = cz
        self.meshes = meshes
        self.obstacles = obstacles
        self.discoveries = discoveries
        self.resources = resources
        self.batches = batches


class ChunkManager:
    """Streams chunks around a player position."""

    def __init__(self, seed, chunk_size=40, render_distance=2, segments=12):
        self.seed = seed
        self.chunk_size = chunk_size
        self.render_distance = render_distance
        self.segments = segments

        # key: (cx, cz) -> Chunk
        self.chunks = {}

    # Helpers

    def chunk_at(self, x, z):
        """Return the chunk grid coords containing world position (x, z)."""
        cx = int(math.floor(x / self.chunk_size))
        cz = int(math.floor(z / self.chunk_size))
        return (cx, cz)

    def _load(self, cx, cz):
        """Generate and bake a chunk, then cache it."""
        data = generate_chunk(
            cx, cz, self.seed,
            chunk_size=self.chunk_size,
            segments=self.segments,
        )
        batches = build_batches(data["meshes"])
        chunk = Chunk(
            cx, cz,
            data["meshes"],
            data["obstacles"],
            data["discoveries"],
            data["resources"],
            batches,
        )
        self.chunks[(cx, cz)] = chunk
        return chunk

    def _unload(self, cx, cz):
        """Free a chunk's GPU VBOs and drop it from the cache."""
        chunk = self.chunks.pop((cx, cz), None)
        if chunk is None:
            return
        import OpenGL.GL as gl
        for batch in chunk.batches:
            if batch.vbo:
                gl.glDeleteBuffers(1, [batch.vbo])

    # Public API

    def update(self, player_x, player_z):
        """Ensure all chunks within render distance are loaded, and unload
        any that have fallen out of range. Returns the list of loaded
        chunks (for rendering)."""
        pcx, pcz = self.chunk_at(player_x, player_z)
        rd = self.render_distance

        # Determine the set of chunks that should be loaded
        wanted = set()
        for dx in range(-rd, rd + 1):
            for dz in range(-rd, rd + 1):
                wanted.add((pcx + dx, pcz + dz))

        # Load missing chunks
        for key in wanted:
            if key not in self.chunks:
                self._load(*key)

        # Unload chunks no longer wanted
        for key in list(self.chunks.keys()):
            if key not in wanted:
                self._unload(*key)

        return list(self.chunks.values())

    def all_batches(self):
        """Flatten all loaded chunks' GPU batches into one list for drawing."""
        batches = []
        for chunk in self.chunks.values():
            batches.extend(chunk.batches)
        return batches

    def all_obstacles(self):
        """Flatten all loaded chunks' collision circles."""
        obstacles = []
        for chunk in self.chunks.values():
            obstacles.extend(chunk.obstacles)
        return obstacles

    def all_discoveries(self):
        """Flatten all loaded chunks' discovery landmarks."""
        discoveries = []
        for chunk in self.chunks.values():
            discoveries.extend(chunk.discoveries)
        return discoveries

    def all_resources(self):
        """Flatten all loaded chunks' collectible resource nodes."""
        resources = []
        for chunk in self.chunks.values():
            resources.extend(chunk.resources)
        return resources

    def clear(self):
        """Unload all chunks (frees all GPU VBOs)."""
        for key in list(self.chunks.keys()):
            self._unload(*key)
