class Mesh:
    def __init__(
        self,
        vertices,
        faces,
        colour,
        position,
        texcoords=None,
        vertex_colours=None,
        alpha=1.0,
    ):
        self.vertices = vertices
        self.faces = faces
        self.colour = colour
        self.position = position
        self.texcoords = texcoords


        self.vertex_colours = vertex_colours


        self.alpha = alpha

        self._vertex_data = None
        self._vertex_count = 0


def create_prism(
        width,
        height,
        depth,
        colour,
        position
):
    vertices = [
            (-width/2, -height/2, -depth/2),
            ( width/2, -height/2, -depth/2),
            ( width/2,  height/2, -depth/2),
            (-width/2,  height/2, -depth/2),
            (-width/2, -height/2,  depth/2),
            ( width/2, -height/2,  depth/2),
            ( width/2,  height/2,  depth/2),
            (-width/2,  height/2,  depth/2),
    ]

    faces = [
        (0,1,2),(0,2,3),
        (4,6,5),(4,7,6),
        (0,4,5),(0,5,1),
        (1,5,6),(1,6,2),
        (2,6,7),(2,7,3),
        (3,7,4),(3,4,0),
    ]

    return Mesh(vertices, faces, colour, position)

def create_pyramid(
        width,
        height,
        depth,
        colour,
        position
):

    hw = width / 2
    hd = depth / 2
    vertices = [
        (-hw, -height/2, -hd),
        ( hw, -height/2, -hd),
        ( hw, -height/2,  hd),
        (-hw, -height/2,  hd),
        (0.0,  height/2, 0.0),
    ]

    faces = [
        (0, 1, 4),
        (1, 2, 4),
        (2, 3, 4),
        (3, 0, 4),
        (0, 3, 2),
        (0, 2, 1),
    ]

    return Mesh(vertices, faces, colour, position)

def create_ground(
        width,
        depth,
        colour,
        position
):


    hw = width / 2
    hd = depth / 2
    segments = 20

    vertices = []
    texcoords = []
    for iz in range(segments + 1):
        for ix in range(segments + 1):
            x = -hw + (width * ix / segments)
            z = -hd + (depth * iz / segments)
            vertices.append((x, 0.0, z))
            texcoords.append((ix / segments, iz / segments))

    faces = []
    for iz in range(segments):
        for ix in range(segments):
            i0 = iz * (segments + 1) + ix
            i1 = iz * (segments + 1) + ix + 1
            i2 = (iz + 1) * (segments + 1) + ix
            i3 = (iz + 1) * (segments + 1) + ix + 1
            faces.append((i0, i1, i2))
            faces.append((i2, i1, i3))

    return Mesh(
        vertices,
        faces,
        colour,
        position,
        texcoords=texcoords,
    )
