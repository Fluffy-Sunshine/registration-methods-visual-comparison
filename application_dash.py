import json
import trimesh
import logging
import numpy as np
import plotly.graph_objects as go
import constants
import registration_methods
import application_html
from copy import deepcopy
from plotly.subplots import make_subplots
from dash import Dash, Output, Input, callback_context, ctx
from constants import FILEPATH, PATIENTS, TIMESTAMPS

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)
app.layout = application_html.layout

# enable only console writing errors
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

# global variables used to propagate values from one graph to the others
patient_id = "137"
timestamp_i = 0  # one lower than actual timestamp because used as index
organ = "Prostate"

# loading of the computed distances used for the graphs
with open("computations_files/icp_distances_c.txt", "r") as icp_dist, \
        open("computations_files/icp_averages_c.txt", "r") as icp_avrg:
    all_distances_icp = json.load(icp_dist)
    lines = icp_avrg.read().splitlines()
    avrg_prostate_icp = list(map(float, lines[::3]))
    avrg_bladder_icp = list(map(float, lines[1::3]))
    avrg_rectum_icp = list(map(float, lines[2::3]))

with open("computations_files/center_distances_c.txt", "r") as center_dist, \
        open("computations_files/center_averages_c.txt", "r") as center_avrg:
    all_distances_center = json.load(center_dist)
    lines = center_avrg.read().splitlines()
    avrg_bones_center = list(map(float, lines[::3]))
    avrg_bladder_center = list(map(float, lines[1::3]))
    avrg_rectum_center = list(map(float, lines[2::3]))

with open("computations_files/rotation_icp.txt", "r") as rotations_icp:
    rotations = json.load(rotations_icp)


def create_meshes_from_objs(objects, color):
    """
    Transforms imported .obj volume to go.Mesh3d.
    :param objects: imported .objs
    :param color: mesh color - pink for the first, purple for the second chosen timestamp
    :return: go.Mesh3d meshes
    """
    meshes = []
    for elem in objects:
        x, y, z = np.array(elem[0]).T
        i, j, k = np.array(elem[1]).T
        pl_mesh = go.Mesh3d(x=x, y=y, z=z, color=color, flatshading=True, i=i, j=j, k=k, showscale=False)
        meshes.append(pl_mesh)
    return meshes


def order_slice_vertices(vertices, indices):
    """
    Corrects the order of the vertices from the slice.
    :param vertices: vertices of the slice
    :param indices: the order of the vertices
    :return: vertices in the correct order
    """
    ordered_vertices = []
    for index in indices:
        ordered_vertices.append(vertices[index])

    return ordered_vertices


@app.callback(
    Output(component_id='method', component_property='style'),
    Output(component_id='alignment-radioitems', component_property='style'),
    Output(component_id='timestamp', component_property='style'),
    Output(component_id='fst-timestamp-dropdown', component_property='style'),
    Output(component_id='snd-timestamp-dropdown', component_property='style'),
    Output(component_id='main-graph', component_property='style'),
    Output(component_id='rotations-axes', component_property='style'),
    Output(component_id='x-slice', component_property='style'),
    Input(component_id='mode-radioitems', component_property='value'))
def options_visibility(mode):
    """
    Changes the 3D graph options visibility according to the chosen mode
    :param mode: either Two timestamps or Plan organs mode
    :return: display style
    """
    if mode == "Two timestamps":
        return {'display': 'inline-block', "padding": "0px 50px 0px 45px"}, \
               {'display': 'inline-block', "font-size": "18px", "padding": "0px 100px 0px 12px"}, \
               {'display': 'inline-block', "padding": "0px 20px 0px 45px"}, \
               {'display': 'inline-block', "width": "60px",
                "height": "30px", "font-size": "16px", "padding": "0px 0px 0px 0px"}, \
               {'display': 'inline-block', "width": "60px",
                "height": "30px", "font-size": "16px", "padding": "0px 0px 0px 30px"}, \
               {"padding": "20px 0px 0px 45x", "display": "inline-block",
                "margin": "20px 0px 10px 45px", "height": "550px"}, {"padding": "137px 0px 0px 0px"}, \
               {"padding": "99px 0px 0px 0px"}

    else:
        return {'display': 'none'}, {'display': 'none'}, {'display': 'none'}, {'display': 'none'}, \
               {'display': 'none'}, {"padding": "20px 0px 0px 45x", "display": "inline-block",
                                     "margin": "14px 0px 10px 45px", "height": "562px"}, \
               {"padding": "50px 0px 0px 0px"}, {"padding": "12px 0px 0px 0px"}


def decide_organs_highlights(click_data, click_id, icp):
    """
    Computes what to highlight in the organ_distances graph according to clickData from other graphs.
    :param click_data: information about the location of the last click
    :param click_id: id of the last clicked graph
    :param icp: true if the organs graph is the icp version, false otherwise
    :return: colors and sizes of the traces in the organs graphs
    """
    global patient_id
    global timestamp_i
    global organ

    colors = [[constants.BLUE1] * 13, [constants.BLUE3] * 13, [constants.BLUE4] * 13] if icp else \
        [[constants.BLUE2] * 13, [constants.BLUE3] * 13, [constants.BLUE4] * 13]
    sizes = [[0] * 13, [0] * 13, [0] * 13]
    data = click_data["points"][0]

    if "heatmap" in click_id:
        patient_id = PATIENTS[data["y"]]
        timestamp_i = int(data["x"]) // 4
        organ = data["text"]
        if data["text"] == "Bladder":
            organ = "Bladder"
            colors[1][timestamp_i], sizes[1][timestamp_i] = "white", 4
        elif data["text"] == "Rectum":
            organ = "Rectum"
            colors[2][timestamp_i], sizes[2][timestamp_i] = "white", 4
        elif (data["text"] == "Prostate" and icp) or (data["text"] == "Bones" and not icp):
            colors[0][timestamp_i], sizes[0][timestamp_i] = "white", 4

    elif "average" in click_id:
        patient_id = data["x"]
        trace = data["curveNumber"] if data["curveNumber"] < 3 else int((data["curveNumber"]) - 1) % 3
        if trace == 1:
            organ = "Bladder"
            colors[1], sizes[1] = ["white"] * 13, [4] * 13
        elif trace == 2:
            organ = "Rectum"
            colors[2], sizes[2] = ["white"] * 13, [4] * 13
        elif (data["curveNumber"] == 0 and icp) or (data["curveNumber"] == 4 and not icp):
            organ = "Prostate" if data["curveNumber"] == 0 else "Bones"
            colors[0], sizes[0] = ["white"] * 13, [4] * 13

    elif "organ" in click_id:
        timestamp_i = int(data["x"]) - 1
        trace = data["curveNumber"] if data["curveNumber"] < 3 else int((data["curveNumber"]) - 1) % 3
        if trace != 0 or (icp and data["marker.line.color"] == constants.BLUE1) \
                or (not icp and data["marker.line.color"] == constants.BLUE2):
            colors[trace][timestamp_i], sizes[trace][timestamp_i] = "white", 4
        if trace == 1:
            organ = "Bladder"
        elif trace == 2:
            organ = "Rectum"
        elif data["curveNumber"] == 0:
            organ = "Prostate"
        else:
            organ = "Bones"

    elif "alignment-differences" in click_id:
        timestamp_i = int(data["x"]) - 1
        if data["curveNumber"] == 0:
            organ = "Bladder"
            colors[1][timestamp_i], sizes[1][timestamp_i] = "white", 4
        elif data["curveNumber"] == 1:
            colors[2][timestamp_i], sizes[2][timestamp_i] = "white", 4
            organ = "Rectum"

    elif "rotations-graph" in click_id:
        timestamp_i = int(data["x"]) - 1
        colors[0][timestamp_i], colors[1][timestamp_i], colors[2][timestamp_i] = "white", "white", "white"
        sizes[0][timestamp_i], sizes[1][timestamp_i], sizes[2][timestamp_i] = 4, 4, 4

    return colors, sizes


