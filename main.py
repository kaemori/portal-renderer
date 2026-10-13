import math
import keyboard
import mouse

from dataclasses import dataclass, asdict as _asdict

import turtle, time

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


def _is_inside(p1, p2, q):
    R = (p2[0] - p1[0]) * (q[1] - p1[1]) - (p2[1] - p1[1]) * (q[0] - p1[0])
    if R <= 0:
        return True
    else:
        return False


def _compute_intersection(a1, a2, b1, b2):
    a_dx, a_dy = a2[0] - a1[0], a2[1] - a1[1]
    b_dx, b_dy = b2[0] - b1[0], b2[1] - b1[1]
    denominator = a_dx * b_dy - a_dy * b_dx
    if abs(denominator) < 1e-12:
        return b1

    offset_x, offset_y = b1[0] - a1[0], b1[1] - a1[1]
    segment_position = (offset_x * a_dy - offset_y * a_dx) / denominator
    x = b1[0] + segment_position * b_dx
    y = b1[1] + segment_position * b_dy
    extra = tuple(v1 + segment_position * (v2 - v1) for v1, v2 in zip(b1[2:], b2[2:]))
    return (x, y) + extra


def _clean_polygon(polygon):
    cleaned = []
    for point in polygon:
        if (
            not cleaned
            or math.hypot(point[0] - cleaned[-1][0], point[1] - cleaned[-1][1]) > 1e-10
        ):
            cleaned.append(point)

    if (
        len(cleaned) > 1
        and math.hypot(cleaned[0][0] - cleaned[-1][0], cleaned[0][1] - cleaned[-1][1])
        <= 1e-10
    ):
        cleaned.pop()

    if len(cleaned) < 3:
        return []

    area = sum(
        cleaned[i][0] * cleaned[(i + 1) % len(cleaned)][1]
        - cleaned[(i + 1) % len(cleaned)][0] * cleaned[i][1]
        for i in range(len(cleaned))
    )
    return cleaned if abs(area) > 1e-10 else []


def clip_polygon(target, clipper):
    # sutherland-hodgman
    target = _clean_polygon(target)
    clipper = _clean_polygon(clipper)
    if not target or not clipper:
        return []

    clipper = clipper.copy()
    signed_area = sum(
        clipper[i][0] * clipper[(i + 1) % len(clipper)][1]
        - clipper[(i + 1) % len(clipper)][0] * clipper[i][1]
        for i in range(len(clipper))
    )
    if signed_area > 0:
        clipper.reverse()

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
        final_polygon = _clean_polygon(final_polygon)
        if not final_polygon:
            return []
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
        d = _asdict(self)
        d["type"] = "Object3D"
        return d


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
        d["type"] = "Plane3D"
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
        d = self.point.to_dict()
        d["type"] = "DebugPoint3D"
        return d


@dataclass
class PortalCouple:
    name: str
    portal_a: Plane3D
    portal_b: Plane3D

    def __post_init__(self):
        triangle_a = self.portal_a._triangles[0]
        triangle_b = self.portal_b._triangles[0]
        edge_a1 = [triangle_a[1][i] - triangle_a[0][i] for i in range(3)]
        edge_a2 = [triangle_a[2][i] - triangle_a[0][i] for i in range(3)]
        edge_b1 = [triangle_b[1][i] - triangle_b[0][i] for i in range(3)]
        edge_b2 = [triangle_b[2][i] - triangle_b[0][i] for i in range(3)]
        length_a1 = math.sqrt(dot(edge_a1, edge_a1))
        length_a2 = math.sqrt(dot(edge_a2, edge_a2))
        length_b1 = math.sqrt(dot(edge_b1, edge_b1))
        length_b2 = math.sqrt(dot(edge_b2, edge_b2))
        if not (
            math.isclose(length_a1, length_b1) and math.isclose(length_a2, length_b2)
        ):
            raise ValueError("The two portals must be congruent.")

        self.portal_a_triangles = self.portal_a._triangles
        self.portal_b_triangles = self.portal_b._triangles

        self.portal_a_normal = cross(edge_a1, edge_a2)
        self.portal_b_normal = cross(edge_b1, edge_b2)
        self.portal_a_orig = [
            sum(v[i] for v in self.portal_a.vertexes) / len(self.portal_a.vertexes)
            for i in range(3)
        ]
        self.portal_b_orig = [
            sum(v[i] for v in self.portal_b.vertexes) / len(self.portal_b.vertexes)
            for i in range(3)
        ]

        self.object_registry = []

    def translate_point_through_both(self, point):
        local_a = [point[i] - self.portal_a_orig[i] for i in range(3)]
        rotated_a = rodrigues(local_a, normalize(self.portal_b_normal), math.pi)

        local_b = [point[i] - self.portal_b_orig[i] for i in range(3)]
        rotated_b = rodrigues(local_b, normalize(self.portal_a_normal), math.pi)

        return (
            [rotated_a[i] + self.portal_b_orig[i] for i in range(3)],
            [rotated_b[i] + self.portal_a_orig[i] for i in range(3)],
        )

    def add_object_to_portal(self, obj: Object3D):
        new_vertexes_a = []
        new_vertexes_b = []
        for vertex in obj.vertexes:
            new_vertex_a, new_vertex_b = self.translate_point_through_both(vertex)
            new_vertexes_a.append(new_vertex_a)
            new_vertexes_b.append(new_vertex_b)

        pobject = _PortalObjects(
            portal_a=Object3D(
                name=self.name + "_" + obj.name + "_portal_a",
                fill=obj.fill,
                outline=obj.outline,
                vertexes=new_vertexes_a,
                faces=obj.faces,
            ),
            portal_b=Object3D(
                name=self.name + "_" + obj.name + "_portal_b",
                fill=obj.fill,
                outline=obj.outline,
                vertexes=new_vertexes_b,
                faces=obj.faces,
            ),
        )

        self.object_registry.append(pobject)
        return pobject

    def to_dict(self):
        d = _asdict(self)
        d["type"] = "PortalCouple"
        d["object_registry"] = [obj.to_dict() for obj in self.object_registry]
        d["portal_a"]["_triangles"] = self.portal_a_triangles
        d["portal_b"]["_triangles"] = self.portal_b_triangles
        return d


