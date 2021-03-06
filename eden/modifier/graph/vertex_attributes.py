import numpy as np
from itertools import izip


def incident_edge_label(graph_list=None, output_attribute='type', separator='', level=1):
    """
    level: int
    level=1 considers all incident edges
    level=2 considers all edges incident on the neighbors
    """
    for g in graph_list:
        # iterate over nodes
        for n, d in g.nodes_iter(data=True):
            # for all neighbors
            edge_labels = []
            if level == 1:
                edge_labels += [ed.get('label', 'N/A') for u, v, ed in g.edges_iter(n, data=True)]
            elif level == 2:
                neighbors = g.neighbors(n)
                for nn in neighbors:
                    # extract list of edge labels
                    edge_labels += [ed.get('label', 'N/A') for u, v, ed in g.edges_iter(nn, data=True)]
            else:
                raise Exception('Unknown level: %s' % level)
            # consider the sorted serialization of all labels as a type
            vertex_type = separator.join(sorted(edge_labels))
            g.node[n][output_attribute] = vertex_type
        yield g


def incident_node_label(graph_list=None, output_attribute='type', separator='', level=1):
    """
    level: int
    level=1 considers all incident nodes
    level=2 considers all nodes incident on the neighbors
    """
    for g in graph_list:
        # iterate over nodes
        for n, d in g.nodes_iter(data=True):
            # for all neighbors
            node_labels = []
            if level == 1:
                node_labels += [g.node[u].get('label', 'N/A') for u in g.neighbors(n)]
            elif level == 2:
                neighbors = g.neighbors(n)
                for nn in neighbors:
                    # extract list of labels
                    node_labels += [g.node[u].get('label', 'N/A') for u in g.neighbors(nn)]
            else:
                raise Exception('Unknown level: %s' % level)
            # consider the sorted serialization of all labels as a type
            vertex_type = separator.join(sorted(node_labels))
            g.node[n][output_attribute] = vertex_type
        yield g


def translate(graph_list=None,
              input_attribute='label',
              output_attribute='label',
              label_map=dict(),
              default=' '):
    original_attribute = input_attribute + '_original'
    for g in graph_list:
        # iterate over nodes
        for n, d in g.nodes_iter(data=True):
            key = d.get(input_attribute, default)
            g.node[n][original_attribute] = key
            mapped_attribute = label_map.get(key, default)
            g.node[n][output_attribute] = mapped_attribute
        yield g


def colorize(graph_list=None, output_attribute='level', labels=['A', 'U', 'C', 'G'], mode=None):
    values = np.linspace(0.0, 1.0, num=len(labels))
    color_dict = dict(zip(labels, values))
    for g in graph_list:
        # iterate over nodes
        for n, d in g.nodes_iter(data=True):
            if mode == "3D":
                g.node[n][output_attribute] = color_dict.get(d['text_label'], 0)
            else:
                g.node[n][output_attribute] = color_dict.get(d['label'], 0)
        yield g


def colorize_binary(graph_list=None, output_attribute='color_value', input_attribute='weight', level=0):
    for g in graph_list:
        # iterate over nodes
        for n, d in g.nodes_iter(data=True):
            val = d.get(input_attribute, 0)
            if val <= level:
                color_value = 0
            else:
                color_value = 1
            g.node[n][output_attribute] = color_value
        yield g


def discretize(graph_list=None, output_attribute='value', input_attribute='weight', interval=0.1):
    for g in graph_list:
        # iterate over nodes
        for n, d in g.nodes_iter(data=True):
            val = d.get(input_attribute, 0)
            g.node[n][output_attribute] = int(val / interval)
        yield g