@app.callback(
    Output("organ-distances", "figure"),
    Input("organ-distances", "clickData"),
    Input("alignment-differences", "clickData"),
    Input("average-distances", "clickData"),
    Input("heatmap-icp", "clickData"),
    Input("heatmap-center", "clickData"),
    Input("rotations-graph", "clickData"),
    Input("scale-organs", "value"))
def create_organ_distances(click_data, differences, average_distances, heatmap_icp, heatmap_center, rotations_graph,
                           scale):
    """
    Creates the organ_distances graph which shows how patient's organs moved in the 13 timestamps after RM aligning.
    :param click_data: clickData from this graph
    :param differences: clickData from the differences graph
    :param average_distances: clickData from the average_distances graph
    :param heatmap_icp: clickData from the heatmap_icp graph
    :param heatmap_center: clickData from the heatmap_center graph
    :param rotations_graph: clickData from the rotations graph
    :param scale: changes axis range, can be uniform or individual
    :return: organ_distances figure
    """
    global patient_id

    all_click_data = [click_data, differences, average_distances, heatmap_icp, heatmap_center, rotations_graph]
    all_ids = ["organ-distances", "alignment-differences", "average-distances", "heatmap-icp", "heatmap-center",
               "rotations-graph"]
    click_data, click_id = resolve_click_data(all_click_data, all_ids)
    colors_icp, colors_center = [[constants.BLUE1] * 13, [constants.BLUE3] * 13, [constants.BLUE4] * 13], \
                                [[constants.BLUE2] * 13, [constants.BLUE3] * 13, [constants.BLUE4] * 13]
    sizes_icp = sizes_center = [[0] * 13, [0] * 13, [0] * 13]

    if click_data:
        colors_icp, sizes_icp = decide_organs_highlights(click_data, click_id, True)
        colors_center, sizes_center = decide_organs_highlights(click_data, click_id, False)

    fig = make_organ_distances_figure(colors_icp, sizes_icp, colors_center, sizes_center)

    fig.update_xaxes(title_text="Timestamp", tick0=0, dtick=1, zerolinewidth=1.2, gridcolor=constants.GREY, gridwidth=2)
    fig.update_yaxes(title_text="Distance [mm]", zerolinewidth=1.2, gridcolor=constants.GREY, gridwidth=1.2)

    if "uniform" in scale:
        fig.update_xaxes(matches="x")
        fig.update_yaxes(matches="y")

    fig.update_layout(yaxis2_showticklabels=True, xaxis2_showticklabels=True, uirevision=patient_id,
                      font=dict(size=17, color='darkgrey'), paper_bgcolor='rgba(50,50,50,1)',
                      legend=dict(orientation="h", entrywidth=130, yanchor="top", y=1.17, xanchor='center', x=0.53),
                      margin=dict(t=85, b=70, l=90), plot_bgcolor='rgba(70,70,70,1)', height=380)
    fig.update_annotations(yshift=37, font=dict(size=18, color='lightgrey'))

    return fig


def make_organ_distances_figure(colors_icp, sizes_icp, colors_center, sizes_center):
    """
    Helper function for plotting of the organ distances graph
    :param colors_icp: colors for the icp traces
    :param sizes_icp: sizes of the icp traces
    :param colors_center: colors for the prostate centring traces
    :param sizes_center: sizes of the prostate centring traces
    :return: organ distances figure
    """
    prostate, bladder_icp, rectum_icp = all_distances_icp[PATIENTS.index(patient_id)]
    bones, bladder_center, rectum_center = all_distances_center[PATIENTS.index(patient_id)]

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.1, subplot_titles=(
        "Distances of ICP aligned organs and the plan organs of patient {}".format(patient_id),
        "Distances of the prostate centred organs and the plan organs of patient {}".format(patient_id)))

    # the first symbol has one bigger size because is less visible
    fig.add_trace(go.Scattergl(x=np.array(range(1, 14)), y=prostate, mode="lines+markers", name="Prostate",
                               marker=dict(color=constants.BLUE1, symbol="x", size=13,
                                           line=dict(width=sizes_icp[0], color=colors_icp[0]))), row=1, col=1)
    fig.add_trace(go.Scattergl(x=np.array(range(1, 14)), y=bladder_icp, mode="lines+markers", name="Bladder",
                               marker=dict(color=constants.BLUE3, symbol="square", size=12,
                                           line=dict(width=sizes_icp[1], color=colors_icp[1]))), row=1, col=1)
    fig.add_trace(go.Scattergl(x=np.array(range(1, 14)), y=rectum_icp, mode="lines+markers", name="Rectum",
                               marker=dict(color=constants.BLUE4, symbol="diamond", size=12,
                                           line=dict(width=sizes_icp[2], color=colors_icp[2]))), row=1, col=1)

    # auxiliary trace for nice displaying of the legend
    fig.add_trace(go.Scattergl(x=[1], y=[0], name="", opacity=0, hoverinfo="skip"), row=1, col=1)

    fig.add_trace(go.Scattergl(x=np.array(range(1, 14)), y=bones, mode="lines+markers", name="Bones",
                               marker=dict(color=constants.BLUE2, symbol="circle", size=12,
                                           line=dict(width=sizes_center[0], color=colors_center[0]))), row=1, col=2)
    fig.add_trace(go.Scattergl(x=np.array(range(1, 14)), y=bladder_center, mode="lines+markers", name="Bladder",
                               marker=dict(color=constants.BLUE3, symbol="square", size=12,
                                           line=dict(width=sizes_center[1], color=colors_center[1]))), row=1, col=2)
    fig.add_trace(go.Scattergl(x=np.array(range(1, 14)), y=rectum_center, mode="lines+markers", name="Rectum",
                               marker=dict(color=constants.BLUE4, symbol="diamond", size=12,
                                           line=dict(width=sizes_center[2], color=colors_center[2]))), row=1, col=2)

    return fig


def decide_differences_highlights(click_data, click_id):
    """
    Computes what to highlight in the differences graph according to clickData from other graphs.
    :param click_data: information about the location of the last click
    :param click_id: id of the last clicked graph
    :return: colors of the traces in the differences graph
    """
    colors = [[constants.BLUE3] * 13, [constants.BLUE4] * 13]
    data = click_data["points"][0]

    if "heatmap" in click_id:
        if data["text"] == "Bladder":
            colors[0][timestamp_i] = "white"
        elif data["text"] == "Rectum":
            colors[1][timestamp_i] = "white"

    elif "average" in click_id:
        trace = data["curveNumber"] if data["curveNumber"] < 3 else (data["curveNumber"] - 1) % 3
        if trace == 1:
            colors[0] = ["white"] * 13
        elif trace == 2:
            colors[1] = ["white"] * 13

    elif "organ" in click_id:
        trace = data["curveNumber"] if data["curveNumber"] < 3 else (data["curveNumber"] - 1) % 3
        if trace == 1:
            colors[0][timestamp_i] = "white"
        elif trace == 2:
            colors[1][timestamp_i] = "white"

    elif "alignment-differences" in click_id:
        colors[data["curveNumber"]][timestamp_i] = "white"

    elif "rotations-graph" in click_id:
        colors[0][timestamp_i], colors[1][timestamp_i] = "white", "white"

    return colors


@app.callback(
    Output("alignment-differences", "figure"),
    Input("alignment-differences", "clickData"),
    Input("organ-distances", "clickData"),
    Input("average-distances", "clickData"),
    Input("heatmap-icp", "clickData"),
    Input("heatmap-center", "clickData"),
    Input("rotations-graph", "clickData"))
