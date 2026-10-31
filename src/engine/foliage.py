import numpy as np

from engine.mesh import Mesh


class LeafCloud(Mesh):
    def __init__(self, instances, position):
        self.leaf_instances = np.ascontiguousarray(instances, dtype=np.float32)
        self.position = position
        self.colour = (45, 125, 48)
        self.texcoords = None
        self.alpha = 1.0
        self._geometry = None

    @property
    def instance_count(self):
        return len(self.leaf_instances)

    def _expand(self):
        if self._geometry is None:
            data = self.leaf_instances
            base, axis, side = data[:, :3], data[:, 3:6], data[:, 6:9]
            points = (
                base[:, None, :]
                + axis[:, None, :] * np.array([0, 0.48, 1, 0.48])[None, :, None]
            )
            points[:, 1] += side
            points[:, 3] -= side
            points[:, 2, 1] -= 0.06
            points[:, 3, 1] -= np.linalg.norm(side, axis=1) * 0.3
            offsets = np.arange(len(data), dtype=np.int32)[:, None, None] * 4
            faces = (offsets + np.array([[0, 1, 2], [0, 2, 3]]))[..., :].reshape(-1, 3)
            self._geometry = (
                points.reshape(-1, 3).tolist(),
                faces.tolist(),
                np.repeat(data[:, 9:12], 4, axis=0).tolist(),
            )
        return self._geometry

    @property
    def vertices(self):
        return self._expand()[0]

    @property
    def faces(self):
        return self._expand()[1]

    @property
    def vertex_colours(self):
        return self._expand()[2]


class BranchCloud(Mesh):
    def __init__(self, instances, position):
        self.branch_instances = np.ascontiguousarray(instances, dtype=np.float32)
        self.position = position
        self.colour = (102, 74, 47)
        self.texcoords = None
        self.alpha = 1.0
        self._geometry = None

    def _expand(self):
        if self._geometry is None:
            from engine.trees import _merge, _tube

            parts = [
                _tube([row[:3], row[:3] + row[3:6]], row[6:8], tuple(row[9:12]), 3)
                for row in self.branch_instances
            ]
            mesh = _merge(parts, self.colour)
            self._geometry = (mesh.vertices, mesh.faces, mesh.vertex_colours)
        return self._geometry

    @property
    def vertices(self):
        return self._expand()[0]

    @property
    def faces(self):
        return self._expand()[1]

    @property
    def vertex_colours(self):
        return self._expand()[2]
