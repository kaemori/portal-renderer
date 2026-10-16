import math
import keyboard
import mouse

from dataclasses import dataclass, asdict as _asdict
from typing import NamedTuple, Optional, Union

import turtle, time

from vectors import *
from polymath import *

# patches keyboard.is_pressed() to work on linux
_check_output = __import__("subprocess", fromlist=["check_output"]).check_output
_kb_overload = lambda cmd, **kwargs: _check_output(
    ["dumpkeys", "-C", "/dev/tty1", *cmd[1:]] if cmd[0] == "dumpkeys" else cmd, **kwargs
)
_nix_kb = getattr(keyboard, "_nixkeyboard", None)
_nix_kb and setattr(_nix_kb, "ensure_root", lambda: 0)
_nix_kb and setattr(_nix_kb, "check_output", _kb_overload)
keyboard.is_pressed("d")  # wake keyboard up


cos = math.cos
sin = math.sin
pi = math.pi

Color = Union[tuple[float, float, float], str]

BACKGROUND_COLOR: Color = "grey"
PORTAL_BACKSIDE_OUTLINE: Color = "darkgrey"
SCREEN_SCALE = 200
CAMERA_FOV_DEGREES = 110
_actual_recurse = 3
_DEBUG_DRAW_OUTLINES = False
MAX_PORTAL_RECURSION = _actual_recurse


# helper maths
def asdict(*args, **kwargs):
    """DO NOT USE DATACLASS ASDICT. INSTEAD, USE THE OBJECT'S `to_dict()` METHOD."""
    raise NotImplementedError(
        "Use the object's `to_dict()` method instead of dataclass's asdict() function. If absolutely necessary, asdict() is available as _asdict()."
    )


def fov_scale(fov_degrees):
    if not 0 < fov_degrees < 180:
        raise ValueError("FOV must be between 0 and 180 degrees.")
    return 1 / math.tan(math.radians(fov_degrees) / 2)


PERSPECTIVE_SCALE = fov_scale(CAMERA_FOV_DEGREES)


# object types
@dataclass
class Object3D:
    name: str
    outline: Optional[Color]
    vertexes: list[Vector3]
    faces: list[tuple[list[int], Optional[Color]]]

    def to_dict(self):
        d = _asdict(self)
        d["type"] = "Object3D"
        return d


@dataclass
class PortalFace(Object3D):
    def __post_init__(self):
        super().__post_init__()
        self._edge1 = self.vertexes[1] - self.vertexes[0]
        self._edge2 = self.vertexes[2] - self.vertexes[0]
        self._length1 = math.sqrt(dot(self._edge1, self._edge1))
        self._length2 = math.sqrt(dot(self._edge2, self._edge2))

    def to_dict(self):
        d = super().to_dict()
        d["_triangles"] = self._triangles
        d["_normal"] = self._normal
        return d


@dataclass
class Plane3D:
    name: str
    outline: Optional[Color]
    vertexes: list[Vector3]
    fill_color: Optional[Color] = None

    def __post_init__(self):
        for vertex in self.vertexes:
            if isinstance(vertex, Vector3):
                break
        else:
            # oh my god im using for else unironically!??!?! first time in my life :shock:
            self.vertexes = [Vector3(v) for v in self.vertexes]

        if len(self.vertexes) < 3:
            raise ValueError("A plane must have at least 3 vertexes.")

        if len(self.vertexes) >= 3:
            self._triangles = triangulate_face(self.vertexes)
            normals = []
            for triangle in self._triangles:
                v0, v1, v2 = triangle
                edge1 = v1 - v0
                edge2 = v2 - v0
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
    portal_a: PortalFace
    portal_b: PortalFace

    def __post_init__(self):
        triangle_a = self.portal_a._triangles[0]
        triangle_b = self.portal_b._triangles[0]
        edge_a1 = triangle_a[1] - triangle_a[0]
        edge_a2 = triangle_a[2] - triangle_a[0]
        edge_b1 = triangle_b[1] - triangle_b[0]
        edge_b2 = triangle_b[2] - triangle_b[0]
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
        self.portal_a_orig = Vector3(
            [
                sum(v[i] for v in self.portal_a.vertexes) / len(self.portal_a.vertexes)
                for i in range(3)
            ]
        )
        self.portal_b_orig = Vector3(
            [
                sum(v[i] for v in self.portal_b.vertexes) / len(self.portal_b.vertexes)
                for i in range(3)
            ]
        )

        self.object_registry = []
        self._same_location = set(map(tuple, self.portal_a.vertexes)) == set(
            map(tuple, self.portal_b.vertexes)
        )

    def translate_point_through_both(self, point):
        local_a = point - self.portal_a_orig
        rotated_a = rodrigues(local_a, normalize(self.portal_b_normal), math.pi)

        local_b = point - self.portal_b_orig
        rotated_b = rodrigues(local_b, normalize(self.portal_a_normal), math.pi)

        return (
            rotated_a + self.portal_b_orig,
            rotated_b + self.portal_a_orig,
        )

    def teleport_point(self, point, through_a):
        if through_a:
            src_o, src_n = self.portal_a_orig, self.portal_a._normal
            dst_o, dst_n = self.portal_b_orig, self.portal_b._normal
        else:
            src_o, src_n = self.portal_b_orig, self.portal_b._normal
            dst_o, dst_n = self.portal_a_orig, self.portal_a._normal

        local = point - src_o
        rotated = rotate_vector_from_to(local, src_n, [-c for c in dst_n])
        return rotated + dst_o

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

        _new_vertexes = [
            self.translate_point_through_both(vertex) for vertex in obj.vertexes
        ]
        new_vertexes_a, new_vertexes_b = [
            [Vector3(n) for n in x] for x in zip(*_new_vertexes[::-1])
        ]

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
    edge_a = vertexes[1] - vertexes[0]
    edge_b = vertexes[2] - vertexes[0]
    return {
        "origin": Vector3(
            [sum(vertex[i] for vertex in vertexes) / len(vertexes) for i in range(3)]
        ),
        "normal": cross(edge_a, edge_b),
    }