def create_distances_between_alignments(differences, organ_distances, average_distances, heatmap_icp, heatmap_center,
                                        rotations_graph):
    """
    Creates the differences graph which shows the distinctions between the RM.
    :param differences: clickData from this graph
    :param organ_distances: clickData from the organ_distances graph
    :param average_distances: clickData from the average_distances graph
    :param heatmap_icp: clickData from the heatmap_icp graph
    :param heatmap_center: clickData from the heatmap_center graph
    :param rotations_graph: clickData from the rotations graph
    :return: differences graph figure
    """
    global patient_id
    dist_icp = all_distances_icp[PATIENTS.index(patient_id)]
    dist_center = all_distances_center[PATIENTS.index(patient_id)]
    distances = np.array(dist_icp) - np.array(dist_center)
    _, bladder, rectum = distances[0], distances[1], distances[2]
    colors = [[constants.BLUE3] * 13, [constants.BLUE4] * 13]

    all_click_data = [differences, organ_distances, average_distances, heatmap_icp, heatmap_center, rotations_graph]
    all_ids = ["alignment-differences", "organ-distances", "average-distances", "heatmap-icp", "heatmap-center",
               "rotations-graph"]
    click_data, click_id = resolve_click_data(all_click_data, all_ids)

    if click_data:
        colors = decide_differences_highlights(click_data, click_id)

    layout = go.Layout(font=dict(size=12, color='darkgrey'), paper_bgcolor='rgba(50,50,50,1)', height=370,
                       margin=dict(t=80, b=70, l=90, r=40), plot_bgcolor='rgba(70,70,70,1)', title=dict(
            text="Differences of distances between the registration methods of patient {}".format(patient_id),
            font=dict(size=20, color='lightgrey')), uirevision=patient_id)
    fig = go.Figure(layout=layout)
    fig.add_trace(go.Bar(x=np.array(range(1, 14)), y=bladder, name="Bladder", marker=dict(color=colors[0])))
    fig.add_trace(go.Bar(x=np.array(range(1, 14)), y=rectum, name="Rectum", marker=dict(color=colors[1])))

    fig.update_xaxes(title_text="Timestamp", tick0=0, dtick=1)
    fig.update_yaxes(title_text="    Prostate centring | ICP distance [mm]", title_font={"size": 17},
                     gridcolor=constants.GREY)
    fig.update_layout(title_x=0.5, font=dict(size=17), title_y=0.90)

    return fig


@app.callback(
    Output("rotations-graph", "figure"),
    Input("rotations-graph", "clickData"),
    Input("heatmap-icp", "clickData"),
    Input("heatmap-center", "clickData"),
    Input("organ-distances", "clickData"),
    Input("alignment-differences", "clickData"),
    Input("average-distances", "clickData"))
def create_rotation_icp_graph(rotations_graph, heatmap_icp, heatmap_center, organ_distances, differences, avrg):
    """
    Creates the rotations graph which shows rotation after ICP RM.
    :param rotations_graph: clickData from this graph
    :param heatmap_icp: clickData from the heatmap_icp graph
    :param heatmap_center: clickData from the heatmap_center graph
    :param organ_distances: clickData from the organ_distances graph
    :param differences: clickData from the differences graph
    :param avrg: clickData from the average graph, we do not use for highlighting
     only for patient changes so we still need the callback to fire
    :return: rotations figure
    """
    colors = [[constants.GREEN] * 13, [constants.YELLOW] * 13, [constants.ORANGE] * 13]
    all_click_data = [rotations_graph, heatmap_icp, heatmap_center, organ_distances, differences]
    all_ids = ["rotations-graph", "heatmap-icp", "heatmap-center", "organ-distances", "alignment-differences"]
    click_data, click_id = resolve_click_data(all_click_data, all_ids)

    if click_data:
        if "rotations" not in click_id:
            colors[0][timestamp_i], colors[1][timestamp_i], colors[2][timestamp_i] = "white", "white", "white"
        else:
            data = click_data["points"][0]
            colors[int(data["curveNumber"])][timestamp_i] = "white"

    rot_x, rot_y, rot_z = rotations[PATIENTS.index(patient_id)][0]

    layout = go.Layout(font=dict(size=12, color='darkgrey'), paper_bgcolor='rgba(50,50,50,1)',
                       margin=dict(t=80, b=70, l=90, r=40), plot_bgcolor='rgba(70,70,70,1)', height=350,
                       title=dict(text="Rotation angles after ICP bone alignment of patient {}".format(patient_id),
                                  font=dict(size=20, color='lightgrey')), uirevision=patient_id)
    fig = go.Figure(layout=layout)
    fig.add_trace(go.Bar(x=np.array(range(1, 14)), y=rot_x, name="X", marker=dict(color=colors[0])))
    fig.add_trace(go.Bar(x=np.array(range(1, 14)), y=rot_y, name="Y", marker=dict(color=colors[1])))
    fig.add_trace(go.Bar(x=np.array(range(1, 14)), y=rot_z, name="Z", marker=dict(color=colors[2])))

    fig.update_xaxes(title_text="Timestamp", tick0=0, dtick=1)
    fig.update_yaxes(title_text="Angle [°]", gridcolor=constants.GREY)
    fig.update_layout(title_x=0.5, font=dict(size=17), title_y=0.90)

    return fig


def decide_average_highlights(data, click_id, icp):
    """
    Computes what to highlight in the average_distances graph according to clickData from other graphs.
    :param data: relevant information about the location of the last click
    :param click_id: id of the last clicked graph
    :param icp: whether we highlight in the icp or prostate aligning version of the average graphs
    :return: colors and sizes of the traces in the average graph
    """
    colors = [[constants.BLUE1] * 8, [constants.BLUE3] * 8, [constants.BLUE4] * 8]
    sizes = [[0] * 8, [0] * 8, [0] * 8]
    pat = PATIENTS.index(patient_id)
    data = data["points"][0]

    if "heatmap" in click_id:
        if (icp and data["text"] == "Prostate") or (not icp and data["text"] == "Bones"):
            colors[0][pat] = "white"
            sizes[0][pat] = 3
        elif data["text"] == "Bladder":
            colors[1][pat] = "white"
            sizes[1][pat] = 3
        elif data["text"] == "Rectum":
            colors[2][pat] = "white"
            sizes[2][pat] = 3

    elif "average" in click_id:
        trace = data["curveNumber"] if data["curveNumber"] < 3 else int((data["curveNumber"]) - 1) % 3
        if data["curveNumber"] != 0 and data["curveNumber"] != 4 or \
                (data["curveNumber"] == 0 and icp) or (data["curveNumber"] == 4 and not icp):
            colors[trace][pat] = "white"
            sizes[trace][pat] = 3

    elif "differences" in click_id:
        trace = data["curveNumber"] if data["curveNumber"] < 3 else int((data["curveNumber"]) - 1) % 3
        highlight = 1 if trace == 0 else 2
        colors[highlight][pat] = "white"
        sizes[highlight][pat] = 3

    elif "rotations" in click_id:
        colors[0][pat], colors[1][pat], colors[2][pat] = "white", "white", "white"
        sizes[0][pat], sizes[1][pat], sizes[2][pat] = 3, 3, 3

    elif "distances" in click_id:
        trace = data["curveNumber"] if data["curveNumber"] < 3 else int((data["curveNumber"]) - 1) % 3
        if trace > 0:
            colors[trace][pat] = "white"
            sizes[trace][pat] = 3
        else:
            if (icp and data["curveNumber"] == 0) or (not icp and data["curveNumber"] == 4):
                colors[trace][pat] = "white"
                sizes[trace][pat] = 3

    return colors, sizes


@app.callback(
    Output("average-distances", "figure"),
    Input("alignment-differences", "clickData"),
    Input("organ-distances", "clickData"),
    Input("average-distances", "clickData"),
    Input("heatmap-icp", "clickData"),
    Input("heatmap-center", "clickData"),
    Input("rotations-graph", "clickData"),
    Input("scale-average", "value"))
