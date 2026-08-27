import struct
import math

from inliner import inline

# nts: move into functions (no glb. lookup)
pack = struct.pack
unpack = struct.unpack
cos = math.cos
sin = math.sin
pi = math.pi

SCALE = 100


# note to self: all vectors have a maximum of ~655.35, 2dp fixed point
@inline
def Vector3(x, y, z):
    return pack("hhh", int(x * SCALE), int(y * SCALE), int(z * SCALE))


@inline
def v3_unpack(v):
    x, y, z = unpack("hhh", v)
    return x / SCALE, y / SCALE, z / SCALE


@inline
def Vector2(x, y):
    return pack("hh", int(x * SCALE), int(y * SCALE))


@inline
def v2_unpack(v):
    x, y = unpack("hh", v)
    return x / SCALE, y / SCALE


camera_position = Vector3(0, -20, 0)
camera_rotation = Vector2(0, 0)  # yaw pitch

cam_x, cam_y, cam_z = v3_unpack(camera_position)
rot_x, rot_y = v2_unpack(camera_rotation)
camera_forward = Vector3(
    sin(rot_x) * cos(rot_y),
    cos(rot_x) * cos(rot_y),
    sin(rot_y),
)
camera_right = Vector3(cos(rot_x), -sin(rot_x), 0)
camera_up = Vector3(
    sin(rot_x) * cos(rot_y - pi / 2),
    cos(rot_x) * cos(rot_y - pi / 2),
    sin(rot_y - pi / 2),
)


def transform_point(point, cam_pos, cam_right, cam_up, cam_forward):
    point_x, point_y, point_z = v3_unpack(point)
    cam_x, cam_y, cam_z = v3_unpack(cam_pos)
    ox = point_x - cam_x
    oy = point_y - cam_y
    oz = point_z - cam_z

    cam_right_x, cam_right_y, cam_right_z = v3_unpack(cam_right)
    cam_up_x, cam_up_y, cam_up_z = v3_unpack(cam_up)
    cam_forward_x, cam_forward_y, cam_forward_z = v3_unpack(cam_forward)
    cx = ox * cam_right_x + oy * cam_right_y + oz * cam_right_z
    cy = ox * cam_up_x + oy * cam_up_y + oz * cam_up_z
    cz = ox * cam_forward_x + oy * cam_forward_y + oz * cam_forward_z

    return (cx, cy, cz)


unit_cube = [
    Vector3(1, 1, 1),
    Vector3(1, 1, 0),
    Vector3(1, 0, 1),
    Vector3(1, 0, 0),
    Vector3(0, 1, 1),
    Vector3(0, 1, 0),
    Vector3(0, 0, 1),
    Vector3(0, 0, 0),
]

import turtle

turtle.hideturtle()
turtle.speed(0)
turtle.tracer(0)


while True:
    turtle.clear()
    cam_x, cam_y, cam_z = v3_unpack(camera_position)
    camera_position = Vector3(cam_x, cam_y + 0.02, cam_z)
    print(cam_x, cam_y, cam_z)
    for p in unit_cube:
        transformed = transform_point(
            p, camera_position, camera_right, camera_up, camera_forward
        )
        cz = transformed[2]
        if cz <= 0:
            continue
        screen_x = (transformed[0] / cz) * 300
        screen_y = (transformed[1] / cz) * 300
        turtle.goto(screen_x, screen_y)
        turtle.dot(5, "red")
    turtle.update()
    # turtle.done()
