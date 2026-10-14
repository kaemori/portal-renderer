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
    fill=False,
    outline="red",
    vertexes=[[x, y, z - _size * 2 + _offset] for x, y, z in _portal_vert][::-1],
)
Portal1B = Plane3D(
    name="Portal 1B",
    fill=False,
    outline="blue",
    vertexes=[[x, y, z + _offset] for x, y, z in _portal_vert],
)
Portal1 = PortalCouple(name="Portal1", portal_a=Portal1A, portal_b=Portal1B)
Portal1.add_object_to_portal(Cube)

_portal_vert2 = [i[-1:] + i[:-1] for i in _portal_vert]
Portal2A = Plane3D(
    name="Portal 2A",
    fill=False,
    outline="green",
    vertexes=[[x - _size * 2 - _offset, y, z] for x, y, z in _portal_vert2][::-1],
)
Portal2B = Plane3D(
    name="Portal 2B",
    fill=False,
    outline="yellow",
    vertexes=[[x + _offset, y, z] for x, y, z in _portal_vert2],
)
Portal2 = PortalCouple(name="Portal2", portal_a=Portal2A, portal_b=Portal2B)
Portal2.add_object_to_portal(Cube)

_portal_vert3 = [i[-1:] + i[:-1] for i in _portal_vert2]
Portal3A = Plane3D(
    name="Portal 3A",
    fill=False,
    outline="purple",
    vertexes=[[x, y - _size * 2 - _offset, z] for x, y, z in _portal_vert3][::-1],
)
Portal3B = Plane3D(
    name="Portal 3B",
    fill=False,
    outline="orange",
    vertexes=[[x, y + _offset, z] for x, y, z in _portal_vert3],
)
Portal3 = PortalCouple(name="Portal3", portal_a=Portal3A, portal_b=Portal3B)
Portal3.add_object_to_portal(Cube)

portals = [Portal1, Portal2, Portal3]
scene = [
    Cube.to_dict(),
    Portal1.to_dict(),
    Portal2.to_dict(),
    Portal3.to_dict(),
]