def create_average_distances(differences, organ_distances, click_data, heatmap_icp, heatmap_center, rotations_graph,
                             scale):
    """
    Creates the average_distances graph which shows the average movements of patient's organs after RMs aligning.
    :param differences: clickData from the differences graph
    :param organ_distances: clickData from the organ_distances graph
    :param click_data: clickData from this graph
    :param heatmap_icp: clickData from the heatmap_icp graph
    :param heatmap_center: clickData from the heatmap_center graph
    :param rotations_graph: clickData from the rotations graph
    :param scale: sets the axis range, can be uniform or individual
    :return: the average_distances figure
    """
    all_click_data = [differences, organ_distances, click_data, heatmap_icp, heatmap_center, rotations_graph]
    all_ids = ["alignment-differences", "organ-distances", "average-distances", "heatmap-icp", "heatmap-center",
               "rotations-graph"]
    click_data, click_id = resolve_click_data(all_click_data, all_ids)
    colors_icp, colors_center = [[constants.BLUE1] * 13, [constants.BLUE3] * 13, [constants.BLUE4] * 13], \
                                [[constants.BLUE2] * 13, [constants.BLUE3] * 13, [constants.BLUE4] * 13]
    sizes_icp = sizes_center = [[0] * 13, [0] * 13, [0] * 13]

    if click_data:
        colors_icp, sizes_icp = decide_average_highlights(click_data, click_id, True)
        colors_center, sizes_center = decide_average_highlights(click_data, click_id, False)

    fig = make_averages_figure(colors_icp, sizes_icp, colors_center, sizes_center)

    fig.update_xaxes(title_text="Patient", zerolinewidth=1.2, gridcolor=constants.GREY, gridwidth=2)
    fig.update_yaxes(title_text="Average distance [mm]", zerolinewidth=1.2, gridcolor=constants.GREY, gridwidth=1.2)

    if "uniform" in scale:
        fig.update_xaxes(matches="x")
        fig.update_yaxes(matches="y")

    fig.update_layout(yaxis2_showticklabels=True, xaxis2_showticklabels=True, font=dict(size=17, color='darkgrey'),
                      paper_bgcolor='rgba(50,50,50,1)', margin=dict(t=80, b=70, l=90, r=81),
                      legend=dict(orientation="h", entrywidth=130, yanchor="top", y=1.15, xanchor='center', x=0.53),
                      plot_bgcolor='rgba(70,70,70,1)', height=380, uirevision="foo")
    fig.update_annotations(yshift=35, font=dict(size=19, color='lightgrey'))

    return fig


def make_averages_figure(colors_icp, sizes_icp, colors_center, sizes_center):
    """
    Helper function for plotting of the average graph
    :param colors_icp: colors for the icp traces
    :param sizes_icp: sizes of the icp traces
    :param colors_center: colors for the prostate centring traces
    :param sizes_center: sizes of the prostate centring traces
    :return: averages figure
    """
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.1,
                        subplot_titles=("Average difference of patients' organs positions after ICP aligning",
                                        "Average difference of patients' organs positions after prostate centring"))

    fig.add_trace(go.Scattergl(x=PATIENTS, y=avrg_prostate_icp, mode="markers", name="Prostate",
                               marker=dict(symbol="x", color=constants.BLUE1, size=13,
                                           line=dict(width=sizes_icp[0], color=colors_icp[0]))), row=1, col=1)
    fig.add_trace(go.Scattergl(x=PATIENTS, y=avrg_bladder_icp, mode="markers", name="Bladder",
                               marker=dict(symbol="square", color=constants.BLUE3, size=12,
                                           line=dict(width=sizes_icp[1], color=colors_icp[1]))), row=1, col=1)
    fig.add_trace(go.Scattergl(x=PATIENTS, y=avrg_rectum_icp, mode="markers", name="Rectum",
                               marker=dict(symbol="diamond", color=constants.BLUE4, size=12,
                                           line=dict(width=sizes_icp[2], color=colors_icp[2]))), row=1, col=1)

    # auxiliary trace for nice displaying of the legend
    fig.add_trace(go.Scattergl(x=[137], y=[0], name="", opacity=0, hoverinfo="skip"), row=1, col=1)

    fig.add_trace(go.Scattergl(x=PATIENTS, y=avrg_bones_center, mode="markers", name="Bones",
                               marker=dict(symbol="circle", color=constants.BLUE2, size=12,
                                           line=dict(width=sizes_center[0], color=colors_center[0]))), row=1, col=2)
    fig.add_trace(go.Scattergl(x=PATIENTS, y=avrg_bladder_center, mode="markers", name="Bladder",
                               marker=dict(symbol="square", color=constants.BLUE3, size=12,
                                           line=dict(width=sizes_center[1], color=colors_center[1]))), row=1, col=2)
    fig.add_trace(go.Scattergl(x=PATIENTS, y=avrg_rectum_center, mode="markers", name="Rectum",
                               marker=dict(symbol="diamond", color=constants.BLUE4, size=12,
                                           line=dict(width=sizes_center[2], color=colors_center[2]))), row=1, col=2)

    return fig


def resolve_click_data(click_data, ids):
    """
    Decides which graph was clicked last.
    :param click_data: clickData from every graph
    :param ids: ids of every graph
    :return: clickData info and the last clicked graph id or None if nothing was clicked in the graphs
    """
    input_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    for i, click_id in zip(range(len(ids)), ids):
        if input_id == click_id:
            return click_data[i], input_id
    return None, None


def create_lines_for_heatmaps(fig):
    """
    Creates lines dividing timestamps and patients in the heatmaps
    :param fig: one of the heatmaps figure
    """
    fig.add_shape(type="rect", x0=-0.48, y0=-0.5, x1=-0.48, y1=7.5, line_width=4.15, line_color=constants.GREY)
    fig.add_shape(type="rect", x0=13 * 4 - 0.5, y0=-0.5, x1=13 * 4 - 0.5, y1=7.5, line_width=4.15,
                  line_color=constants.GREY)

    for i in range(1, 13):
        fig.add_shape(type="rect", x0=4 * i - 0.5, y0=-0.5, x1=4 * i - 0.5, y1=7.5, line_width=4,
                      line_color=constants.GREY)
    for i in range(0, 9):
        fig.add_hline(y=i - 0.5, line_width=4, line_color=constants.GREY)


@app.callback(
    Output("heatmap-icp", "figure"),
    Input("organ-distances", "clickData"),
    Input("alignment-differences", "clickData"),
    Input("heatmap-icp", "clickData"),
    Input("heatmap-center", "clickData"),
    Input("average-distances", "clickData"),
    Input("rotations-graph", "clickData"),
    Input("scale-heatmap", "value"),
    Input("heatmap-icp", "relayoutData"))
def create_heatmap_icp(organ_distances, differences, click_data, center_click_data, average_distances, rotations_graph,
                       scale, zoom):
    """
    Creates the heatmap_icp graph which depicts every patient and their every organ movement after icp aligning.
    :param organ_distances: clickData from the organ_distances graph
    :param differences: clickData from the differences graph
    :param click_data: clickData from this graph
    :param center_click_data: clickData from the heatmap_center graph
    :param average_distances: clickData from the average_distances graph
    :param rotations_graph: clickData from the rotations graph
    :param scale: sets the axis range, can be uniform or individual
    :param zoom: indicates if the graph was zoomed to hide or show the organ legend
    :return: heatmap_icp figure
    """
    global patient_id

    layout = go.Layout(font=dict(size=15, color='darkgrey'), paper_bgcolor='rgba(50,50,50,1)',
                       margin=dict(t=100, b=70, l=90, r=81), plot_bgcolor='rgba(50,50,50,1)', height=340,
                       showlegend=True, title=dict(text="Difference of patients' organ positions after ICP "
                                                        "aligning to the bones", font=dict(size=20, color='lightgrey')),
                       uirevision=scale)

    fig = create_heatmap_fig(scale, layout, True)
    create_lines_for_heatmaps(fig)

    all_click_data = [organ_distances, differences, average_distances, click_data, center_click_data, rotations_graph]
    all_ids = ["organ-distances", "alignment-differences", "average-distances", "heatmap-icp", "heatmap-center",
               "rotations-graph"]
    click_data, click_id = resolve_click_data(all_click_data, all_ids)

    if click_data:
        data = click_data["points"][0]
        decide_heatmap_highlights(fig, data, click_id)

    # decide whether add organ legend according to zoom
    if not zoom or len(zoom) <= 1 or "xaxis.autorange" in zoom.keys():
        add_heatmap_annotations(fig)

    fig.update_xaxes(title_text="Timestamp", ticktext=TIMESTAMPS, tickmode="array", tickvals=np.arange(1.5, 52, 4),
                     zeroline=False, showgrid=False, range=[-0.55, 51.55], title_font={"size": 20}, tickfont_size=18)
    fig.update_yaxes(title_text="Patient", ticktext=PATIENTS + ["info"], tickmode="array", tickvals=np.arange(0, 8, 1),
                     zeroline=False, showgrid=False, title_font={"size": 20}, tickfont_size=18)
    fig.update_layout(title_x=0.5, title_y=0.90, legend={"x": 0.73, "y": 1.14, "orientation": "h", "xanchor": "left"})

    return fig


