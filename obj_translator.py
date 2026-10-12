def load_objs(file_path, scale=1):
    with open(file_path) as file:
        lines = file.readlines()

    recording = False
    objects = []
    vertexes = []
    faces = []
    curr_mtl = None

    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        command, *args = parts

        if command == "o":
            name = args[0]
            if recording:  # add current object, reset
                objects.append({"name": name, "vertexes": vertexes, "faces": faces})
                vertexes = []
                faces = []
            else:
                recording = True

        elif command == "v":
            vertexes.append(list(map(lambda x: float(x) * scale, args)))
        elif command == "f":
            faces.append(([int(i.split("/")[0]) - 1 for i in args], curr_mtl))
        elif command == "usemtl":
            curr_mtl = args[0]

    objects.append({"name": name, "vertexes": vertexes, "faces": faces})

    # pprint(vertexes)
    return objects


def load_mtl(file_path):
    with open(file_path) as file:
        lines = file.readlines()

    colors = {}
    curr_mtl = None

    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        command, *args = parts
        if command == "newmtl":
            curr_mtl = args[0]
        elif command == "Kd" and curr_mtl:
            colors[curr_mtl] = tuple([float(i) for i in args])
    return colors


if __name__ == "__main__":
    scene = load_objs("objs/cube.obj", 10)
    scene_colors = load_mtl("objs/cube.mtl")

    print(scene)
    print(scene_colors)
