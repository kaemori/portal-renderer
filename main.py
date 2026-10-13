import math
import keyboard
import mouse

from dataclasses import dataclass, asdict as _asdict

import turtle, time
from operator import itemgetter

from pprint import pprint

# patches keyboard.is_pressed() to work on linux
_check_output = __import__("subprocess", fromlist=["check_output"]).check_output
_kb_overload = lambda cmd, **kwargs: _check_output(
    ["dumpkeys", "-C", "/dev/tty1", *cmd[1:]] if cmd[0] == "dumpkeys" else cmd, **kwargs
)
_nix_kb = getattr(keyboard, "_nixkeyboard", None)
_nix_kb and setattr(_nix_kb, "ensure_root", lambda: 0)
_nix_kb and setattr(_nix_kb, "check_output", _kb_overload)


cos = math.cos
sin = math.sin
pi = math.pi


# helper maths
def asdict(*args, **kwargs):
    """DO NOT USE DATACLASS ASDICT. INSTEAD, USE THE OBJECT'S `to_dict()` METHOD."""
    raise NotImplementedError(
        "Use the object's `to_dict()` method instead of dataclass's asdict() function. If absolutely necessary, asdict() is available as _asdict()."
    )


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def normalize(v):
    length = math.sqrt(dot(v, v))
    if length == 0:
        return [0, 0, 0]
    return [v[i] / length for i in range(3)]


def perpendicular_to(v):
    if v[0] == 0 and v[1] == 0:
        return [1, 0, 0]
    return [-v[1], v[0], 0]