def _linear_trapezoidal_weight(pos,
                               high_weight=None,
                               low_weight=None,
                               interpolate_up_start=None,
                               interpolate_up_end=None,
                               interpolate_down_start=None,
                               interpolate_down_end=None):
    """
    Piecewise linear weight function between two levels with specified start end
    positions. This function linearly interpolates between positions
    interpolate_up_start and interpolate_up_end and between positions
    interpolate_down_start and interpolate_down_end where start and end points get
    high and low weights.

    This function does not check for parameter sanity.

              interpolate_up_end
              |
              | interpolate_down_start
              | |
    high      ___
             /   \
    low   __/     \__
           |       |
           |       interpolate_down_end
           |
           interpolate_up_start

    >>> _linear_trapezoidal_weight(pos=0,
    ...                            high_weight=1,
    ...                            low_weight=0,
    ...                            interpolate_up_end=3,
    ...                            interpolate_down_start=5,
    ...                            interpolate_up_start=1,
    ...                            interpolate_down_end=7)
    0
    >>> _linear_trapezoidal_weight(pos=1,
    ...                            high_weight=1,
    ...                            low_weight=0,
    ...                            interpolate_up_end=3,
    ...                            interpolate_down_start=5,
    ...                            interpolate_up_start=1,
    ...                            interpolate_down_end=7)
    0
    >>> _linear_trapezoidal_weight(pos=2,
    ...                            high_weight=1,
    ...                            low_weight=0,
    ...                            interpolate_up_end=3,
    ...                            interpolate_down_start=5,
    ...                            interpolate_up_start=1,
    ...                            interpolate_down_end=7)
    0.5
    >>> _linear_trapezoidal_weight(pos=3,
    ...                            high_weight=1,
    ...                            low_weight=0,
    ...                            interpolate_up_end=3,
    ...                            interpolate_down_start=5,
    ...                            interpolate_up_start=1,
    ...                            interpolate_down_end=7)
    1
    >>> _linear_trapezoidal_weight(pos=4,
    ...                            high_weight=1,
    ...                            low_weight=0,
    ...                            interpolate_up_end=3,
    ...                            interpolate_down_start=5,
    ...                            interpolate_up_start=1,
    ...                            interpolate_down_end=7)
    1
    >>> _linear_trapezoidal_weight(pos=5,
    ...                            high_weight=1,
    ...                            low_weight=0,
    ...                            interpolate_up_end=3,
    ...                            interpolate_down_start=5,
    ...                            interpolate_up_start=1,
    ...                            interpolate_down_end=7)
    1
    >>> _linear_trapezoidal_weight(pos=6,
    ...                            high_weight=1,
    ...                            low_weight=0,
    ...                            interpolate_up_end=3,
    ...                            interpolate_down_start=5,
    ...                            interpolate_up_start=1,
    ...                            interpolate_down_end=7)
    0.5
    >>> _linear_trapezoidal_weight(pos=7,
    ...                            high_weight=1,
    ...                            low_weight=0,
    ...                            interpolate_up_end=3,
    ...                            interpolate_down_start=5,
    ...                            interpolate_up_start=1,
    ...                            interpolate_down_end=7)
    0
    """
    if pos <= interpolate_up_start:
        """
           ___
        __/   \__
        |
        """
        return low_weight
    elif pos > interpolate_up_start and pos < interpolate_up_end:
        """
           ___
        __/   \__
          |
        """
        return (high_weight - low_weight) / float(interpolate_up_end - interpolate_up_start) * \
            (pos - interpolate_up_start) + low_weight
    elif pos >= interpolate_up_end and pos <= interpolate_down_start:
        """
           ___
        __/   \__
            |
        """
        return high_weight
    elif pos > interpolate_down_start and pos < interpolate_down_end:
        """
           ___
        __/   \__
              |
        """
        return high_weight - \
            (high_weight - low_weight) / float(interpolate_down_end - interpolate_down_start) * \
            (pos - interpolate_down_start)
    elif pos >= interpolate_down_end:
        """
           ___
        __/   \__
                |
        """
        return low_weight


def trapezoidal_reweighting(graph_list=None,
                            high_weight=1.0,
                            low_weight=0.1,
                            interpolate_up_start=0,
                            interpolate_up_end=1,
                            interpolate_down_start=0,
                            interpolate_down_end=1,
                            attribute='weight'):
    """
    Weight graphs via piecewise linear weight function between two levels with
    specified start end positions. This function linearly interpolates between
    positions interpolate_up_start and interpolate_up_end and between positions
    interpolate_down_start and interpolate_down_end where start and end points
    get high and low weights.

              interpolate_up_start
              |
              | interpolate_down_start
              | |
    high      ___
             /   \
    low   __/     \__
           |       |
           |       interpolate_down_end
           |
           interpolate_up_start
    """