@app.callback(
    Output("heatmap-center", "figure"),
    Input("heatmap-center", "clickData"),
    Input("heatmap-icp", "clickData"),
    Input("alignment-differences", "clickData"),
    Input("average-distances", "clickData"),
    Input("organ-distances", "clickData"),
    Input("rotations-graph", "clickData"),
    Input("scale-heatmap", "value"),
    Input("heatmap-center", "relayoutData"))
def create_heatmap_centering(click_data, icp_click_data, differences, average_distances, organ_distances,
                             rotations_graph, scale, zoom):
    """
    Creates the heatmap_center graph which depicts every patient and their every organ movement after centering on
    the prostate.
    :param click_data: clickData from this graph
    :param icp_click_data: clickData from the heatmap_icp graph
    :param differences: clickData from the differences graph
    :param average_distances: clickData from the average_distances graph
    :param organ_distances: clickData from the organ_distances graph
    :param rotations_graph: clickData from the rotations graph
    :param scale: sets the axis range, can be uniform or individual
    :param zoom: indicates if the graph was zoomed to hide or show the organ legend
    :return: heatmap_center figure
    """
    global patient_id

    layout = go.Layout(font=dict(size=15, color='darkgrey'), paper_bgcolor='rgba(50,50,50,1)',
                       margin=dict(t=100, b=70, l=90, r=81), plot_bgcolor='rgba(50,50,50,1)', height=340,
                       showlegend=True, title=dict(text="Difference of patients' organs positions after prostate "
                                                        "centring", font=dict(size=20, color='lightgrey')),
                       uirevision=scale)

    fig = create_heatmap_fig(scale, layout, False)
    create_lines_for_heatmaps(fig)

    all_click_data = [organ_distances, differences, average_distances, icp_click_data, click_data, rotations_graph]
    all_ids = ["organ-distances", "alignment-differences", "average-distances", "heatmap-icp", "heatmap-center",
               "rotations-graph"]
    click_data, click_id = resolve_click_data(all_click_data, all_ids)

    if click_data:
        data = click_data["points"][0]
        decide_heatmap_highlights(fig, data, click_id)

    # same as in heatmap_icp
    if not zoom or len(zoom) <= 1 or "xaxis.autorange" in zoom.keys():
        add_heatmap_annotations(fig)

    fig.update_xaxes(title_text="Timestamp", ticktext=TIMESTAMPS, tickmode="array", tickvals=np.arange(1.5, 52, 4),
                     zeroline=False, showgrid=False, range=[-0.55, 51.55], title_font={"size": 20}, tickfont_size=18)
    fig.update_yaxes(title_text="Patient", ticktext=PATIENTS, tickmode="array", tickvals=np.arange(0, 8, 1),
                     zeroline=False, showgrid=False, title_font={"size": 20}, tickfont_size=18)
    fig.update_layout(title_x=0.5, font=dict(size=16), title_y=0.90, legend={"x": 0.73, "y": 1.14, "orientation": "h",
                                                                             "xanchor": "left"})
    return fig


def create_heatmap_fig(scale, layout, icp):
    """
    Helper function to create heatmaps' figures.
    :param scale: selected scale
    :param layout: figure layout
    :param icp: whether the graphs is icp or not
    :return:
    """
    data, custom_data, hover_text = create_data_for_heatmap(icp)

    # changing the colour scale with zmin, zmax
    if "uniform" in scale:
        fig = go.Figure(data=go.Heatmap(z=data, zmin=0, zmax=85, text=hover_text, customdata=custom_data,
                                        colorbar=dict(title="Distance<br>[mm]"),
                                        hovertemplate="<b>%{text}</b><br>Patient: %{y}<br>Timestamp: %{customdata}<br>"
                                                      "Distance: %{z:.2f} mm<extra></extra>",
                                        colorscale=constants.HEATMAP_CS), layout=layout)
    else:
        fig = go.Figure(data=go.Heatmap(z=data, text=hover_text, customdata=custom_data,
                                        colorbar=dict(title="Distance<br>[mm]"),
                                        hovertemplate="<b>%{text}</b><br>Patient: %{y}<br>Timestamp: "
                                                      "%{customdata}<br>" "Distance: %{z:.2f} mm<extra></extra>",
                                        colorscale=constants.HEATMAP_CS), layout=layout)
    return fig


def add_heatmap_annotations(fig):
    """Adds organ legend as image, so it is not clickable"""
    fig.add_layout_image(dict(source=app.get_asset_url("annot_heatmap1.png"),
                              xref="paper", yref="paper", x=0, y=1, sizex=1, sizey=1,
                              xanchor="left", yanchor="bottom"))

    fig.add_layout_image(dict(source=app.get_asset_url("legend_heatmap1.png"),
                              xref="paper", yref="paper", x=1.084, y=1.15, sizex=0.35, sizey=0.35,
                              xanchor="right", yanchor="bottom"))


def decide_heatmap_highlights(fig, data, click_id):
    """
    Computes what to highlight in the heatmaps according to clickData from other graphs.
    :param fig: heatmap figure
    :param data: clickData from the clicked graph
    :param click_id: id of the clicked graph
    """
    if "heatmap" in click_id:
        fig.add_shape(type="rect", x0=data["x"] - 0.43, y0=data["y"] - 0.41, x1=data["x"] + 0.43,
                      y1=data["y"] + 0.41, line_color="white", line_width=4)
    else:
        y = PATIENTS.index(patient_id)
        trace = 0
        if data["curveNumber"] == 0:
            trace = 1
        elif data["curveNumber"] == 1 or data["curveNumber"] == 5:
            trace = 2
        elif data["curveNumber"] == 2 or data["curveNumber"] == 6:
            trace = 3

        if "average" in click_id:
            for i in range(13):
                fig.add_shape(type="rect", x0=(trace - 0.43) + 4 * i, y0=y - 0.41, x1=(trace + 0.43) + 4 * i,
                              y1=y + 0.41, line_width=4, line_color="white")
        elif "organ" in click_id:
            fig.add_shape(type="rect", x0=timestamp_i * 4 - 0.43 + trace, y0=y - 0.41,
                          x1=timestamp_i * 4 + 0.43 + trace, y1=y + 0.41, line_color="white", line_width=4)
        elif "differences" in click_id:
            x = data["curveNumber"] + 2
            fig.add_shape(type="rect", x0=timestamp_i * 4 - 0.43 + x, y0=y - 0.41, x1=timestamp_i * 4 + 0.43 + x,
                          y1=y + 0.41, line_color="white", line_width=4)
        elif "rotations" in click_id:
            fig.add_shape(type="rect", x0=timestamp_i * 4 - 0.43, y0=y - 0.41, x1=timestamp_i * 4 + 3.43,
                          y1=y + 0.41, line_color="white", line_width=4)


def create_data_for_heatmap(icp):
    """
    Creates hover texts and formats the data for the heatmaps
    :param icp: true if our graph is the icp version of the heatmaps, false otherwise
    :return: formatted data for the heatmap and the hover text
    """
    # data is 2d array with distances for the heightmap, custom_data and hover_text are used just for hover labels
    data, custom_data, hover_text = [], [], []
    for i in range(len(PATIENTS)):
        # patient contains four arrays: bones, prostate, bladder, rectum with distances from all the timestamps
        patient = all_distances_icp[i] if icp else all_distances_center[i]
        data_row, custom_row, hover_row = [], [], []

        for j in range(len(TIMESTAMPS)):
            data_row.extend([0, patient[0][j], patient[1][j], patient[2][j]]) if icp \
                else data_row.extend([patient[0][j], 0, patient[1][j], patient[2][j]])
            custom_row.extend([j + 1, j + 1, j + 1, j + 1])
            hover_row.extend(["Bones", "Prostate", "Bladder", "Rectum"])

        data.append(data_row)
        custom_data.append(custom_row)
        hover_text.append(hover_row)

    return data, custom_data, hover_text