def _transform_camera_through_portal(camera, source_portal, destination_portal):
    source_normal = source_portal["normal"]
    destination_normal = [-c for c in destination_portal["normal"]]

    def transform_vector(vector):
        return rotate_vector_from_to(vector, source_normal, destination_normal)

    local_position = camera.pos - source_portal["origin"]
    rotated = transform_vector(local_position)

    virtual_camera = Camera(
        destination_portal["origin"] + rotated,
        camera.rot,
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
    e1 = v1 - v0
    e2 = v2 - v0
    if dot(cross(e1, e2), v0) >= 0:
        return None

    face_tv = clip_face_near(face_tv, camera.near)
    if len(face_tv) < 3:
        return None

    projected = [
        (x * PERSPECTIVE_SCALE / z, y * PERSPECTIVE_SCALE / z) for x, y, z in face_tv
    ]
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
                _DrawFace(
                    bounds,
                    None,
                    source["outline"] if _DEBUG_DRAW_OUTLINES else None,
                    distance_offset + distance,
                )
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


_color_cache = {}
_turtle_screen = turtle.Screen()
_canvas = turtle.getcanvas()


def _get_color_name(name):
    cached = _color_cache.get(name)
    if cached is None:
        cached = [i / 257 / 256 for i in _canvas.winfo_rgb(name)]
        _color_cache[name] = cached
    return cached


def _color_to_hex(color):
    if color is None:
        return ""
    if isinstance(color, str):
        color = _canvas.winfo_rgb(color)
        return "#" + "".join(f"{channel // 257:02x}" for channel in color)
    return "#" + "".join(
        f"{round(max(0, min(1, channel)) * 255):02x}" for channel in color
    )


def _apply_dist_lighting(faces):
    for face in faces:
        if face.fill is not None:
            raw = 1 / (1 + face.distance * 0.1) - face.distance * 0.0001
            factor = max(0, min(1, raw))
            blend = 1 - factor
            bgrgb = _get_color_name(BACKGROUND_COLOR)

            if isinstance(face.fill, str):
                rgb = _get_color_name(face.fill)
            else:
                rgb = list(face.fill)

            face.fill = tuple(c * factor + d * blend for c, d in zip(rgb, bgrgb))
            # face.fill = tuple(d * blend for c, d in zip(rgb, bgrgb))


def _draw_face(face, window_bounds):
    if face.fill is None and face.outline is None:
        return

    screen_points = [(x * SCREEN_SCALE, -y * SCREEN_SCALE) for x, y in face.points]
    screen_points = clip_polygon(screen_points, window_bounds)
    if not screen_points:
        return

    flat_coords = [coordinate for point in screen_points for coordinate in point]
    _canvas.create_polygon(
        *flat_coords,
        fill=_color_to_hex(face.fill),
        outline=_color_to_hex(face.outline),
    )


# camera
class Camera:
    def __init__(self, position: Vector3, rotation: Rot, near=0.1):
        self.pos = position
        self.rot = rotation
        self.near = near
        self.velocity = Vector3(0, 0, 0)

        self.forward, self.right, self.up = self.get_axis()
        self.last_mouse_x, self.last_mouse_y = mouse.get_position()

    def get_axis(self):
        sinrot_x, sinrot_y = sin(self.rot.yaw), sin(self.rot.pitch)
        cosrot_x, cosrot_y = cos(self.rot.yaw), cos(self.rot.pitch)

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
        self.rot.pitch += (mouse_y - self.last_mouse_y) * 0.01
        self.rot.yaw += (mouse_x - self.last_mouse_x) * 0.01
        self.rot.pitch = max(-pi / 2, min(pi / 2, self.rot.pitch))
        self.last_mouse_x, self.last_mouse_y = mouse.get_position()

        self.forward, self.right, self.up = self.get_axis()

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
        sinrot_x = sin(self.rot.yaw)
        cosrot_x = cos(self.rot.yaw)
        befpos = self.pos.copy()
        self.pos.x += sinrot_x * self.velocity[1] + cosrot_x * self.velocity[0]
        self.pos.y += cosrot_x * self.velocity[1] - sinrot_x * self.velocity[0]
        self.pos.z += self.velocity[2]

        if keyboard.is_pressed("r"):
            self.velocity = zero3()
        if keyboard.is_pressed("t"):
            self.rotation = zero2()
        if keyboard.is_pressed("y"):
            self.pos = Vector3(round(coord) for coord in self.pos)

        return (befpos, self.pos)

    def transform_point(self, point):
        point_x, point_y, point_z = point
        cam_x, cam_y, cam_z = self.pos
        ox = point_x - cam_x
        oy = point_y - cam_y
        oz = point_z - cam_z

        cx = ox * self.right[0] + oy * self.right[1] + oz * self.right[2]
        cy = ox * self.up[0] + oy * self.up[1] + oz * self.up[2]
        cz = ox * self.forward[0] + oy * self.forward[1] + oz * self.forward[2]

        return Vector3(cx, cy, cz)


# scene
import cProfile, pstats

with cProfile.Profile() as pr:
    MainCamera = Camera(position=Vector3(5, -50, 0), rotation=Rot(0, 0))
    turtle.setundobuffer(None)
    turtle.bgcolor(BACKGROUND_COLOR)
    turtle.penup()
    turtle.hideturtle()
    turtle.speed(0)
    turtle.tracer(0)
    turtle.pensize(0)

    _cubeverts = [
        Vector3(face)
        for face in [
            [10, 10, -10],
            [10, -10, -10],
            [10, 10, 10],
            [10, -10, 10],
            [-10, 10, -10],
            [-10, -10, -10],
            [-10, 10, 10],
            [-10, -10, 10],
        ]
    ]
    Cube = Object3D(
        name="Cube",
        outline=None,
        vertexes=_cubeverts,
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
        Vector3(-_size, _size, _size),
        Vector3(_size, _size, _size),
        Vector3(_size, -_size, _size),
        Vector3(-_size, -_size, _size),
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
stats = pstats.Stats(pr)
stats.dump_stats("init.prof")


def main():
    paint_time = 0
    end_time = 0
    frame_stats = "FPS: -- | Render: -- | Draw: --"
    last_ten_frames = []

    while True:
        start_time = time.monotonic()
        turtle.penup()
        turtle.clear()
        _canvas.delete("all")

        window_width, window_height = turtle.window_width(), turtle.window_height()
        window_bounds = [
            (-window_width / 2, -window_height / 2),
            (window_width / 2, -window_height / 2),
            (window_width / 2, window_height / 2),
            (-window_width / 2, window_height / 2),
        ]

        before_pos, after_pos = MainCamera.update()

        for portal in portals:
            if line_segment_intersects_single_portal(
                before_pos, after_pos, portal.portal_a, positive_only=True
            ):
                MainCamera.pos = portal.teleport_point(MainCamera.pos, True)
            if line_segment_intersects_single_portal(
                before_pos, after_pos, portal.portal_b, positive_only=True
            ):
                MainCamera.pos = portal.teleport_point(MainCamera.pos, False)

        faces_to_draw = _render_scene(MainCamera, 0)
        faces_to_draw.sort(key=lambda face: -face.distance)
        _apply_dist_lighting(faces_to_draw)

        paint_time = time.monotonic()
        for face in faces_to_draw:
            _draw_face(face, window_bounds)

        turtle.penup()
        turtle.color("red")
        turtle.goto(-window_width / 2 + 10, window_height / 2 - 20)
        turtle.write(frame_stats, font=("Arial", 12, "normal"))

        turtle.update()
        end_time = time.monotonic()

        # remaining = (1 / 20) - (time.monotonic() - start_time)
        # if remaining > 0:
        #     time.sleep(remaining)

        true_time = time.monotonic()

        frame_duration = end_time - start_time
        last_ten_frames.append(frame_duration)
        last_ten_frames = last_ten_frames[-10:]
        frame_stats = (
            f"FPS: {1 / frame_duration:.2f} (AVG: {10 / sum(last_ten_frames):.2f} / TRUE: {1/(true_time-start_time):.2f}) | "
            f"Render: {paint_time - start_time:.4f}s | "
            f"Draw: {end_time - paint_time:.4f}s"
        )

        # if keyboard.is_pressed("o"):
        #     MAX_PORTAL_RECURSION = 5
        # else:
        #     MAX_PORTAL_RECURSION = _actual_recurse

        # break


# render
# cProfile.run("main()", "main.prof")
main()
