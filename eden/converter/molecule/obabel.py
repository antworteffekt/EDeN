import openbabel as ob
import pybel
import networkx as nx
import scipy.spatial.distance
import numpy as np
import subprocess
import shlex
from eden.util import read
from itertools import tee, groupby
import random


def mol_file_to_iterable(filename=None, file_format=None):
    if file_format == 'sdf':
        with open(filename) as f:
            s = ''
            for line in f:
                if line.strip() != '$$$$':
                    s = s + line
                else:
                    return_value = s + line
                    s = ''
                    yield return_value
    elif file_format == 'smi':
        with open(filename) as f:
            for line in f:
                yield line
    else:
        raise Exception('ERROR: unrecognized file format: %s' % file_format)


def obabel_to_eden(iterable, file_format='sdf', **options):
    """
    Takes a string list in sdf format format and yields networkx graphs.

    Parameters
    ----------
    iterable : SMILES strings containing molecular structures.

    """
    def smi_has_error(smi):
        smi = smi.strip()
        n_open_parenthesis = sum(1 for c in smi if c == '(')
        n_close_parenthesis = sum(1 for c in smi if c == ')')
        n_open_parenthesis_square = sum(1 for c in smi if c == '[')
        n_close_parenthesis_square = sum(1 for c in smi if c == ']')
        return (n_open_parenthesis != n_close_parenthesis) or \
            (n_open_parenthesis_square != n_close_parenthesis_square)

    if file_format == 'sdf':
        for mol_sdf in read(iterable):
            mol = pybel.readstring("sdf", mol_sdf.strip())
            # remove hydrogens
            mol.removeh()
            graph = obabel_to_networkx(mol)
            if len(graph):
                yield graph
    elif file_format == 'smi':
        for mol_smi in read(iterable):
            if smi_has_error(mol_smi) is False:
                mol = pybel.readstring("smi", mol_smi.strip())
                # remove hydrogens
                mol.removeh()
                graph = obabel_to_networkx(mol)
                if len(graph):
                    graph.graph['info'] = mol_smi.strip()
                    yield graph
    else:
        raise Exception('ERROR: unrecognized file format: %s' % file_format)


def obabel_to_networkx(mol):
    """
    Takes a pybel molecule object and converts it into a networkx graph.
    """
    graph = nx.Graph()
    # atoms
    for atom in mol:
        node_id = atom.idx - 1
        label = str(atom.type)
        graph.add_node(node_id, label=label)
    # bonds
    for bond in ob.OBMolBondIter(mol.OBMol):
        label = str(bond.GetBO())
        graph.add_edge(
            bond.GetBeginAtomIdx() - 1, bond.GetEndAtomIdx() - 1, label=label)
    return graph


##########################################################################