@dataclass
class _PortalObjects:
    portal_a: Object3D
    portal_b: Object3D

    def to_dict(self):
        d = _asdict(self)
        d["type"] = "PortalObjects"
        return d


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
        self.rotation[0] = max(-pi / 2, min(pi / 2, self.rotation[0]))
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

        if keyboard.is_pressed("r"):
            self.velocity = [0, 0, 0]
        if keyboard.is_pressed("t"):
            self.rotation = [0, 0]
        if keyboard.is_pressed("y"):
            self.position = [round(coord) for coord in self.position]

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
_portal_vert = [
    [-40, 40, 40],
    [40, 40, 40],
    [40, -40, 40],
    [-40, -40, 40],
]
Portal1A = Plane3D(
    name="Portal 1A",
    fill=False,
    outline="red",
    vertexes=[[x, y, z - 80] for x, y, z in _portal_vert][::-1],
)
Portal1B = Plane3D(
    name="Portal 1B",
    fill=False,
    outline="blue",
    vertexes=[[x, y, z] for x, y, z in _portal_vert],
)
Portal1 = PortalCouple(name="Portal1", portal_a=Portal1A, portal_b=Portal1B)
Portal1.add_object_to_portal(Cube)

_portal_vert2 = [i[-1:] + i[:-1] for i in _portal_vert]
Portal2A = Plane3D(
    name="Portal 2A",
    fill=False,
    outline="green",
    vertexes=[[x - 80, y, z] for x, y, z in _portal_vert2][::-1],
)
Portal2B = Plane3D(
    name="Portal 2B",
    fill=False,
    outline="yellow",
    vertexes=[[x, y, z] for x, y, z in _portal_vert2],
)
Portal2 = PortalCouple(name="Portal2", portal_a=Portal2A, portal_b=Portal2B)
Portal2.add_object_to_portal(Cube)

_portal_vert3 = [i[-1:] + i[:-1] for i in _portal_vert2]
Portal3A = Plane3D(
    name="Portal 3A",
    fill=False,
    outline="purple",
    vertexes=[[x, y - 80, z] for x, y, z in _portal_vert3][::-1],
)
Portal3B = Plane3D(
    name="Portal 3B",
    fill=False,
    outline="orange",
    vertexes=[[x, y, z] for x, y, z in _portal_vert3],
)
Portal3 = PortalCouple(name="Portal3", portal_a=Portal3A, portal_b=Portal3B)
Portal3.add_object_to_portal(Cube)


