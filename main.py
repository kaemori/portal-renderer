import math
import keyboard
import mouse

from dataclasses import dataclass, asdict as _asdict
from typing import NamedTuple, Optional, Union

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

Color = Union[tuple[float, float, float], str]

BACKGROUND_COLOR: Color = "grey"
PORTAL_BACKSIDE_OUTLINE: Color = "darkgrey"
SCREEN_SCALE = 200
_actual_recurse = 2
MAX_PORTAL_RECURSION = _actual_recurse


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
        perp = normalize(perpendicular_to(n1))
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


def clip_face_near(face_tv, near):
    clipped = []
    n = len(face_tv)
    for i in range(n):
        a = face_tv[i]
        b = face_tv[(i + 1) % n]
        a_in = a[2] >= near
        b_in = b[2] >= near
        if a_in:
            clipped.append(a)
        if a_in != b_in:
            t = (near - a[2]) / (b[2] - a[2])
            clipped.append(tuple(a[k] + t * (b[k] - a[k]) for k in range(3)))
    return clipped


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


def line_segment_intersects_single_portal(p1, p2, portal, positive_only=False):
    direction = normalize([p2[i] - p1[i] for i in range(3)])
    if positive_only and dot(direction, portal._normal) >= 0:
        return False
    distance = math.sqrt(sum((p2[i] - p1[i]) ** 2 for i in range(3)))
    for triangle in portal._triangles:
        intersects, n = ray_triangle_intersection(p1, direction, triangle)
        if intersects and 0 <= n[0] <= distance:
            return True
    return False


# object types
@dataclass
class Object3D:
    name: str
    outline: Optional[Color]
    vertexes: list[list[float]]
    faces: list[tuple[list[int], Optional[Color]]]

    def to_dict(self):
        d = _asdict(self)
        d["type"] = "Object3D"
        return d