def obabel_to_eden3d(iterable, file_format='sdf', conformers_from_file=True,
                     cache={}, split_components=True, **kwargs):
    """
    Takes an iterable file and yields the corresponding networkx graphs.

    **kwargs: arguments to be passed to other methods.
    """

    n_conf = kwargs.get('n_conf', 1)

    if file_format == 'sdf':
        if conformers_from_file:

            if split_components:  # yield every graph separately
                for k, g in groupby(read(iterable), lambda x: pybel.readstring('sdf', x).data['PUBCHEM_COMPOUND_CID']):
                    molecules = []
                    for mol_sdf in g:
                        molecule = pybel.readstring('sdf', mol_sdf)
                        molecule.removeh()
                        molecules.append(molecule)
                    if len(molecules) > n_conf:
                        molecules = molecules[0:n_conf]
                    for molecule in molecules:
                        graph = obabel_to_networkx3d(molecule, **kwargs)
                        if len(graph):
                            yield graph

            else:  # construct a global graph and accumulate everything there
                global_graph = nx.Graph()

                for k, g in groupby(read(iterable), lambda x: pybel.readstring('sdf', x).data['PUBCHEM_COMPOUND_CID']):
                    molecules = []
                    for mol_sdf in g:
                        molecule = pybel.readstring('sdf', mol_sdf)
                        molecule.removeh()
                        molecules.append(molecule)
                    if len(molecules) > n_conf:
                        molecules = molecules[0:n_conf]

                    for molecule in molecules:
                        graph = obabel_to_networkx3d(molecule, **kwargs)
                        if len(graph):
                            global_graph = nx.disjoint_union(
                                global_graph, graph)

                    yield global_graph

        else:
            if split_components:  # yield every graph separately
                for mol_sdf in read(iterable):
                    mol = pybel.readstring("sdf", mol_sdf)
                    mols = generate_conformers(mol.write("sdf"), n_conf)
                    for molecule in mols:
                        molecule.removeh()
                        graph = obabel_to_networkx3d(molecule, **kwargs)
                        if len(graph):
                            yield graph
            else:  # construct a global graph and accumulate everything there
                global_graph = nx.Graph()
                for mol_sdf in read(iterable):
                    mol = pybel.readstring("sdf", mol_sdf)
                    mols = generate_conformers(mol.write("sdf"), n_conf)
                    for molecule in mols:
                        molecule.removeh()
                        g = obabel_to_networkx3d(molecule, **kwargs)
                        if len(g):
                            global_graph = nx.disjoint_union(global_graph, g)
                yield global_graph

    elif file_format == 'smi':
        if split_components:  # yield every graph separately
            for mol_smi in read(iterable):
                # First check if the molecule has appeared before and thus is
                # already converted
                if mol_smi not in cache:
                    # convert from SMILES to SDF and store in cache
                    command_string = 'obabel -:"' + mol_smi + '" -osdf --gen3d'
                    args = shlex.split(command_string)
                    sdf = subprocess.check_output(args)
                    # Assume the incoming string contains only one molecule
                    # Remove warning messages generated by openbabel
                    sdf = '\n'.join(
                        [x for x in sdf.split('\n') if 'WARNING' not in x])
                    cache[mol_smi] = sdf

                mols = generate_conformers(cache[mol_smi], n_conf)
                for molecule in mols:
                    graph = obabel_to_networkx3d(molecule, **kwargs)
                    if len(graph):
                        yield graph

        else:  # construct global graph and accumulate everything there
            global_graph = nx.Graph()
            for mol_smi in read(iterable):
                # First check if the molecule has appeared before and thus is
                # already converted
                if mol_smi not in cache:
                    # convert from SMILES to SDF and store in cache
                    command_string = 'obabel -:"' + mol_smi + '" -osdf --gen3d'
                    args = shlex.split(command_string)
                    sdf = subprocess.check_output(args)
                    sdf = '\n'.join(
                        [x for x in sdf.split('\n') if 'WARNING' not in x])
                    cache[mol_smi] = sdf

                mols = generate_conformers(cache[mol_smi], n_conf)
                for molecule in mols:
                    g = obabel_to_networkx3d(molecule, **kwargs)
                    if len(g):
                        global_graph = nx.disjoint_union(global_graph, g)
            yield global_graph

    else:
        raise Exception('ERROR: unrecognized file format: %s' % file_format)


def obabel_to_networkx3d(input_mol, **kwargs):
    # similarity_fn, atom_types=None, k=3, threshold=0):
    """
    Takes a pybel molecule object and converts it into a networkx graph.

    :param input_mol: A molecule object
    :type input_mol: pybel.Molecule
    :param atom_types: A list containing the atomic number of atom types to be
     looked for in the molecule
    :type atom_types: list or None
    :param k: The number of nearest neighbors to be considered
    :type k: int
    :param label_name: the name to be used for the neighbors attribute
    :type label_name: string
    """

    graph = nx.Graph()
    graph.graph['info'] = str(input_mol).strip()

    method = kwargs.get('method', 'metric')

    # Calculate pairwise distances between all atoms:
    coords = []
    for atom in input_mol:
        coords.append(atom.coords)

    coords = np.asarray(coords)
    distances = scipy.spatial.distance.squareform(
        scipy.spatial.distance.pdist(coords))

    # Find the nearest neighbors for each atom
    for atom in input_mol:
        atomic_no = str(atom.atomicnum)
        atom_type = str(atom.type)
        node_id = atom.idx - 1
        graph.add_node(node_id)
        if method == "metric":
            graph.node[node_id]['label'] = find_nearest_neighbors(
                input_mol, distances, atom.idx, **kwargs)
        elif method == "topological":
            graph.node[node_id]['label'] = calculate_local_density(
                input_mol, distances, atom.idx, **kwargs)
        graph.node[node_id]['discrete_label'] = atomic_no
        graph.node[node_id]['atom_type'] = atom_type
        graph.node[node_id]['ID'] = node_id

    for bond in ob.OBMolBondIter(input_mol.OBMol):
        label = str(bond.GetBO())
        graph.add_edge(bond.GetBeginAtomIdx() - 1,
                       bond.GetEndAtomIdx() - 1,
                       label=label)
    # print "current graph edges: "
    # print g.edges()
    return graph