@app.callback(
    Output("snd-timestamp-dropdown", "value"),
    Input("organ-distances", "clickData"),
    Input("alignment-differences", "clickData"),
    Input("heatmap-icp", "clickData"),
    Input("heatmap-center", "clickData"),
    Input("rotations-graph", "clickData"))
def update_timestamp_dropdown(organ_distances, differences, heatmap_icp, heatmap_center, rotations_graph):
    """Function needed for updating the callbacks."""
    return timestamp_i + 1


@app.callback(
    Output("rotations-axes", "figure"),
    Input("heatmap-icp", "clickData"),
    Input("heatmap-center", "clickData"),
    Input("average-distances", "clickData"),
    Input("alignment-radioitems", "value"),
    Input("mode-radioitems", "value"),
    Input("fst-timestamp-dropdown", "value"))
def create_3d_angle(heatmap_icp, heatmap_center, average_distances, method, mode, fst_timestamp):
    """
    Creates 3D rotation angle representation graph.
    :param heatmap_icp: used for firing the callback and changing the patient
    :param heatmap_center: used for firing the callback and changing the patient
    :param average_distances: used for firing the callback and changing the patient
    :param method: method of alignment - ICP or prostate centring
    :param mode: plan organs or two timestamps
    :param fst_timestamp: number of the first selected timestamp
    :return: 3D rotation figure
    """
    layout = go.Layout(font=dict(size=12, color='darkgrey'), paper_bgcolor='rgba(50,50,50,1)', showlegend=False,
                       plot_bgcolor='rgba(50,50,50,1)', margin=dict(l=10, r=10, t=10, b=10), height=280, width=320)
    fig = go.Figure(layout=layout)
    camera = dict(up=dict(x=0, y=0, z=1), center=dict(x=0, y=0, z=0), eye=dict(x=1.1, y=0.4, z=0.4))
    annot = []
    steps = 50
    cone_tip = 7
    size = 12

    if "ICP" in method and "Two" in mode and fst_timestamp == "plan":
        text_x = str(round(rotations[PATIENTS.index(patient_id)][0][0][timestamp_i], 2)) + "°"
        text_y = str(round(rotations[PATIENTS.index(patient_id)][0][1][timestamp_i], 2)) + "°"
        text_z = str(round(rotations[PATIENTS.index(patient_id)][0][2][timestamp_i], 2)) + "°"
    else:
        text_x, text_y, text_z = "0°", "0°", "0°"

    create_rotation_axes(fig, annot)
    t = np.linspace(0, 10, steps)
    x, y, z = 20, np.cos(t) * size, np.sin(t) * size

    # X axis rotation arrow
    fig.add_trace(go.Scatter3d(mode="lines", x=[x] * 25, y=y, z=z, line=dict(width=5, color=constants.GREEN),
                               hoverinfo='none'))
    fig.add_trace(go.Cone(x=[x], y=[y[0]], z=[z[0]], u=[0], v=[cone_tip * (y[0] - y[1])], w=[cone_tip * (z[0] - z[1])],
                          showlegend=False, showscale=False, colorscale=[[0, constants.GREEN], [1, constants.GREEN]],
                          hoverinfo='none'))
    annot.append(dict(showarrow=False, text=text_x, x=25, y=-25, z=0, font=dict(color=constants.GREEN, size=15)))

    # Y axis rotation arrow
    x, y, z = np.cos(t) * size, 20, np.sin(t) * size
    fig.add_trace(go.Scatter3d(mode="lines", x=x, y=[y] * 25, z=z, line=dict(width=5, color=constants.YELLOW),
                               hoverinfo='none'))
    fig.add_trace(go.Cone(x=[x[0]], y=[y], z=[z[0]], u=[cone_tip * (x[0] - x[1])], v=[0], w=[cone_tip * (z[0] - z[1])],
                          showlegend=False, showscale=False, colorscale=[[0, constants.YELLOW], [1, constants.YELLOW]],
                          hoverinfo='none'))
    annot.append(dict(showarrow=False, text=text_y, x=5, y=35, z=15, font=dict(color=constants.YELLOW, size=15)))

    # Z axis rotation arrow
    x, y, z = np.cos(t) * size, np.sin(t) * size, 20
    fig.add_trace(go.Scatter3d(mode="lines", x=x, y=y, z=[z] * 25, line=dict(width=5, color=constants.ORANGE),
                               hoverinfo='none'))
    fig.add_trace(go.Cone(x=[x[0]], y=[y[0]], z=[z], u=[cone_tip * (x[0] - x[1])], v=[cone_tip * (y[0] - y[1])],
                          w=[0], showlegend=False, showscale=False, colorscale=[[0, constants.ORANGE],
                                                                                [1, constants.ORANGE]],
                          hoverinfo='none'))
    annot.append(dict(showarrow=False, text=text_z, x=10, y=-10, z=z + 10, font=dict(color=constants.ORANGE, size=15)))

    fig.update_layout(scene=dict(annotations=annot, camera=camera))

    return fig


def create_rotation_axes(fig, annot):
    """
    Creates axes in the 3D space
    :param fig: 3D rotation figure
    :param annot: figure annotations
    """
    cone_tip = 12
    fig.add_trace(go.Scatter3d(x=[-70, 50], y=[0, 0], z=[0, 0], mode='lines', hoverinfo='skip',
                               line=dict(color=constants.GREEN, width=7)))
    fig.add_trace(go.Cone(x=[50], y=[0], z=[0], u=[cone_tip * (50 - 48)], v=[0], w=[0], hoverinfo='none',
                          showlegend=False, showscale=False, colorscale=[[0, constants.GREEN], [1, constants.GREEN]]))

    fig.add_trace(go.Scatter3d(x=[0, 0], y=[-70, 50], z=[0, 0], mode='lines', hoverinfo='skip',
                               line=dict(color=constants.YELLOW, width=7)))
    fig.add_trace(go.Cone(x=[0], y=[50], z=[0], u=[0], v=[cone_tip * (50 - 48)], w=[0], hoverinfo='none',
                          showlegend=False, showscale=False, colorscale=[[0, constants.YELLOW], [1, constants.YELLOW]]))

    fig.add_trace(go.Scatter3d(x=[0, 0], y=[0, 0], z=[-50, 50], mode='lines', hoverinfo='skip',
                               line=dict(color=constants.ORANGE, width=7)))
    fig.add_trace(go.Cone(x=[0], y=[0], z=[50], u=[0], v=[0], w=[cone_tip * (50 - 48)], hoverinfo='none',
                          showlegend=False, showscale=False, colorscale=[[0, constants.ORANGE], [1, constants.ORANGE]]))

    annot.append(dict(showarrow=False, text="X", x=65, y=0, z=0, font=dict(color=constants.GREEN, size=16)))
    annot.append(dict(showarrow=False, text="Y", x=0, y=65, z=0, font=dict(color=constants.YELLOW, size=16)))
    annot.append(dict(showarrow=False, text="Z", x=0, y=0, z=65, font=dict(color=constants.ORANGE, size=16)))

    fig.update_layout(scene=dict(xaxis=dict(backgroundcolor=constants.GREY2, gridcolor=constants.LIGHT_GREY2),
                                 yaxis=dict(backgroundcolor=constants.GREY2, gridcolor=constants.LIGHT_GREY2),
                                 zaxis=dict(backgroundcolor=constants.GREY2, gridcolor=constants.LIGHT_GREY2)))


@app.callback(
    [Output("main-graph", "figure"),
     Output("organs-checklist", "value")],
    Input("alignment-radioitems", "value"),
    Input("organs-checklist", "value"),
    Input("mode-radioitems", "value"),
    Input("fst-timestamp-dropdown", "value"),
    Input("snd-timestamp-dropdown", "value"),
    Input("heatmap-icp", "clickData"),
    Input("heatmap-center", "clickData"),
    Input("average-distances", "clickData"),
    Input("organ-distances", "clickData"),
    Input("alignment-differences", "clickData"))
