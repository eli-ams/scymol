import functools
import os
import shutil
from typing import Any
from typing import List, Tuple
from typing import Union, Callable

import numpy as np
from numba import jit, prange
from pysimm import system
from rdkit import Chem
from rdkit.Chem import PDBWriter
from rdkit.Geometry import Point3D
from sobol_seq import i4_sobol_generate


def generate_sobol_positions(
    num_points: int, box_dims: Tuple[float, float, float]
) -> Tuple[List[float], List[float], List[float]]:
    """
    Generate Sobol sequence points within a given 3D box.

    :param num_points: The number of points to generate.
    :type num_points: int
    :param box_dims: Dimensions of the box (x_dim, y_dim, z_dim).
    :type box_dims: Tuple[float, float, float]
    :return: Three lists of x, y, and z coordinates.
    :rtype: Tuple[List[float], List[float], List[float]]
    """

    # Generate the Sobol sequence for the desired number of points [0,1]
    sobol_points = i4_sobol_generate(
        3, num_points
    )  # Assume the function is imported as needed

    # Transform the Sobol sequence to match the dimensions of the box
    for i in range(3):
        sobol_points[:, i] *= box_dims[i]

    return list(sobol_points[:, 0]), list(sobol_points[:, 1]), list(sobol_points[:, 2])


def clear_folder(folder_path: Union[str, os.PathLike]) -> None:
    """
    Delete all files and folders within the specified folder, then recreate the empty folder.

    :param folder_path: The path of the folder to clear.
    :type folder_path: Union[str, os.PathLike]
    :return: None
    """

    # Iterate through each item in the folder
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        # Remove files
        if os.path.isfile(file_path):
            os.remove(file_path)

        # Remove subdirectories
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)

    # Recreate the empty folder
    os.makedirs(folder_path, exist_ok=True)


def molobj_to_pdb(molecule_object: Any, filename: str) -> None:
    """
    Write the molecular structure to a PDB (Protein Data Bank) file.

    :param molecule_object: The molecule object to write.
    :type molecule_object: Any
    :param filename: The name of the output PDB file.
    :type filename: str
    :return: None
    """

    # Initialize PDB writer and write the molecule object
    with PDBWriter(
        filename
    ) as writer:  # Using 'with' ensures that writer.close() is called automatically
        writer.write(molecule_object)


def split_number(number_str: str, right_part_length: int) -> tuple:
    """
    Split a string representation of a number into left and right parts.

    :param number_str: The string representation of the number.
    :type number_str: str
    :param right_part_length: The length of the right part to extract.
    :type right_part_length: int
    :return: A tuple containing the left part and the right part of the string.
    :rtype: tuple
    """
    left_part: str = number_str[:-right_part_length]
    right_part: str = number_str[-right_part_length:]
    return left_part, right_part


def fix_mol_file(file: str) -> None:
    """
    Fix a Molecular Structure File (MOL file) by making specific modifications.

    :param file: The path to the MOL file to be fixed.
    :type file: str
    :return: None
    """
    nbr_of_atoms: int = 0
    nbr_of_bonds: int = 0

    # Get the full path of the input file
    full_path: str = os.path.abspath(file)
    # Get the directory name from the full path
    directory_name: str = os.path.dirname(full_path)
    # Create the full path for the output file
    write_file_path: str = os.path.join(directory_name, "fixed.mol")

    with open(file=full_path, mode="r") as read_file, open(
        write_file_path, "w"
    ) as write_file:
        for line in read_file:
            line_split = line.split()
            if len(line_split) == 10:
                left_part, right_part = split_number(
                    number_str=line_split[0], right_part_length=3
                )
                line_split[0] = " ".join([left_part, right_part])
                write_file.write(" ".join(line_split) + "\n")
            elif len(line_split) == 16:
                nbr_of_atoms += 1
                write_file.write(line)
            elif len(line_split) == 4:
                nbr_of_bonds += 1
                write_file.write(line)
            elif len(line_split) == 3:
                nbr_of_bonds += 1
                left_part, right_part = split_number(
                    number_str=line_split[0], right_part_length=3
                )
                line_split[0] = " ".join([left_part, right_part])
                write_file.write(" " + " ".join(line_split) + "\n")
            else:
                write_file.write(line)

    # Replace the original MOL file with the fixed file
    os.replace(write_file_path, full_path)


