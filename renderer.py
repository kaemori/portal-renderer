from math import cos, sin


def project_point(self, point, screen_width=800, screen_height=600, fov=90):
    relative = point - self.pos

    yaw = self.yaw
    pitch = self.pitch

    cos_yaw = cos(yaw)
    sin_yaw = sin(yaw)
    cos_pitch = cos(pitch)
    sin_pitch = sin(pitch)

    xz = Vector3(
        cos_yaw * relative.x + sin_yaw * relative.z,
        relative.y,
        -sin_yaw * relative.x + cos_yaw * relative.z,
    )

    final = Vector3(
        xz.x,
        cos_pitch * xz.y - sin_pitch * xz.z,
        sin_pitch * xz.y + cos_pitch * xz.z,
    )

    if final.z <= 0:
        return None

    aspect_ratio = screen_width / screen_height

    fov_rad = radians(fov)
    f = 1 / tan(fov_rad / 2)

    screen_x = (final.x * f / final.z) * (screen_height / screen_width)
    screen_y = final.y * f / final.z

    screen_x = screen_x * (screen_width / 2) + screen_width / 2
    screen_y = screen_y * (screen_height / 2) + screen_height / 2

    turtle_x = screen_x - screen_width / 2
    turtle_y = screen_y - screen_height / 2

    return (turtle_x, turtle_y)