def create_3dgraph(method, organs, mode, fst_timestamp, snd_timestamp, heatmap_icp, heatmap_center, average_distances,
                   organ_distances, differences):
    """
    Creates the 3D figure and visualises organs and bones. The last five arguments are just for updating the graph.
    :param method: ICP or prostate aligning registration method
    :param organs: organs selected by the user
    :param mode: showing either plan organs or organs in the two timestamps
    :param fst_timestamp: the first selected timestamp
    :param snd_timestamp: the second selected timestamp
    :return: the 3d figure
    """
    fst_timestamp = "_plan" if fst_timestamp == "plan" else fst_timestamp
    snd_timestamp = "_plan" if snd_timestamp == "plan" else snd_timestamp

    # if the user clicked on any of the mentioned graphs, the value will propagate to the 3D graph
    if "distances" in ctx.triggered_id or "heatmap" in ctx.triggered_id or "differences" in ctx.triggered_id:
        organs = [organ]

    objects_fst = import_selected_organs(organs, fst_timestamp, patient_id)
    objects_snd = import_selected_organs(organs, snd_timestamp, patient_id)

    camera = dict(up=dict(x=0, y=0, z=1), center=dict(x=0, y=0, z=0), eye=dict(x=0.5, y=-2, z=0))
    layout = go.Layout(font=dict(size=12, color='darkgrey'), paper_bgcolor='rgba(50,50,50,1)', uirevision=patient_id,
                       plot_bgcolor='rgba(50,50,50,1)', margin=dict(l=40, r=40, t=60, b=40), showlegend=True)
    fig = go.Figure(layout=layout)
    fig.update_layout(scene_camera=camera, scene=dict(xaxis_title='x [mm]', yaxis_title='y [mm]', zaxis_title='z [mm]'))

    fst_meshes, snd_meshes = \
        decide_3d_graph_mode(mode, fig, method, organs, fst_timestamp, snd_timestamp, objects_fst, objects_snd)

    for meshes in [fst_meshes, snd_meshes]:
        for mesh in meshes:
            mesh.update(cmin=-7, lightposition=dict(x=100, y=200, z=0),
                        lighting=dict(ambient=0.4, diffuse=1, fresnel=0.1, specular=1, roughness=0.5,
                                      facenormalsepsilon=1e-15, vertexnormalsepsilon=1e-15))
            fig.add_trace(mesh)

    return fig, organs


def import_selected_organs(organs, time_or_plan, patient):
    """
    Imports selected organs as .obj files.
    :param organs: selected organs
    :param time_or_plan: chosen timestamp or _plan suffix
    :param patient: id of the patient
    :return: imported objs
    """
    objects = []
    for organ in organs:
        objects.extend(registration_methods.import_obj([FILEPATH + "{}\\{}\\{}{}.obj"
                                                       .format(patient, organ.lower(), organ.lower(), time_or_plan)]))
    return objects


def decide_3d_graph_mode(mode, fig, method, organs, fst_timestamp, snd_timestamp, objects_fst, objects_snd):
    """
    Helper function to perform commands according to the chosen mode
    :param mode: showing either plan organs or organ in the two timestamps
    :param fig: 3D figure
    :param method: ICP or prostate aligning registration method
    :param organs: organs selected by the user
    :param fst_timestamp: the first selected timestamp
    :param snd_timestamp: the second selected timestamp
    :param objects_fst: organs from the first timestamp
    :param objects_snd: organs from the second timestamp
    :return: created meshes
    """
    fst_meshes, snd_meshes = [], []

    if "Two timestamps" in mode:
        fst_meshes, snd_meshes = \
            two_timestamps_mode(method, fst_timestamp, snd_timestamp, objects_fst, objects_snd)

        fst_timestamp = "plan organs" if "_plan" == fst_timestamp else "timestamp number {}".format(fst_timestamp)
        snd_timestamp = "plan organs" if "_plan" == snd_timestamp else "timestamp number {}".format(snd_timestamp)

        fig.update_layout(title_text="Patient {}, {} (pink) and {} (purple)"
                          .format(patient_id, fst_timestamp, snd_timestamp), title_x=0.5, title_y=0.95)

    else:
        objects = import_selected_organs(organs, "_plan", patient_id)
        fst_meshes = create_meshes_from_objs(objects, constants.PINK)
        fig.update_layout(title_text="Plan organs of patient {}".format(patient_id), title_x=0.5, title_y=0.95)

    return fst_meshes, snd_meshes


def two_timestamps_mode(method, fst_timestamp, snd_timestamp, objects_fst, objects_snd):
    """
    Helper to get the chosen meshes and align them according to the selected method.
    :param method: ICP or prostate centering
    :param fst_timestamp: number of the first selected timestamp
    :param snd_timestamp: number of the second selected timestamp
    :param objects_fst: objects imported in the time of the first timestamp
    :param objects_snd: objects imported in the time of the second timestamp
    :return: aligned meshes and center of the moved organs
    """
    fst_meshes, snd_meshes = [], []
    if "ICP" in method:
        meshes = get_meshes_after_icp(fst_timestamp, objects_fst, patient_id)
        fst_meshes.extend(meshes)
        meshes = get_meshes_after_icp(snd_timestamp, objects_snd, patient_id, constants.PURPLE)
        snd_meshes.extend(meshes)

    else:
        meshes = get_meshes_after_centering(fst_timestamp, objects_fst, patient_id, constants.PINK)
        fst_meshes.extend(meshes)
        meshes = get_meshes_after_centering(snd_timestamp, objects_snd, patient_id)
        snd_meshes.extend(meshes)

    return fst_meshes, snd_meshes


def get_meshes_after_icp(timestamp, objects, patient, color=constants.PINK):
    """
    Runs functions which perform the icp aligning.
    :param timestamp: chosen time
    :param objects: organ meshes
    :param patient: patient ID
    :param color: mesh color, the first mesh is pink, the second purple
    :return: meshes after aligning
    """

    plan_bones = registration_methods.import_obj([FILEPATH + "{}\\bones\\bones_plan.obj".format(patient)])
    bones = registration_methods.import_obj([FILEPATH + "{}\\bones\\bones{}.obj".format(patient, timestamp)])

    transform_matrix = registration_methods.icp_transformation_matrix(bones[0][0], plan_bones[0][0])
    transfr_objects = registration_methods.vertices_transformation(transform_matrix, deepcopy(objects))
    after_icp_meshes = create_meshes_from_objs(transfr_objects, color)

    return after_icp_meshes


def get_meshes_after_centering(timestamp, objects, patient, color=constants.PURPLE):
    """
    Runs functions which perform the prostate centring.
    :param timestamp: chosen time
    :param objects: organ meshes
    :param patient: patient ID
    :param color: mesh color, the first mesh is pink, the second purple
    :return: meshes after aligning
    """

    prostate = registration_methods.import_obj([FILEPATH + "{}\\prostate\\prostate{}.obj".format(patient, timestamp)])
    plan_center = registration_methods.find_center_of_mass(registration_methods.import_obj(
        [FILEPATH + "{}\\prostate\\prostate_plan.obj".format(patient)])[0][0])
    other_center = registration_methods.find_center_of_mass(prostate[0][0])

    center_matrix = registration_methods.create_translation_matrix(plan_center, other_center)
    center_transfr_objects = registration_methods.vertices_transformation(center_matrix, deepcopy(objects))
    after_center_meshes = create_meshes_from_objs(center_transfr_objects, color)

    return after_center_meshes


@app.callback(
    Output("x-slice-graph", "figure"),
    Output("y-slice-graph", "figure"),
    Output("z-slice-graph", "figure"),
    Input("x-slice-slider", "value"),
    Input("y-slice-slider", "value"),
    Input("z-slice-slider", "value"),
    Input("organs-checklist", "value"),
    Input("alignment-radioitems", "value"),
    Input("mode-radioitems", "value"),
    Input("fst-timestamp-dropdown", "value"),
    Input("snd-timestamp-dropdown", "value"))