# assert high_ weight > low_weight
    if high_weight < low_weight:
        raise Exception('high_weight (%f) must be higher than low_weight (%f)' % (high_weight, low_weight))

    # assert low_weight boundaries includes high_weight boundaries
    if interpolate_up_end > interpolate_down_end:
        raise Exception('interpolate_up_end (%d) must be lower than interpolate_down_end (%d)' %
                        (interpolate_up_end, interpolate_down_end))
    if interpolate_up_end < interpolate_up_start:
        raise Exception('interpolate_up_end (%d) must be higher than interpolate_up_start (%d)' %
                        (interpolate_up_end, interpolate_up_start))
    if interpolate_down_start < interpolate_up_start:
        raise Exception('interpolate_down_start (%d) must be higher than interpolate_up_start (%d)' %
                        (interpolate_down_start, interpolate_up_start))
    if interpolate_down_start > interpolate_down_end:
        raise Exception('interpolate_down_start (%d) must be higher than interpolate_down_end (%d)' %
                        (interpolate_down_start, interpolate_down_end))

    for g in graph_list:
        # iterate over nodes
        for n, d in g.nodes_iter(data=True):
            if 'position' not in d:
                # assert nodes must have position attribute
                raise Exception('Nodes must have "position" attribute')
            # given the 'position' attribute of node assign weight according to
            # piece wise linear weight function between two levels
            pos = d['position']
            g.node[n][attribute] = _linear_trapezoidal_weight(pos,
                                                              high_weight=high_weight,
                                                              low_weight=low_weight,
                                                              interpolate_up_end=interpolate_up_end,
                                                              interpolate_down_start=interpolate_down_start,
                                                              interpolate_up_start=interpolate_up_start,
                                                              interpolate_down_end=interpolate_down_end)
        yield g


def reweight(graph_list, weight_vector_list, attribute='weight'):
    """Assigns a value to the weight attribute of each node in each graph according to
    the information supplied in the list of vectors."""

    for g, w in izip(graph_list, weight_vector_list):
        # iterate over nodes
        for n, d in g.nodes_iter(data=True):
            if 'position' not in d:
                # assert nodes must have position attribute
                raise Exception('Nodes must have "position" attribute')
            # given the 'position' attribute of node assign the weight accordingly
            pos = d['position']
            g.node[n][attribute] = w[pos]
        yield g


def start_end_weight_reweight(graph, start_end_weight_list=None, attribute='weight'):
    for start, end, weight in start_end_weight_list:
        # iterate over nodes
        for n, d in graph.nodes_iter(data=True):
            if 'position' not in d:
                # assert nodes must have position attribute
                raise Exception('Nodes must have "position" attribute')
            # given the 'position' attribute of node assign the weight accordingly
            pos = d['position']
            if pos >= start and pos < end:
                graph.node[n][attribute] = weight
            if start == -1 and end == -1:
                graph.node[n][attribute] = weight
    return graph


def list_reweight(graph_list, start_end_weight_list=None, attribute='weight'):
    """Assign weights according to a list of triplets: each triplet defines the start, end position
    and the (uniform) weight of the region; the order of the triplets matters: later triplets override
    the weight specification of previous triplets. The special triplet (-1,-1,w) assign a default weight
    to all nodes."""

    for g in graph_list:
        g = start_end_weight_reweight(g, start_end_weight_list=start_end_weight_list, attribute=attribute)
        yield g


def listof_list_reweight(graph_list, listof_start_end_weight_list=None, attribute='weight'):
    """Assign weights according to a list of triplets: each triplet defines the start, end position
    and the (uniform) weight of the region; the order of the triplets matters: later triplets override
    the weight specification of previous triplets. The special triplet (-1,-1,w) assign a default weight
    to all nodes. Each element in listof_start_end_weight_list specifies the start_end_weight_list for a
    single graph."""

    for g, start_end_weight_list in izip(graph_list, listof_start_end_weight_list):
        g = start_end_weight_reweight(g, start_end_weight_list=start_end_weight_list, attribute=attribute)
        yield g