def translate_molecule(mol_obj: Any, x: float, y: float, z: float) -> None:
    """
    Translate the coordinates of all atoms in a molecule by specified x, y, and z distances.

    :param mol_obj: The molecule object to translate.
    :type mol_obj: Any
    :param x: The distance to translate along the x-axis.
    :type x: float
    :param y: The distance to translate along the y-axis.
    :type y: float
    :param z: The distance to translate along the z-axis.
    :type z: float
    :return: None
    """

    # Retrieve the conformer and number of atoms
    conformer = mol_obj.GetConformer()
    num_atoms = mol_obj.GetNumAtoms()

    # Loop through each atom to update its position
    for i in range(num_atoms):
        position = conformer.GetAtomPosition(i)
        new_position = Point3D(position.x + x, position.y + y, position.z + z)
        conformer.SetAtomPosition(i, new_position)


def extract_atom_positions_from_mol_obj_list(
    mol_obj_list: List[Any],
) -> Tuple[List[float], List[float], List[float]]:
    """
    Extract x, y, and z atomic coordinates from a list of molecule objects.

    :param mol_obj_list: A list of molecule objects.
    :type mol_obj_list: List[Any]
    :return: Lists of x, y, and z coordinates for all atoms in all molecules.
    :rtype: Tuple[List[float], List[float], List[float]]
    """

    atoms_pos_x, atoms_pos_y, atoms_pos_z = [], [], []

    # Loop through each molecule object in the list
    for mol in mol_obj_list:
        conf = mol.GetConformer()

        # Loop through each atom in the molecule
        for atom in mol.GetAtoms():
            pos = conf.GetAtomPosition(atom.GetIdx())
            atoms_pos_x.append(pos.x)
            atoms_pos_y.append(pos.y)
            atoms_pos_z.append(pos.z)

    return atoms_pos_x, atoms_pos_y, atoms_pos_z


@jit(nopython=True)
def lennard_jones_potential(
    rij: float, epsilon: float = 1.0, sigma: float = 1.0
) -> float:
    """
    Calculate the Lennard-Jones potential between two particles separated by a distance rij.

    :param rij: The separation distance between two particles.
    :type rij: float
    :param epsilon: The depth of the potential well, defaults to 1.0.
    :type epsilon: float, optional
    :param sigma: The finite distance where the inter-particle potential is zero, defaults to 1.0.
    :type sigma: float, optional
    :return: The Lennard-Jones potential energy.
    :rtype: float
    """

    return 4.0 * epsilon * ((sigma / rij) ** 12 - (sigma / rij) ** 6)


@jit(nopython=True)
def compute_distance(
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
    box_dimensions: Tuple[float, float, float],
) -> float:
    """
    Compute the distance between two points with periodic boundary conditions.

    :param x1, y1, z1: Coordinates of the first point.
    :param x2, y2, z2: Coordinates of the second point.
    :param box_dimensions: Dimensions of the periodic box.
    :type box_dimensions: Tuple[float, float, float]
    :return: The distance between the two points.
    :rtype: float
    """

    dx = x1 - x2
    dy = y1 - y2
    dz = z1 - z2

    # Apply periodic boundary conditions
    dx = dx - box_dimensions[0] * np.round(dx / box_dimensions[0])
    dy = dy - box_dimensions[1] * np.round(dy / box_dimensions[1])
    dz = dz - box_dimensions[2] * np.round(dz / box_dimensions[2])

    # Calculate squared distance
    r_squared = dx**2 + dy**2 + dz**2

    return np.sqrt(r_squared)


