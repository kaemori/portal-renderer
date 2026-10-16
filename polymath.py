import math

from vectors import Vector3


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
    return Vector3(
        [
            v[i] * c + cross(axis, v)[i] * s + axis[i] * dot(axis, v) * (1 - c)
            for i in range(3)
        ]
    )


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
    # return polygon
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