@dataclass
class Plane3D:
    name: str
    outline: Optional[Color]
    vertexes: list[list[float]]
    fill_color: Optional[Color] = None

    def __post_init__(self):
        if len(self.vertexes) < 3:
            raise ValueError("A plane must have at least 3 vertexes.")

        if len(self.vertexes) >= 3:
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

            self._normal = normals[0]

    def to_dict(self):
        d = _asdict(self)
        d["faces"] = [(list(range(len(self.vertexes))), self.fill_color)]
        d["type"] = "Plane3D"
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
        self._same_location = set(map(tuple, self.portal_a.vertexes)) == set(
            map(tuple, self.portal_b.vertexes)
        )

    def translate_point_through_both(self, point):
        local_a = [point[i] - self.portal_a_orig[i] for i in range(3)]
        rotated_a = rodrigues(local_a, normalize(self.portal_b_normal), math.pi)

        local_b = [point[i] - self.portal_b_orig[i] for i in range(3)]
        rotated_b = rodrigues(local_b, normalize(self.portal_a_normal), math.pi)

        return (
            [rotated_a[i] + self.portal_b_orig[i] for i in range(3)],
            [rotated_b[i] + self.portal_a_orig[i] for i in range(3)],
        )

    def teleport_point(self, point, through_a):
        if through_a:
            src_o, src_n = self.portal_a_orig, self.portal_a._normal
            dst_o, dst_n = self.portal_b_orig, self.portal_b._normal
        else:
            src_o, src_n = self.portal_b_orig, self.portal_b._normal
            dst_o, dst_n = self.portal_a_orig, self.portal_a._normal

        local = [point[i] - src_o[i] for i in range(3)]
        rotated = rotate_vector_from_to(local, src_n, [-c for c in dst_n])
        return [rotated[i] + dst_o[i] for i in range(3)]

    def add_object_to_portal(self, obj: Object3D):
        obj_portal_a_name = self.name + "_" + obj.name + "_portal_a"
        obj_portal_b_name = self.name + "_" + obj.name + "_portal_b"
        target_obj = next(
            (
                pobj
                for pobj in self.object_registry
                if pobj.portal_a.name == obj_portal_a_name
                or pobj.portal_b.name == obj_portal_b_name
            ),
            None,
        )
        if target_obj is not None:
            self.object_registry.remove(target_obj)

        new_vertexes_a = []
        new_vertexes_b = []
        for vertex in obj.vertexes:
            new_vertex_a, new_vertex_b = self.translate_point_through_both(vertex)
            new_vertexes_a.append(new_vertex_a)
            new_vertexes_b.append(new_vertex_b)

        pobject = _PortalObjects(
            portal_a=Object3D(
                name=obj_portal_a_name,
                outline=obj.outline,
                vertexes=new_vertexes_a,
                faces=obj.faces,
            ),
            portal_b=Object3D(
                name=obj_portal_b_name,
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
        d["_same_location"] = self._same_location
        return d


@dataclass
class _PortalObjects:
    portal_a: Object3D
    portal_b: Object3D

    def to_dict(self):
        d = _asdict(self)
        d["type"] = "PortalObjects"
        return d


# draw definitions
@dataclass
class _DrawFace:
    points: list
    fill: Optional[Color]
    outline: Optional[Color]
    distance: float


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
    source_normal = source_portal["normal"]
    destination_normal = [-c for c in destination_portal["normal"]]

    def transform_vector(vector):
        return rotate_vector_from_to(vector, source_normal, destination_normal)

    local_position = [camera.position[i] - source_portal["origin"][i] for i in range(3)]
    rotated = transform_vector(local_position)

    virtual_camera = Camera(
        [rotated[i] + destination_portal["origin"][i] for i in range(3)],
        list(camera.rotation),
    )
    virtual_camera.near = camera.near
    virtual_camera.forward = transform_vector(list(camera.forward))
    virtual_camera.right = transform_vector(list(camera.right))
    virtual_camera.up = transform_vector(list(camera.up))
    return virtual_camera


def _project_face(camera, vertexes, indexes, clip=None):
    face_tv = [camera.transform_point(vertexes[i]) for i in indexes]
    if len(face_tv) < 3:
        return None

    v0, v1, v2 = face_tv[:3]
    e1 = [v1[i] - v0[i] for i in range(3)]
    e2 = [v2[i] - v0[i] for i in range(3)]
    if dot(cross(e1, e2), v0) >= 0:
        return None

    face_tv = clip_face_near(face_tv, camera.near)
    if len(face_tv) < 3:
        return None

    projected = [(x / z, y / z) for x, y, z in face_tv]
    if clip is not None:
        projected = clip_polygon(projected, clip)
    if not projected:
        return None

    center = [sum(v[i] for v in face_tv) / len(face_tv) for i in range(3)]
    return projected, math.sqrt(sum(c**2 for c in center))


def _project_portal(camera, portal, allow_back):
    vertexes = portal["vertexes"]
    indexes = range(len(vertexes))

    front = _project_face(camera, vertexes, indexes)
    if front is not None:
        return front[0], front[1], True

    if not allow_back:
        return None

    back = _project_face(camera, vertexes[::-1], indexes)
    if back is None:
        return None
    return back[0][::-1], back[1], False


def _mesh_faces(camera, shape, clip, distance_offset):
    for indexes, fill in shape["faces"]:
        projected = _project_face(camera, shape["vertexes"], indexes, clip)
        if projected is not None:
            points, distance = projected
            yield _DrawFace(points, fill, shape["outline"], distance_offset + distance)


def _portal_faces(camera, couple, clip, distance_offset, recursion_depth=0):
    faces = []
    visible_portals = []

    for source_key, destination_key in (
        ("portal_a", "portal_b"),
        ("portal_b", "portal_a"),
    ):
        source, destination = couple[source_key], couple[destination_key]
        projected = _project_portal(
            camera, source, allow_back=not couple["_same_location"]
        )
        if projected is None:
            continue

        bounds, distance, is_front = projected
        if clip is not None:
            bounds = clip_polygon(bounds, clip)
        if not bounds:
            continue

        if is_front:
            faces.append(
                _DrawFace(bounds, None, source["outline"], distance_offset + distance)
            )
            visible_portals.append((source, destination, bounds, distance))
        else:
            faces.append(
                _DrawFace(
                    bounds,
                    BACKGROUND_COLOR if recursion_depth == 0 else None,
                    None,
                    distance_offset + distance,
                )
            )

    return faces, visible_portals


def _render_scene(camera, recursion_depth, clip=None, distance_offset=0.0):
    faces = []
    visible_portals = []

    for shape in scene:
        if shape["type"] in ("Object3D", "Plane3D"):
            faces.extend(_mesh_faces(camera, shape, clip, distance_offset))
        elif shape["type"] == "PortalCouple":
            portal_faces, portals_seen = _portal_faces(
                camera, shape, clip, distance_offset, recursion_depth
            )
            faces.extend(portal_faces)
            visible_portals.extend(portals_seen)

    if recursion_depth < MAX_PORTAL_RECURSION:
        for source, destination, bounds, distance in visible_portals:
            virtual_camera = _transform_camera_through_portal(
                camera, _portal_data(source), _portal_data(destination)
            )
            faces.extend(
                _render_scene(
                    virtual_camera,
                    recursion_depth + 1,
                    bounds,
                    distance_offset + distance,
                )
            )
    return faces


def _draw_face(face, window_bounds):
    screen_points = [(x * SCREEN_SCALE, y * SCREEN_SCALE) for x, y in face.points]
    screen_points = clip_polygon(screen_points, window_bounds)
    if not screen_points:
        return

    turtle.penup()
    turtle.goto(screen_points[-1])

    if face.fill is not None:
        turtle.fillcolor(face.fill)
        turtle.pencolor(face.outline if face.outline is not None else face.fill)
        turtle.begin_fill()
    elif face.outline is not None:
        turtle.pencolor(face.outline)

    turtle.pendown()
    for point in screen_points:
        turtle.goto(point)
    turtle.goto(screen_points[0])

    if face.fill is not None:
        turtle.end_fill()
    turtle.penup()


# camera
class Camera:
    def __init__(self, position, rotation, near=0.1):
        self.position = position
        self.rotation = rotation
        self.near = near
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
        befpos = self.position.copy()
        self.position[0] += sinrot_x * self.velocity[1] + cosrot_x * self.velocity[0]
        self.position[1] += cosrot_x * self.velocity[1] - sinrot_x * self.velocity[0]

        self.position[2] += self.velocity[2]

        if keyboard.is_pressed("r"):
            self.velocity = [0, 0, 0]
        if keyboard.is_pressed("t"):
            self.rotation = [0, 0]
        if keyboard.is_pressed("y"):
            self.position = [round(coord) for coord in self.position]

        return (befpos, self.position)

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


# scene
Cube = Object3D(
    name="Cube",
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
        ([0, 4, 6, 2], (1, 0, 0)),
        ([5, 4, 0, 1], (0, 1, 0)),
        ([7, 6, 4, 5], (0, 0, 1)),
        ([3, 2, 6, 7], (1, 1, 0)),
        ([1, 0, 2, 3], (1, 0, 1)),
        ([5, 1, 3, 7], (0, 1, 1)),
    ],
)

portals = []
_size = 30
_portal_vert = [
    [-_size, _size, _size],
    [_size, _size, _size],
    [_size, -_size, _size],
    [-_size, -_size, _size],
]
_offset = 0
Portal1A = Plane3D(
    name="Portal 1A",
    outline="red",
    vertexes=[[x, y, z - _size * 2 + _offset] for x, y, z in _portal_vert][::-1],
)
Portal1B = Plane3D(
    name="Portal 1B",
    outline="blue",
    vertexes=[[x, y, z + _offset] for x, y, z in _portal_vert],
)
Portal1 = PortalCouple(name="Portal1", portal_a=Portal1A, portal_b=Portal1B)
Portal1.add_object_to_portal(Cube)
portals.append(Portal1)

_portal_vert2 = [i[-1:] + i[:-1] for i in _portal_vert]
Portal2A = Plane3D(
    name="Portal 2A",
    outline="green",
    vertexes=[[x - _size * 2 - _offset, y, z] for x, y, z in _portal_vert2][::-1],
)
Portal2B = Plane3D(
    name="Portal 2B",
    outline="yellow",
    vertexes=[[x + _offset, y, z] for x, y, z in _portal_vert2],
)
Portal2 = PortalCouple(name="Portal2", portal_a=Portal2A, portal_b=Portal2B)
Portal2.add_object_to_portal(Cube)
portals.append(Portal2)

_portal_vert3 = [i[-1:] + i[:-1] for i in _portal_vert2]
Portal3A = Plane3D(
    name="Portal 3A",
    outline="purple",
    vertexes=[[x, y - _size * 2 - _offset, z] for x, y, z in _portal_vert3][::-1],
)
Portal3B = Plane3D(
    name="Portal 3B",
    outline="orange",
    vertexes=[[x, y + _offset, z] for x, y, z in _portal_vert3],
)
Portal3 = PortalCouple(name="Portal3", portal_a=Portal3A, portal_b=Portal3B)
Portal3.add_object_to_portal(Cube)
portals.append(Portal3)

scene = [
    Cube.to_dict(),
    *[portal.to_dict() for portal in portals],
]


# render
MainCamera = Camera(position=[5, -50, 0], rotation=[0, 0])
turtle.bgcolor(BACKGROUND_COLOR)
turtle.penup()
turtle.hideturtle()
turtle.speed(0)
turtle.tracer(0)
turtle.pensize(0)

while True:
    start_time = time.monotonic()
    turtle.penup()
    turtle.clear()
    before_pos, after_pos = MainCamera.update()

    for portal in portals:
        if line_segment_intersects_single_portal(
            before_pos, after_pos, portal.portal_a, positive_only=True
        ):
            MainCamera.position = portal.teleport_point(MainCamera.position, True)
            break
        elif line_segment_intersects_single_portal(
            before_pos, after_pos, portal.portal_b, positive_only=True
        ):
            MainCamera.position = portal.teleport_point(MainCamera.position, False)
            break

    faces_to_draw = _render_scene(MainCamera, 0)
    faces_to_draw.sort(key=lambda face: -face.distance)

    paint_time = time.monotonic()
    window_width, window_height = turtle.window_width(), turtle.window_height()
    window_bounds = [
        (-window_width / 2, -window_height / 2),
        (window_width / 2, -window_height / 2),
        (window_width / 2, window_height / 2),
        (-window_width / 2, window_height / 2),
    ]
    for face in faces_to_draw:
        _draw_face(face, window_bounds)

    turtle.update()
    end_time = time.monotonic()

    while (time.monotonic() - start_time) <= (1 / 60):
        pass

    if keyboard.is_pressed("o"):
        MAX_PORTAL_RECURSION = 10
    else:
        MAX_PORTAL_RECURSION = _actual_recurse