def create_graph_slices(x_slider, y_slider, z_slider, organs, method, mode, fst_timestamp, snd_timestamp):
    """
    Creates three figures of slices made in the X, Y, and the Z axis direction. These figures are made according to the
    3D graph.
    :param x_slider: how far on the X axis normal we want to cut the slice
    :param y_slider: how far on the Y axis normal we want to cut the slice
    :param z_slider: how far on the Z axis normal we want to cut the slice
    :param organs: organs chosen for the 3D graph
    :param method: method of alignment in the 3D graph
    :param mode: mode from the 3D graph
    :param fst_timestamp: first timestamp chosen in the 3D graph
    :param snd_timestamp: second timestamp chosen in the 3D graph
    :return: the three slices figures
    """
    figures, fst_meshes, snd_meshes = [], [], []
    names = ["X axis slice - Sagittal", "Y axis slice - Coronal", "Z axis slice - Axial"]

    for i in range(3):
        layout = go.Layout(font=dict(size=12, color='darkgrey'), paper_bgcolor='rgba(50,50,50,1)', height=280,
                           width=320, plot_bgcolor='rgba(50,50,50,1)', margin=dict(l=40, r=30, t=60, b=60),
                           showlegend=False, title=dict(text=names[i], y=0.9))
        fig = go.Figure(layout=layout)
        fig.update_layout(title_x=0.5)
        figures.append(fig)

    if "Two timestamps" in mode:
        fst_timestamp = "_plan" if fst_timestamp == "plan" else fst_timestamp
        snd_timestamp = "_plan" if snd_timestamp == "plan" else snd_timestamp
        fst_meshes = two_slices_mode(method, patient_id, organs, fst_timestamp)
        snd_meshes = two_slices_mode(method, patient_id, organs, snd_timestamp)
    else:
        for organ_a in organs:
            fst_meshes.append(
                trimesh.load_mesh(FILEPATH + "{}\\{}\\{}_plan.obj".format(patient_id, organ_a.lower(),
                                                                          organ_a.lower())))

    x_fig = create_slice_final(x_slider, fst_meshes, snd_meshes, figures[0], "x")
    y_fig = create_slice_final(y_slider, fst_meshes, snd_meshes, figures[1], "y")
    z_fig = create_slice_final(z_slider, fst_meshes, snd_meshes, figures[2], "z")

    return x_fig, y_fig, z_fig


def two_slices_mode(method, patient, organs, timestamp):
    """
    Helper function to decide and perform the steps of the chosen method of alignment.
    :param method: method of the alignment
    :param patient: chosen patient id
    :param organs: organs chosen in the 3D graph
    :param timestamp: chosen time of the timestamp
    :return: aligned meshes
    """
    if "ICP" in method:
        plan_bones = registration_methods.import_obj([FILEPATH + "{}\\bones\\bones_plan.obj".format(patient)])
        bones = registration_methods.import_obj([FILEPATH + "{}\\bones\\bones{}.obj".format(patient, timestamp)])
        icp_matrix = registration_methods.icp_transformation_matrix(bones[0][0], plan_bones[0][0])
        meshes = selected_organs_slices(icp_matrix, patient, organs, timestamp)

    else:
        plan_prostate = trimesh.load_mesh(FILEPATH + "{}\\prostate\\prostate_plan.obj".format(patient))
        prostate = trimesh.load_mesh(FILEPATH + "{}\\prostate\\prostate{}.obj".format(patient, timestamp))
        key_center = registration_methods.find_center_of_mass(plan_prostate.vertices)
        other_center = registration_methods.find_center_of_mass(prostate.vertices)
        center_matrix = registration_methods.create_translation_matrix(key_center, other_center)
        meshes = selected_organs_slices(center_matrix, patient, organs, timestamp)

    return meshes


def selected_organs_slices(matrix, patient, organs, timestamp):
    """
    Applies the transformation to selected organs.
    :param matrix: acquired either from icp algorithm or centering on the prostate
    :param patient: chosen patient id
    :param organs: organs chosen in the 3D graph
    :param timestamp: chosen time of the timestamp
    :return: transformed meshes
    """
    meshes = []

    for organ_a in organs:
        mesh = trimesh.load_mesh(FILEPATH + "{}\\{}\\{}{}.obj".format(patient, organ_a.lower(), organ_a.lower(),
                                                                      timestamp))
        meshes.append(deepcopy(mesh).apply_transform(matrix))

    return meshes


def create_slice(mesh, slice_slider, params):
    """
    Creates the slices from the imported organs
    :param mesh: mesh of the selected organ
    :param slice_slider: where on the normal of the axis we want to make the slice
    :param params: parameters for the computation of the slice
    :return: created slices
    """
    min_val, max_val, plane_origin, plane_normal, axis = params
    slope = (max_val - 2.5) - (min_val + 0.5)

    if axis == "x":
        plane_origin[0] = (min_val + 0.5) + slope * slice_slider
    elif axis == "y":
        plane_origin[1] = (min_val + 0.5) + slope * slice_slider
    else:
        plane_origin[2] = (min_val + 0.5) + slope * slice_slider

    axis_slice = mesh.section(plane_origin=plane_origin, plane_normal=plane_normal)

    slices = []
    for entity in axis_slice.entities:
        ordered_slice = order_slice_vertices(axis_slice.vertices, entity.points)
        i, j, k = np.array(ordered_slice).T
        slices.append((i, j, k))

    return slices


def create_slice_helper(meshes, slice_slider, fig, color, axis):
    """
    Helper function for the axis creation and the creation of the slices traces for the figures.
    :param meshes: meshes of the selected organs
    :param slice_slider: where on the normal of the axis we want to make the slice
    :param fig: slice graph
    :param color: either pink or purple according to the slices order
    :param axis: which axis slice we are creating
    """
    for mesh in meshes:
        if axis == "x":
            params = mesh.bounds[0][0], mesh.bounds[1][0], [0, mesh.centroid[1], mesh.centroid[2]], [1, 0, 0], "x"
            slices = create_slice(mesh, slice_slider, params)
            for _, x, y in slices:
                fig.add_trace(go.Scatter(x=x, y=y, line=go.scatter.Line(color=color, width=3)))
            fig.update_xaxes(title="y [mm]", zeroline=False, gridcolor=constants.GREY)
            fig.update_yaxes(title="z [mm]", zeroline=False, gridcolor=constants.GREY)

        elif axis == "y":
            params = mesh.bounds[0][1], mesh.bounds[1][1], [mesh.centroid[0], 0, mesh.centroid[2]], [0, 1, 0], "y"
            slices = create_slice(mesh, slice_slider, params)
            for x, _, y in slices:
                fig.add_trace(go.Scatter(x=x, y=y, line=go.scatter.Line(color=color, width=3)))
            fig.update_xaxes(title="x [mm]", zeroline=False, gridcolor=constants.GREY)
            fig.update_yaxes(title="z [mm]", zeroline=False, gridcolor=constants.GREY)
        else:
            params = mesh.bounds[0][2], mesh.bounds[1][2], [mesh.centroid[0], mesh.centroid[1], 0], [0, 0, 1], "z"
            slices = create_slice(mesh, slice_slider, params)
            for x, y, _ in slices:
                fig.add_trace(go.Scatter(x=x, y=y, line=go.scatter.Line(color=color, width=3)))
            fig.update_xaxes(title="x [mm]", zeroline=False, gridcolor=constants.GREY)
            fig.update_yaxes(title="y [mm]", zeroline=False, gridcolor=constants.GREY)


def create_slice_final(slice_slider, icp_meshes, centered_meshes, fig, axis):
    """
    Calls the function to create the axis slices.
    :param slice_slider: where on the normal of the axis we want to make the slice
    :param icp_meshes: if we are using the icp alignment
    :param centered_meshes: if we are using the prostate centring
    :param fig: slice graph
    :param axis: which axis slice are we making
    :return slice figure
    """
    if icp_meshes:
        create_slice_helper(icp_meshes, slice_slider, fig, constants.PINK, axis)
    if centered_meshes:
        create_slice_helper(centered_meshes, slice_slider, fig, constants.PURPLE, axis)

    fig.update_xaxes(constrain="domain")
    fig.update_yaxes(scaleanchor="x")

    return fig


if __name__ == '__main__':
    app.run_server(debug=True)