def find_nearest_neighbors(mol, distances, current_idx, **kwargs):

    # Most common elements in our galaxy with atomic number:
    # 1 Hydrogen
    # 2 Helium
    # 8 Oxygen
    # 6 Carbon
    # 10 Neon
    # 26 Iron
    # 7 Nitrogen
    # 14 Silicon
    # 12 Magnesium
    # 16 Sulfur
    atom_types = kwargs.get('atom_types', [1, 2, 8, 6, 10, 26, 7, 14, 12, 16])
    similarity_fn = kwargs.get('similarity_fn', lambda x: 1. / (x + 1))
    k = kwargs.get('k', 3)
    threshold = kwargs.get('threshold', 0)
    sorted_indices = np.argsort(distances[current_idx - 1, ])

    # Obs: nearest_atoms will contain the atom index, which starts in 0
    nearest_atoms = []

    for atomic_no in atom_types:
        # Don't remove current atom from list:
        atom_idx = [atom.idx for atom in mol if atom.atomicnum == atomic_no]
        # Indices cannot be compared directly with idx
        if len(atom_idx) >= k:
            nearest_atoms.append(
                [id for id in sorted_indices if id + 1 in atom_idx][:k])
        else:
            nearest_atoms.append(
                [id for id in sorted_indices if id + 1 in atom_idx] +
                [None] * (k - len(atom_idx)))

    # The following expression flattens the list
    nearest_atoms = [x for sublist in nearest_atoms for x in sublist]
    # Replace idx for distances, assign an arbitrarily large distance for None
    nearest_atoms = [distances[current_idx - 1, i]
                     if i is not None else 1e10 for i in nearest_atoms]
    # If a threshold value is entered, filter the list of distances
    if threshold > 0:
        nearest_atoms = [x if x <= threshold else 1e10 for x in nearest_atoms]
    # Finally apply the similarity function to the resulting list and return
    nearest_atoms = [similarity_fn(x) if similarity_fn(
        x) > np.spacing(1e10) else 0 for x in nearest_atoms]

    return nearest_atoms


def calculate_local_density(mol, distances, current_idx, **kwargs):

    max_dist = kwargs.get('max_dist', 10)
    n_intervals = kwargs.get('n_intervals', 20)

    thresholds = np.linspace(0, max_dist, n_intervals)
    mol_size = len(mol.atoms)
    density_values = []

    current_distances = distances[current_idx - 1, ]
    for t in thresholds:
        density_values.append(
            len([x for x in current_distances if x <= t]) / float(mol_size))
    # Append the current atom's atomic number at the beginning of the list:
    # density_values.insert(0, mol.atoms[current_idx - 1].atomicnum)

    return density_values


def generate_conformers(input_sdf, n_conf=10, method="rmsd"):
    """
    Given an input sdf string, call obabel to construct a specified number of
    conformers.
    """
    import subprocess
    import pybel as pb
    import re

    if n_conf == 0:
        return [pb.readstring("sdf", input_sdf)]

    command_string = 'echo "%s" | obabel -i sdf -o sdf --conformer --nconf %d\
    --score rmsd --writeconformers 2>&-' % (input_sdf, n_conf)
    sdf = subprocess.check_output(command_string, shell=True)
    # Clean the resulting output
    first_match = re.search('OpenBabel', sdf)
    clean_sdf = sdf[first_match.start():]
    # Accumulate molecules in a list
    mols = []
    # Each molecule in the sdf output begins with the 'OpenBabel' string
    matches = list(re.finditer('OpenBabel', clean_sdf))
    for i in range(len(matches) - 1):
        # The newline at the beginning is needed for obabel to recognize the
        # sdf format
        mols.append(
            pb.readstring(
                "sdf",
                '\n' + clean_sdf[matches[i].start():matches[i + 1].start()]))

    mols.append(pb.readstring("sdf", '\n' + clean_sdf[matches[-1].start():]))
    return mols