@jit(nopython=True, parallel=True)
def compute_total_lj_potential(x, y, z, box_dimensions, rcut: float) -> float:
    """
    Compute the total Lennard-Jones potential energy of a system of particles.

    :param x, y, z: Lists containing the coordinates of the particles.
    :param box_dimensions: Dimensions of the periodic box.
    :type box_dimensions: Tuple[float, float, float]
    :param rcut: Cutoff distance for interactions.
    :type rcut: float
    :return: The total Lennard-Jones potential energy of the system.
    :rtype: float
    """

    n_particles = len(x)
    total_potential_energy = 0.0

    # Parallel loop over all pairs of particles
    for i in prange(n_particles):
        for j in prange(i + 1, n_particles):
            r = compute_distance(x[i], y[i], z[i], x[j], y[j], z[j], box_dimensions)
            if r < rcut:
                total_potential_energy += lennard_jones_potential(r)

    return total_potential_energy


def add_molecules_by_type(
    working_dir: str, molecule_properties: dict, ff: str, pysimm_system: Any
) -> Any:
    """
    Add molecules of a certain type to a simulation system.

    :param working_dir: The working directory for temporary files.
    :type working_dir: str
    :param molecule_properties: Properties of the molecules.
    :type molecule_properties: dict
    :param ff: The force field for the simulation.
    :type ff: str
    :param pysimm_system: The simulation system.
    :type pysimm_system: Any
    :return: The updated simulation system.
    :rtype: Any
    """
    parent_mol = None

    for n in range(molecule_properties["nbr_of_mols"]):
        # Export molecule object into a temporary MOL file:
        Chem.MolToMolFile(
            molecule_properties["duplicate_objects"][n], f"{working_dir}temp.mol"
        )
        fix_mol_file(file=f"{working_dir}temp.mol")

        if pysimm_system is None:  # Creating a new pySIMM system:
            pysimm_system = load_molecule_with_forcefield(f"{working_dir}temp.mol", ff)
            parent_mol = load_molecule_with_forcefield(f"{working_dir}temp.mol", ff)
        else:
            if parent_mol is None:  # New molecule type
                parent_mol_tmp = load_molecule_with_forcefield(
                    f"{working_dir}temp.mol", ff
                )
                parent_mol = parent_mol_tmp.copy()
                pysimm_system.add(parent_mol_tmp, change_dim=True)
            else:
                copy_of_parent_mol = parent_mol.copy()
                # Duplicate and adjust positions of the parent molecule:
                duplicate_mol = system.read_mol(f"{working_dir}temp.mol")

                copy_of_parent_mol = apply_positions(copy_of_parent_mol, duplicate_mol)
                pysimm_system.add(copy_of_parent_mol, change_dim=True)

    return pysimm_system


def load_molecule_with_forcefield(mol_file: str, forcefield: str) -> Any:
    """
    Load a molecule from a file and apply a forcefield.

    :param mol_file: The path to the molecule file.
    :type mol_file: str
    :param forcefield: The forcefield to apply.
    :type forcefield: str
    :return: The molecule system with the applied forcefield.
    :rtype: Any
    """
    mol_system = system.read_mol(mol_file)
    mol_system.apply_forcefield(forcefield)
    return mol_system


def apply_positions(system1: Any, system2: Any) -> Any:
    """
    Copy positions from one system to another.

    :param system1: The destination system for the positions.
    :type system1: Any
    :param system2: The source system for the positions.
    :type system2: Any
    :return: The destination system with updated positions.
    :rtype: Any
    """
    for p1, p2 in zip(system1.particles, system2.particles):
        p1.x, p1.y, p1.z = p2.x, p2.y, p2.z
    return system1


def log_function_call(func: Callable) -> Callable:
    """
    Decorator to log the name of a function when it is called, including class name if applicable.

    :param func: The function to be wrapped.
    :type func: Callable

    :return: The wrapped function.
    :rtype: Callable
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check if the function is a method of a class
        if args and hasattr(args[0], "__class__"):
            class_name = args[0].__class__.__name__
            func_name = f"{class_name}.{func.__name__}"
            is_method = True
        else:
            func_name = func.__name__
            is_method = False

        logging.info(func_name)

        # Adjust arguments for class methods, skipping 'self'
        if is_method:
            arg_count = func.__code__.co_argcount - 1
            args = args[: arg_count + 1]

        return func(*args, **kwargs)

    return wrapper
