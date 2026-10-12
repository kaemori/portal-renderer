import math
import keyboard
import mouse

from dataclasses import dataclass, asdict

import turtle, time
from operator import itemgetter

from pprint import pprint

# patches keyboard.is_pressed() to work on linux
check_output = __import__("subprocess", fromlist=["check_output"]).check_output
keyboard._nixkeyboard.ensure_root = lambda: 0
keyboard._nixkeyboard.check_output = lambda cmd, **kwargs: (
    check_output(["dumpkeys", "-C", "/dev/tty1"] + cmd[1:], **kwargs)
    if cmd[0] == "dumpkeys"
    else check_output(cmd, **kwargs)
)

cos = math.cos
sin = math.sin
pi = math.pi


@dataclass
class Object3D:
    name: str
    fill: bool
    outline: str
    vertexes: list[list[float]]
    faces: list[tuple[list[int], str]]


@dataclass
class PortalCouple:
    portal_a: Object3D
    portal_b: Object3D


def transform_point(point, cam_pos, cam_right, cam_up, cam_forward):
    point_x, point_y, point_z = point
    cam_x, cam_y, cam_z = cam_pos
    ox = point_x - cam_x
    oy = point_y - cam_y
    oz = point_z - cam_z

    cam_right_x, cam_right_y, cam_right_z = cam_right
    cam_up_x, cam_up_y, cam_up_z = cam_up
    cam_forward_x, cam_forward_y, cam_forward_z = cam_forward
    cx = ox * cam_right_x + oy * cam_right_y + oz * cam_right_z
    cy = ox * cam_up_x + oy * cam_up_y + oz * cam_up_z
    cz = ox * cam_forward_x + oy * cam_forward_y + oz * cam_forward_z

    return (cx, cy, cz)


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
Portal1A = Object3D(
    name="Portal 1A",
    fill=False,
    outline="black",
    vertexes=[
        [-20, 20, 20],
        [20, 20, 20],
        [20, -20, 20],
        [-20, -20, 20],
    ][::-1],
    faces=[([0, 3, 2, 1], None)],
)
Portal1B = Object3D(
    name="Portal 1B",
    fill=False,
    outline="orange",
    vertexes=[
        [-20, 20, 20],
        [20, 20, 20],
        [20, -20, 20],
        [-20, -20, 20],
    ],
    faces=[([0, 3, 2, 1], None)],
)
Portal1 = PortalCouple(portal_a=Portal1A, portal_b=Portal1B)

scene = [asdict(Cube), asdict(Portal1A), asdict(Portal1B)]
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

while True:
    start_time = time.monotonic()
    turtle.clear()

    # look
    mouse_x, mouse_y = mouse.get_position()
    camera_rotation[0] += (mouse_y - last_mouse_y) * 0.01
    camera_rotation[1] += (mouse_x - last_mouse_x) * 0.01
    last_mouse_x, last_mouse_y = mouse.get_position()

    # calculate camera axis
    sinrot_x = sin(camera_rotation[1])
    sinrot_y = sin(camera_rotation[0])
    cosrot_x = cos(camera_rotation[1])
    cosrot_y = cos(camera_rotation[0])

    camera_forward = (
        sinrot_x * cosrot_y,
        cosrot_x * cosrot_y,
        sinrot_y,
    )
    camera_right = (cosrot_x, -sinrot_x, 0)
    camera_up = (
        sinrot_x * sinrot_y,
        cosrot_x * sinrot_y,
        -cosrot_y,
    )

    # calculate movement
    camera_movement = [
        keyboard.is_pressed("d") - keyboard.is_pressed("a"),
        keyboard.is_pressed("w") - keyboard.is_pressed("s"),
        keyboard.is_pressed("ctrl") - keyboard.is_pressed("space"),
    ]

    for i in range(3):
        camera_velocity[i] += camera_movement[i] * 0.42
        camera_velocity[i] *= 0.85

    # move + strafe
    camera_position[0] += sinrot_x * camera_velocity[1] + cosrot_x * camera_velocity[0]
    camera_position[1] += cosrot_x * camera_velocity[1] - sinrot_x * camera_velocity[0]

    camera_position[2] += camera_velocity[2]

    # Transform and collect every visible face before drawing any of them.
    faces_to_draw = []
    for shape in scene:
        transformed_vertexes = [[] * 3 for _ in range(len(shape["vertexes"]))]
        for i, vertex in enumerate(shape["vertexes"]):
            transformed_vertexes[i] = transform_point(
                vertex, camera_position, camera_right, camera_up, camera_forward
            )

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