def graph_to_molfile(graph):
    # Atom symbols listed by atomic number - will be needed below:
    symbols = {'1': 'H',
               '2': 'He',
               '3': 'Li',
               '4': 'Be',
               '5': 'B',
               '6': 'C',
               '7': 'N',
               '8': 'O',
               '9': 'F',
               '10': 'Ne',
               '11': 'Na',
               '12': 'Mg',
               '13': 'Al',
               '14': 'Si',
               '15': 'P',
               '16': 'S',
               '17': 'Cl',
               '18': 'Ar',
               '19': 'K',
               '20': 'Ca',
               '21': 'Sc',
               '22': 'Ti',
               '23': 'V',
               '24': 'Cr',
               '25': 'Mn',
               '26': 'Fe',
               '27': 'Co',
               '28': 'Ni',
               '29': 'Cu',
               '30': 'Zn',
               '31': 'Ga',
               '32': 'Ge',
               '33': 'As',
               '34': 'Se',
               '35': 'Br',
               '36': 'Kr',
               '37': 'Rb',
               '38': 'Sr',
               '39': 'Y',
               '40': 'Zr',
               '41': 'Nb',
               '42': 'Mo',
               '43': 'Tc',
               '44': 'Ru',
               '45': 'Rh',
               '46': 'Pd',
               '47': 'Ag',
               '48': 'Cd',
               '49': 'In',
               '50': 'Sn',
               '51': 'Sb',
               '52': 'Te',
               '53': 'I',
               '54': 'Xe',
               '55': 'Cs',
               '56': 'Ba',
               '57': 'La',
               '58': 'Ce',
               '59': 'Pr',
               '60': 'Nd',
               '61': 'Pm',
               '62': 'Sm',
               '63': 'Eu',
               '64': 'Gd',
               '65': 'Tb',
               '66': 'Dy',
               '67': 'Ho',
               '68': 'Er',
               '69': 'Tm',
               '70': 'Yb',
               '71': 'Lu',
               '72': 'Hf',
               '73': 'Ta',
               '74': 'W',
               '75': 'Re',
               '76': 'Os',
               '77': 'Ir',
               '78': 'Pt',
               '79': 'Au',
               '80': 'Hg',
               '81': 'Tl',
               '82': 'Pb',
               '83': 'Bi',
               '84': 'Po',
               '85': 'At',
               '86': 'Rn',
               '87': 'Fr',
               '88': 'Ra',
               '89': 'Ac',
               '90': 'Th',
               '91': 'Pa',
               '92': 'U',
               '93': 'Np',
               '94': 'Pu',
               '95': 'Am',
               '96': 'Cm',
               '97': 'Bk',
               '98': 'Cf',
               '99': 'Es',
               '100': 'Fm',
               '101': 'Md',
               '102': 'No',
               '103': 'Lr',
               '104': 'Rf',
               '105': 'Db',
               '106': 'Sg',
               '107': 'Bh',
               '108': 'Hs',
               '109': 'Mt',
               '110': 'Ds',
               '111': 'Rg',
               '112': 'Uub',
               '113': 'Uut',
               '114': 'Uuq',
               '115': 'Uup',
               '116': 'Uuh',
               '117': 'Uus',
               '118': 'Uuo'}

    # creating an SDF file from graph:
    # The header block, i.e. the first three lines, may be empty:
    sdf_string = "Networkx graph to molfile\n\n\n"

    # After the header block comes the connection table:
    # First the counts line - step by step
    counts_line = ""
    # Number of atoms
    counts_line += str(len(graph.nodes())).rjust(3)
    # Number of bonds
    counts_line += str(len(graph.edges())).rjust(3)
    # Number of atom lists
    counts_line += '  0'
    # Three blank spaces, then the chirality flag
    counts_line += '     1'
    # Five identical blocks
    counts_line += '  0' * 5
    # Finish with 0999 V2000
    counts_line += '999 V2000\n'
    sdf_string += counts_line

    # Atom block - this contains one atom line per atom in the molecule
    for n, d in graph.nodes_iter(data=True):
        atom_line = ''
        # Set all coordinates to 0
        atom_line += '    0.0000    0.0000    0.0000 '
        # Atom symbol: it should be the entry from the periodic table, using
        # atom type for now
        atom_line += symbols.get(d['discrete_label']).ljust(3)
        # Lots of unnecessary atomic information:
        atom_line += ' 0  0  0  0  0  0  0  0  0  0  0  0\n'
        sdf_string += atom_line

    # Bond block
    for i, j, k in graph.edges_iter(data=True):
        edge_line = ''
        # Use the stored atom ids for the bonds, plus one
        edge_line += str(i + 1).rjust(3) + \
            str(j + 1).rjust(3) + k['label'].rjust(3)
        # More information
        edge_line += '  0  0  0  0\n'
        sdf_string += edge_line

    sdf_string += 'M END\n\n$$$$'

    return sdf_string