scene = [
    Cube.to_dict(),
    Portal1.to_dict(),
    Portal2.to_dict(),
    Portal3.to_dict(),
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
turtle.pensize(0)


def _prepare_visible_face(transformed_vertexes, face, flip_winding=False):
    vertex_indexes, mtl = face
    face_tv = [transformed_vertexes[i] for i in vertex_indexes]
    projected = []
    for vertex in face_tv:
        if vertex[2] <= 0:
            return None
        projected.append((vertex[0] / vertex[2], vertex[1] / vertex[2]))

    ax, ay = projected[0]
    bx, by = projected[1]
    cx, cy = projected[2]
    e1x, e1y = bx - ax, by - ay
    e2x, e2y = cx - ax, cy - ay
    winding = e1x * e2y - e1y * e2x
    if (not flip_winding and winding >= 0) or (flip_winding and winding <= 0):
        return None

    center = [sum(vertex[i] for vertex in face_tv) / len(face_tv) for i in range(3)]
    distance = sum(component**2 for component in center)
    return face_tv, mtl, distance


MAX_PORTAL_RECURSION = 3


def _portal_data(portal):
    vertexes = portal["vertexes"]
    edge_a = [vertexes[1][i] - vertexes[0][i] for i in range(3)]
    edge_b = [vertexes[2][i] - vertexes[0][i] for i in range(3)]
    return {
        "origin": [
            sum(vertex[i] for vertex in vertexes) / len(vertexes) for i in range(3)
        ],
        "normal": cross(edge_a, edge_b),
    }


def _transform_camera_through_portal(camera, source_portal, destination_portal):
    source_normal = normalize(source_portal["normal"])

    def reflect_normal_component(vector):
        normal_component = dot(vector, source_normal)
        return [vector[i] - 2 * normal_component * source_normal[i] for i in range(3)]

    def transform_vector(vector):
        return rotate_vector_from_to(
            reflect_normal_component(vector),
            source_portal["normal"],
            destination_portal["normal"],
        )

    local_position = [camera.position[i] - source_portal["origin"][i] for i in range(3)]
    rotated = transform_vector(local_position)

    virtual_camera = Camera(
        [rotated[i] + destination_portal["origin"][i] for i in range(3)],
        list(camera.rotation),
    )
    virtual_camera.forward = transform_vector(list(camera.forward))
    virtual_camera.right = transform_vector(list(camera.right))
    virtual_camera.up = transform_vector(list(camera.up))
    return virtual_camera


def _project_face(camera, vertexes, face, clip=None, flip_winding=False):
    visible_face = _prepare_visible_face(
        [camera.transform_point(vertex) for vertex in vertexes], face, flip_winding
    )
    if visible_face is None:
        return None
    face_tv, mtl, distance = visible_face
    projected = [(x / z, y / z) for x, y, z in face_tv]
    if clip is not None:
        projected = clip_polygon(projected, clip)
    if not projected:
        return None
    return projected, mtl, distance


def _render_scene(camera, recursion_depth, clip=None, distance_offset=0.0):
    faces = []
    visible_portals = []
    flip_winding = recursion_depth % 2 == 1

    for shape in scene:
        if shape["type"] == "Object3D":
            for face in shape["faces"]:
                rendered = _project_face(
                    camera, shape["vertexes"], face, clip, flip_winding
                )
                if rendered is not None:
                    projected, mtl, distance = rendered
                    faces.append(
                        (
                            projected,
                            mtl,
                            distance_offset + math.sqrt(distance),
                            shape,
                        )
                    )
        elif shape["type"] == "PortalCouple":
            for source_name, destination_name in (
                ("portal_a", "portal_b"),
                ("portal_b", "portal_a"),
            ):
                source = shape[source_name]
                destination = shape[destination_name]
                portal_face = _project_face(
                    camera,
                    source["vertexes"],
                    (range(len(source["vertexes"])), None),
                    flip_winding=flip_winding,
                )
                if portal_face is None:
                    continue
                portal_bounds, _, distance = portal_face
                if clip is not None:
                    portal_bounds = clip_polygon(portal_bounds, clip)
                if portal_bounds:
                    faces.append(
                        (
                            portal_bounds,
                            None,
                            distance_offset + math.sqrt(distance),
                            source,
                        )
                    )
                    visible_portals.append(
                        (source, destination, portal_bounds, math.sqrt(distance))
                    )
        elif shape["type"] == "Plane3D":
            rendered = _project_face(
                camera,
                shape["vertexes"],
                (range(len(shape["vertexes"])), None),
                clip,
                flip_winding,
            )
            if rendered is not None:
                projected, mtl, distance = rendered
                faces.append(
                    (
                        projected,
                        mtl,
                        distance_offset + math.sqrt(distance),
                        shape,
                    )
                )

    if recursion_depth < MAX_PORTAL_RECURSION:
        print(
            f"Recursion depth: {recursion_depth}, visible portals: {len(visible_portals)}"
        )
        for source, destination, portal_bounds, portal_distance in visible_portals:
            virtual_camera = _transform_camera_through_portal(
                camera, _portal_data(source), _portal_data(destination)
            )
            faces.extend(
                _render_scene(
                    virtual_camera,
                    recursion_depth + 1,
                    portal_bounds,
                    distance_offset + portal_distance,
                )
            )
    return faces


while True:
    start_time = time.monotonic()
    turtle.penup()
    turtle.clear()
    main_camera.update()
    faces_to_draw = _render_scene(main_camera, 0)
    faces_to_draw.sort(key=lambda face: -face[2])

    for projected_points, mtl, _, shape in faces_to_draw:
        screen_points = [(x * 300, y * 300) for x, y in projected_points]
        fill_color = scene_colors.get(mtl, (1, 1, 1))
        outline_color = shape["outline"]
        turtle.penup()
        turtle.goto(screen_points[-1])

        if shape["fill"]:
            turtle.fillcolor(fill_color)
            turtle.pencolor(fill_color if outline_color is None else outline_color)
            turtle.begin_fill()
        elif outline_color is not None:
            turtle.pencolor(outline_color)

        turtle.pendown()
        for point in screen_points:
            turtle.goto(point)
        turtle.goto(screen_points[0])

        if shape["fill"]:
            turtle.end_fill()
        turtle.penup()

    turtle.update()
    while (time.monotonic() - start_time) <= (1 / 60):
        pass

    if keyboard.is_pressed("o"):
        MAX_PORTAL_RECURSION = 10