def rodrigues(v, axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    return [
        v[i] * c + cross(axis, v)[i] * s + axis[i] * dot(axis, v) * (1 - c)
        for i in range(3)
    ]


def rotate_vector_from_to(v, n1, n2):
    n1 = normalize(n1)
    n2 = normalize(n2)

    if math.isclose(dot(n1, n2), 1.0):
        return v
    if math.isclose(dot(n1, n2), -1.0):
        perp = perpendicular_to(n1)
        return rodrigues(v, perp, math.pi)

    axis = normalize(cross(n1, n2))
    angle = math.acos(dot(n1, n2))
    return rodrigues(v, axis, angle)


def _is_inside(self, p1, p2, q):
    R = (p2[0] - p1[0]) * (q[1] - p1[1]) - (p2[1] - p1[1]) * (q[0] - p1[0])
    if R <= 0:
        return True
    else:
        return False


def _compute_intersection(self, p1, p2, p3, p4):
    if p2[0] - p1[0] == 0:
        x = p1[0]
        m2 = (p4[1] - p3[1]) / (p4[0] - p3[0])
        b2 = p3[1] - m2 * p3[0]
        y = m2 * x + b2
    elif p4[0] - p3[0] == 0:
        x = p3[0]
        m1 = (p2[1] - p1[1]) / (p2[0] - p1[0])
        b1 = p1[1] - m1 * p1[0]
        y = m1 * x + b1
    else:
        m1 = (p2[1] - p1[1]) / (p2[0] - p1[0])
        b1 = p1[1] - m1 * p1[0]
        m2 = (p4[1] - p3[1]) / (p4[0] - p3[0])
        b2 = p3[1] - m2 * p3[0]
        x = (b2 - b1) / (m1 - m2)
        y = m1 * x + b1

    return (x, y)


def clip_polygon(target, clipper):
    # sutherland-hodgman
    final_polygon = target.copy()
    for i in range(len(clipper)):
        input_polygon = final_polygon.copy()
        final_polygon = []
        p1 = clipper[i]
        p2 = clipper[(i + 1) % len(clipper)]
        for j in range(len(input_polygon)):
            q1 = input_polygon[j]
            q2 = input_polygon[(j + 1) % len(input_polygon)]
            if _is_inside(p1, p2, q2):
                if not _is_inside(p1, p2, q1):
                    intersection_point = _compute_intersection(p1, p2, q1, q2)
                    final_polygon.append(intersection_point)
                final_polygon.append(q2)
            elif _is_inside(p1, p2, q1):
                intersection_point = _compute_intersection(p1, p2, q1, q2)
                final_polygon.append(intersection_point)
    return final_polygon


def triangulate_face(face):
    triangles = []
    for i in range(1, len(face) - 1):
        triangles.append((face[0], face[i], face[i + 1]))
    return triangles


def ray_triangle_intersection(origin, direction, triangle):
    v0, v1, v2 = triangle
    edge1 = [v1[i] - v0[i] for i in range(3)]
    edge2 = [v2[i] - v0[i] for i in range(3)]
    h = cross(direction, edge2)
    a = dot(edge1, h)
    if abs(a) < 1e-6:
        return False, None
    f = 1.0 / a
    s = [origin[i] - v0[i] for i in range(3)]
    u = f * dot(s, h)
    if u < 0.0 or u > 1.0:
        return False, None
    q = cross(s, edge1)
    v = f * dot(direction, q)
    if v < 0.0 or u + v > 1.0:
        return False, None
    t = f * dot(edge2, q)
    if t > 1e-6:
        return True, (t, (1 - u - v, u, v))
    return False, None


@dataclass
class Object3D:
    name: str
    fill: bool
    outline: str
    vertexes: list[list[float]]
    faces: list[tuple[list[int], str]]

    def to_dict(self):
        return _asdict(self)


@dataclass
class Plane3D:
    name: str
    fill: bool
    outline: str
    vertexes: list[list[float]]
    fill_color: tuple[float, float, float] = None

    def __post_init__(self):
        if len(self.vertexes) < 3:
            raise ValueError("A plane must have at least 3 vertexes.")

        if len(self.vertexes) > 3:
            self._triangles = triangulate_face(self.vertexes)
            normals = []
            for triangle in self._triangles:
                v0, v1, v2 = triangle
                edge1 = [v1[i] - v0[i] for i in range(3)]
                edge2 = [v2[i] - v0[i] for i in range(3)]
                normal = cross(edge1, edge2)
                length = math.sqrt(dot(normal, normal))
                if length > 0:
                    normal = [n / length for n in normal]
                normals.append(normal)

            one_over = [normals[(i + 1) % len(normals)] for i in range(len(normals))]
            if any(map(lambda a, b: cross(a, b) != [0, 0, 0], *zip(normals, one_over))):
                raise ValueError("The vertexes of the plane must be coplanar.")

    def to_dict(self):
        d = _asdict(self)
        d["faces"] = [([i for i in range(len(self.vertexes))], None)]
        return d


@dataclass
class DebugPoint3D:
    position: list[float]

    def __post_init__(self):
        vert = (
            [0.5, 0.5, -0.5],
            [0.5, -0.5, -0.5],
            [0.5, 0.5, 0.5],
            [0.5, -0.5, 0.5],
            [-0.5, 0.5, -0.5],
            [-0.5, -0.5, -0.5],
            [-0.5, 0.5, 0.5],
            [-0.5, -0.5, 0.5],
        )
        faces = [
            ([0, 4, 6, 2], "Material.001"),
            ([5, 4, 0, 1], "Material.002"),
            ([7, 6, 4, 5], "Material.003"),
            ([3, 2, 6, 7], "Material.004"),
            ([1, 0, 2, 3], "Material.005"),
            ([5, 1, 3, 7], "Material.006"),
        ]
        vert = [
            [v[0] + self.position[0], v[1] + self.position[1], v[2] + self.position[2]]
            for v in vert
        ]
        faces = [(face[::-1], mtl) for face, mtl in faces]
        self.point = Object3D(
            name=id(self),
            fill=True,
            outline=None,
            vertexes=vert,
            faces=faces,
        )

    def to_dict(self):
        return self.point.to_dict()


@dataclass
class PortalCouple:
    portal_a: Plane3D
    portal_b: Plane3D

    def __post_init__(self):
        triangle_a = self.portal_a._triangles[0]
        triangle_b = self.portal_b._triangles[0]
        self.edge_a1 = [triangle_a[1][i] - triangle_a[0][i] for i in range(3)]
        self.edge_a2 = [triangle_a[2][i] - triangle_a[0][i] for i in range(3)]
        self.edge_b1 = [triangle_b[1][i] - triangle_b[0][i] for i in range(3)]
        self.edge_b2 = [triangle_b[2][i] - triangle_b[0][i] for i in range(3)]
        length_a1 = math.sqrt(dot(self.edge_a1, self.edge_a1))
        length_a2 = math.sqrt(dot(self.edge_a2, self.edge_a2))
        length_b1 = math.sqrt(dot(self.edge_b1, self.edge_b1))
        length_b2 = math.sqrt(dot(self.edge_b2, self.edge_b2))
        if not (
            math.isclose(length_a1, length_b1) and math.isclose(length_a2, length_b2)
        ):
            raise ValueError("The two portals must be congruent.")

        self.portal_a_normal = cross(self.edge_a1, self.edge_a2)
        self.portal_b_normal = cross(self.edge_b1, self.edge_b2)
        self.portal_a_orig = [
            sum(v[i] for v in self.portal_a.vertexes) / len(self.portal_a.vertexes)
            for i in range(3)
        ]
        self.portal_b_orig = [
            sum(v[i] for v in self.portal_b.vertexes) / len(self.portal_b.vertexes)
            for i in range(3)
        ]

    def translate_point_through_both(self, point):
        local_a = [point[i] - self.portal_a_orig[i] for i in range(3)]
        rotated_a = rotate_vector_from_to(
            local_a, self.portal_a_normal, self.portal_b_normal
        )

        local_b = [point[i] - self.portal_b_orig[i] for i in range(3)]
        rotated_b = rotate_vector_from_to(
            local_b, self.portal_b_normal, self.portal_a_normal
        )

        return (
            [rotated_a[i] + self.portal_b_orig[i] for i in range(3)],
            [rotated_b[i] + self.portal_a_orig[i] for i in range(3)],
        )


class Camera:
    def __init__(self, position, rotation):
        self.position = position
        self.rotation = rotation
        self.velocity = [0, 0, 0]

        self.forward, self.right, self.up = self.get_axis(rotation)

        self.last_mouse_x, self.last_mouse_y = mouse.get_position()

    @staticmethod
    def get_axis(rotation):
        sinrot_x = sin(rotation[1])
        sinrot_y = sin(rotation[0])
        cosrot_x = cos(rotation[1])
        cosrot_y = cos(rotation[0])

        forward = (
            sinrot_x * cosrot_y,
            cosrot_x * cosrot_y,
            sinrot_y,
        )
        right = (cosrot_x, -sinrot_x, 0)
        up = (
            sinrot_x * sinrot_y,
            cosrot_x * sinrot_y,
            -cosrot_y,
        )

        return forward, right, up

    def update(self):
        mouse_x, mouse_y = mouse.get_position()
        self.rotation[0] += (mouse_y - self.last_mouse_y) * 0.01
        self.rotation[1] += (mouse_x - self.last_mouse_x) * 0.01
        self.last_mouse_x, self.last_mouse_y = mouse.get_position()

        self.forward, self.right, self.up = self.get_axis(self.rotation)

        # calculate movement
        kb_camera_movement = [
            keyboard.is_pressed("d") - keyboard.is_pressed("a"),
            keyboard.is_pressed("w") - keyboard.is_pressed("s"),
            keyboard.is_pressed("ctrl") - keyboard.is_pressed("space"),
        ]

        for i in range(3):
            self.velocity[i] += kb_camera_movement[i] * 0.42
            self.velocity[i] *= 0.85

        # move + strafe
        sinrot_x = sin(self.rotation[1])
        cosrot_x = cos(self.rotation[1])
        self.position[0] += sinrot_x * self.velocity[1] + cosrot_x * self.velocity[0]
        self.position[1] += cosrot_x * self.velocity[1] - sinrot_x * self.velocity[0]

        self.position[2] += self.velocity[2]

    def transform_point(self, point):
        point_x, point_y, point_z = point
        cam_x, cam_y, cam_z = self.position
        ox = point_x - cam_x
        oy = point_y - cam_y
        oz = point_z - cam_z

        cx = ox * self.right[0] + oy * self.right[1] + oz * self.right[2]
        cy = ox * self.up[0] + oy * self.up[1] + oz * self.up[2]
        cz = ox * self.forward[0] + oy * self.forward[1] + oz * self.forward[2]

        return (cx, cy, cz)


main_camera = Camera(position=[5, -50, 0], rotation=[0, 0])

camera_position = [5, -50, 0]  # x left-right, y forwards-backwards, z up-down,
camera_rotation = [0, 0]  # pitch yaw
camera_velocity = [0, 0, 0]

last_mouse_x, last_mouse_y = mouse.get_position()

Cube = Object3D(
    name="Cube",
    fill=True,
    outline=None,
    vertexes=[
        [10, 10, -10],
        [10, -10, -10],
        [10, 10, 10],
        [10, -10, 10],
        [-10, 10, -10],
        [-10, -10, -10],
        [-10, 10, 10],
        [-10, -10, 10],
    ],
    faces=[
        ([0, 4, 6, 2], "Material.001"),
        ([5, 4, 0, 1], "Material.002"),
        ([7, 6, 4, 5], "Material.003"),
        ([3, 2, 6, 7], "Material.004"),
        ([1, 0, 2, 3], "Material.005"),
        ([5, 1, 3, 7], "Material.006"),
    ],
)
Portal1A = Plane3D(
    name="Portal 1A",
    fill=False,
    outline="red",
    vertexes=[
        [-20, 20, 20],
        [20, 20, 20],
        [20, -20, 20],
        [-20, -20, 20],
    ][::-1],
)
Portal1B = Plane3D(
    name="Portal 1B",
    fill=False,
    outline="blue",
    vertexes=[
        [-20, 20, 20],
        [20, 20, 20],
        [20, -20, 20],
        [-20, -20, 20],
    ],
)
Portal1 = PortalCouple(portal_a=Portal1A, portal_b=Portal1B)

scene = [
    Cube.to_dict(),
    Portal1A.to_dict(),
    Portal1B.to_dict(),
    DebugPoint3D(position=[0, 0, 20]).to_dict(),
]
scene_colors = {
    "Material.001": (1, 0, 0),
    "Material.002": (0, 1, 0),
    "Material.003": (0, 0, 1),
    "Material.004": (1, 1, 0),
    "Material.005": (1, 0, 1),
    "Material.006": (0, 1, 1),
}
turtle.bgcolor("grey")
turtle.penup()
turtle.hideturtle()
turtle.speed(0)
turtle.tracer(0)
turtle.pensize(1)

while True:
    start_time = time.monotonic()
    turtle.clear()
    main_camera.update()

    # transform and collect every visible face before drawing any of them.
    faces_to_draw = []
    for shape in scene:
        transformed_vertexes = [[] * 3 for _ in range(len(shape["vertexes"]))]
        for i, vertex in enumerate(shape["vertexes"]):
            transformed_vertexes[i] = main_camera.transform_point(vertex)

        for i, face in enumerate(shape["faces"]):
            vertex_indexes, mtl = face
            face_tv = [transformed_vertexes[i] for i in vertex_indexes]

            projected = []
            skip = False
            for v in face_tv:
                if v[2] <= 0:
                    skip = True
                    break
                projected.append((v[0] / v[2], v[1] / v[2]))
            if skip:
                continue

            ax, ay = projected[0]
            bx, by = projected[1]
            cx, cy = projected[2]
            e1x, e1y = bx - ax, by - ay
            e2x, e2y = cx - ax, cy - ay
            if e1x * e2y - e1y * e2x >= 0:
                continue

            cx_avg = sum(v[0] for v in face_tv) / len(vertex_indexes)
            cy_avg = sum(v[1] for v in face_tv) / len(vertex_indexes)
            cz_avg = sum(v[2] for v in face_tv) / len(vertex_indexes)
            distance = cx_avg**2 + cy_avg**2 + cz_avg**2
            faces_to_draw.append((face_tv, mtl, distance, shape))

    faces_to_draw.sort(key=itemgetter(2), reverse=True)

    for vertexes, mtl, _, shape in faces_to_draw:
        projected_points = []
        for transformed in vertexes:
            cz = transformed[2]
            if cz <= 0:
                break
            screen_x = (transformed[0] / cz) * 300
            screen_y = (transformed[1] / cz) * 300
            projected_points.append((screen_x, screen_y))
        else:
            fill_color = scene_colors.get(mtl, (1, 1, 1))
            outline_color = shape["outline"]
            turtle.penup()
            turtle.goto(projected_points[-1])
            if shape["fill"]:
                turtle.fillcolor(fill_color)
                turtle.pencolor(fill_color if outline_color is None else outline_color)
                turtle.begin_fill()
            elif outline_color is not None:
                turtle.pencolor(outline_color)

            turtle.pendown()
            for p in projected_points:
                turtle.goto(p)
            turtle.goto(projected_points[0])

            if shape["fill"]:
                turtle.end_fill()
            turtle.penup()

    turtle.update()

    while (time.monotonic() - start_time) <= (1 / 60):
        pass