def flip_node_labels(orig_graph, new_label_name, old_label_name):
    '''
    :param graph: a networkx graph object. The data dictionaries in its nodes
    will be used
    :param new_label_name: the dict key that will be converted to the new label
    :param old_label_name: the dict key the current label will obtain

    '''
    import networkx as nx
    from copy import deepcopy

    graph = deepcopy(orig_graph)
    # If the specified new label name doesn't exist, assume
    # that it is already the main label - do nothing
    if new_label_name not in graph.node[graph.nodes()[0]].keys():
        return graph
    else:
        # Extract data from old label
        old_label_data = dict([(n, d['label'])
                               for n, d in graph.nodes_iter(data=True)])
        # Extract data from new label
        new_label_data = dict([(n, d[new_label_name])
                               for n, d in graph.nodes_iter(data=True)])
        # Swap the information
        nx.set_node_attributes(graph, 'label', new_label_data)
        nx.set_node_attributes(graph, old_label_name, old_label_data)
        # Delete information corresponding to the old label name,
        # as it will be redundant.
        for id, node in graph.nodes(data=True):
            del node[new_label_name]

        return graph


def selection_iterator(iterable, ids, multiple_conformers=True):
    '''Given an iterable and a list of ids (zero based) yield only the items whose id matches'''
    if multiple_conformers:
        for item in iterable:
            if pybel.readstring('sdf', item).data['PUBCHEM_COMPOUND_CID'] in ids:
                yield item
    else:
        local_ids = ids[:]
        for item in iterable:
            current_cid = pybel.readstring(
                'sdf', item).data['PUBCHEM_COMPOUND_CID']
            if current_cid in local_ids:
                local_ids.remove(current_cid)
                yield item


def random_bipartition_conformers(iterable, relative_size):

    iterable_train, iterable_test, iterable_ids = tee(iterable, 3)

    ids = [k for k, g in groupby(iterable_ids, lambda x: pybel.readstring(
        'sdf', x).data['PUBCHEM_COMPOUND_CID'])]

    random.shuffle(ids)
    split_point = int(relative_size * len(ids))
    train_ids, test_ids = ids[:split_point], ids[split_point:]

    no_confs_train, w_confs_train = tee(iterable_train)
    iter_train_no_confs = selection_iterator(no_confs_train, train_ids, multiple_conformers=False)
    iter_train_w_confs = selection_iterator(w_confs_train, train_ids, multiple_conformers=True)

    no_confs_test, w_confs_test = tee(iterable_test)
    iter_test_no_confs = selection_iterator(no_confs_test, test_ids, multiple_conformers=False)
    iter_test_w_confs = selection_iterator(w_confs_test, test_ids, multiple_conformers=True)

    return iter_train_no_confs, iter_test_no_confs, iter_train_w_confs, iter_test_w_confs
