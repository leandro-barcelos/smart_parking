from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
import subprocess
import os
import sys

from constants import PREFIX, DOUBLE_ROWS, ROW_DIST, SLOTS_PER_ROW, SLOT_WIDTH, INFINITY

DISABLED_PER_ROW = 1

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # type: ignore


def create_node(file, id, x, y):
    print(f'<node id="{id}" x="{x}" y="{y}"/>', file=file)


def create_edge(file, id, from_, to, oneWay=True, numLanes=2):
    if oneWay:
        print(
            f'<edge id="{id}" from="{from_}" to="{to}" numLanes="{numLanes}"/>',
            file=file,
        )
    else:
        print(
            f"""<edge id="{id}" from="{from_}" to="{to}" numLanes="{numLanes}">
    <lane index="0" allow="pedestrian" width="2.00"/>
    <lane index="1" disallow="pedestrian"/>
</edge>""",
            file=file,
        )


def create_parking_area(file, id, lane, x, n_disabled=0, angle=270, length=8):
    print(
        f'\t<parkingArea id="ParkArea{id}" lane="{lane}" angle="{angle}" length="{length}">',
        file=file,
    )

    space_padding = (3 * SLOT_WIDTH - 1) / SLOTS_PER_ROW

    y = space_padding + 3

    spaces = []
    for i in range(SLOTS_PER_ROW):
        if i < n_disabled:
            disabled = True
        else:
            disabled = False

        space = f"""      <space x="{x}" y="{y}">
            <param key="id" value="r{id}s{i}"/>
            <param key="disabled" value="{disabled}"/>
        </space>"""
        spaces.append(space)

        y += SLOT_WIDTH + space_padding

    for space in spaces:
        print(space, file=file)

    print("</parkingArea>", file=file)


# def create_parking_area(file, id, lane, angle=270, length=8):
#     print(
#         f'\t<parkingArea id="{id}" lane="{lane}" roadsideCapacity="{SLOTS_PER_ROW}" angle="{angle}" length="{length}"/>',
#         file=file,
#     )


def create_vtype(file, id, color, vClass=""):
    vClass_str = f'vClass="{vClass}"' if vClass != "" else ""

    print(
        (f'\t<vType id="{id}" color="{color}" {vClass_str}/> '),
        file=file,
    )


def create_trip(file, id, type, depart, from_, to, parkingArea):
    print(
        f"""    <trip id="{id}" type="{type}" depart="{depart}" from="{from_}" to="{to}">
        <stop parkingArea="{parkingArea}" duration="{INFINITY}"/>
    </trip>""",
        file=file,
    )


# network building
nodes = open(f"{PREFIX}.nod.xml", "w")
sumolib.xml.writeHeader(nodes, root="nodes")
edges = open(f"{PREFIX}.edg.xml", "w")
sumolib.xml.writeHeader(edges, root="edges")

# entrada
nodeID = "principal0"
create_node(nodes, "principalentrada", -100, 0)
create_edge(edges, "principalin", "principalentrada", nodeID)
for row in range(DOUBLE_ROWS):
    nextNodeID = f"principal{row}"
    x = row * ROW_DIST
    create_node(nodes, nextNodeID, x, 0)
    if row > 0:
        create_edge(edges, f"principal{row - 1}to{row}", nodeID, nextNodeID)
    nodeID = nextNodeID
create_node(nodes, "principalsaida", x + 100, 0)
create_edge(edges, "principalout", nodeID, "principalsaida")

# saida
y = (SLOTS_PER_ROW + 3) * SLOT_WIDTH
nodeID = "secundaria0"
create_node(nodes, "secundariaentrada", -100, y)
create_edge(edges, "secundariain", nodeID, "secundariaentrada")
for row in range(DOUBLE_ROWS):
    nextNodeID = f"secundaria{row}"
    x = row * ROW_DIST
    create_node(nodes, nextNodeID, x, y)
    if row > 0:
        create_edge(edges, f"secundaria{row - 1}to{row}", nextNodeID, nodeID)
    nodeID = nextNodeID
create_node(nodes, "secundariasaida", x + 100, y)
create_edge(edges, "secundariaout", "secundariasaida", nodeID)

# roads in the parking area
for row in range(DOUBLE_ROWS):
    create_edge(edges, f"road{row}", f"principal{row}", f"secundaria{row}", False)
    create_edge(edges, f"-road{row}", f"secundaria{row}", f"principal{row}", False)

print("</nodes>", file=nodes)
nodes.close()
print("</edges>", file=edges)
edges.close()

subprocess.call(
    [
        sumolib.checkBinary("netconvert"),
        "-n",
        f"{PREFIX}.nod.xml",
        "-e",
        f"{PREFIX}.edg.xml",
        "-o",
        f"{PREFIX}.net.xml",
    ]
)

# Parking Areas
stops = open(f"{PREFIX}.add.xml", "w")
sumolib.xml.writeHeader(stops, root="additional")
for row in range(DOUBLE_ROWS):
    x = (row + 3) * ROW_DIST + 1.75
    # create_parking_area(stops, f"ParkArea{row}", f"road{row}_1")
    # create_parking_area(stops, f"ParkArea-{row}", f"-road{row}_1")
    create_parking_area(stops, str(row), f"-road{row}_1", x, DISABLED_PER_ROW)
    create_parking_area(
        stops, "-" + str(row), f"road{row}_1", x + ROW_DIST / 2, DISABLED_PER_ROW
    )

# vehicle types
create_vtype(stops, "car", "0.7,0.0,0.0")
create_vtype(stops, "disabled", "0.0,0.0,0.7")
create_vtype(stops, "ped_pedestrian", "1,0.2,0.2", "pedestrian")

print("</additional>", file=stops)
stops.close()

PERIOD = 5

# routes person
routes = open(f"{PREFIX}_demand{PERIOD}.rou.xml", "w")
print("<routes>", file=routes)
for v in range(SLOTS_PER_ROW):
    for idx in range(DOUBLE_ROWS):
        if idx < DISABLED_PER_ROW:
            type_ = "disabled"
        else:
            type_ = "car"

        create_trip(
            routes,
            f"v{idx}.{v}",
            type_,
            v * PERIOD,
            "principalin",
            f"road{idx}",
            f"ParkArea{idx}",
        )
        create_trip(
            routes,
            f"v-{idx}.{v}",
            type_,
            v * PERIOD,
            "principalin",
            f"-road{idx}",
            f"ParkArea-{idx}",
        )

print("</routes>", file=routes)
routes.close()

# sumo config
config = open(f"{PREFIX}{PERIOD}.sumocfg", "w")
print(
    f"""<configuration>
    <input>
        <net-file value="{PREFIX}.net.xml"/>
        <route-files value="{PREFIX}_demand{PERIOD}.rou.xml"/>
        <additional-files value="{PREFIX}.add.xml"/>
        <no-step-log value="True"/>
        <time-to-teleport value="0"/>
    </input>
</configuration>""",
    file=config,
)
config.close()
