class Mesh:
    def __init__(
        self,
        vertices,
        faces,
        colour,
        position
    ):
        self.vertices = vertices
        self.faces = faces
        self.colour = colour
        self.position = position

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

def create_ground(
        width,
        depth,
        colour,
        position
):
    hw = width / 2
    hd = depth / 2

    vertices = [
        (-hw, 0.0, -hd),
        (hw, 0.0, -hd),
        (hw, 0.0, hd),
        (-hw, 0.0, hd),
    ]

    faces = [
        (0, 1, 2),
        (0, 2, 3),
    ]

    back_faces = [
        (0, 2, 1),
        (0, 3, 2),
    ]
    return Mesh(
        vertices,
        faces + back_faces,
        colour,
        position
    )
