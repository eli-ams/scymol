import copy
import importlib
from typing import List
import numpy as np
from pysimm import forcefield
from rdkit import Chem
import scymol.backend.backend_static_functions as backend_static_functions
import scymol.backend.inputs as inputs
from scymol.backend.molecule import Molecule


class Mixture:
    _id: int = 0  # Class variable to keep track of the number of Mixture instances

    def __init__(self) -> None:
        """
        Initialize a new Mixture instance.

        This constructor sets initial attributes, resets molecule counters, populates
        molecules based on a global dictionary, updates mixture information, generates
        Sobol positions, and initializes other attributes.

        Returns:
            None
        """
        Molecule.reset_counters()
        Mixture._id += 1
        self.potential_energy: float = 0
        self.nbr_of_mols: int = 0
        self.weight: float = 0
        self.mw_gmol: float = 0
        self.box_dims: List[float] = [0, 0, 0]
        self.box_final_cubic_dim: float = 0
        self.molecules: List[Molecule] = []
        self.molecules_set: List[Molecule] = []

        # Populate molecules based on global dictionary
        self._populate_molecules()

        # Update mixture information
        self.update_mixture_information()

        self.sobol_x = []
        self.sobol_y = []
        self.sobol_z = []

        # Generate Sobol positions
        self.generate_sobol_positions()

        self.accepted = False

        # Initialize force field based on inputs
        self.forcefield = getattr(forcefield, inputs.use_forcefield)()

        # Initialize force field chagres based on inputs
        self.charges = inputs.charges

    def _populate_molecules(self) -> None:
        """
        Populate the list of molecules based on the global dictionary.

        Returns:
            None
        """
        for key, value in inputs.molecules_dictionary.items():
            self.molecules.append(Molecule(name=key, info=value))
            self.molecules_set.append(self.molecules[-1])
            for _ in range(value["nbr_of_mols"] - 1):
                duplicate_molecule = copy.deepcopy(self.molecules[-1])
                duplicate_molecule.update_name_and_id()
                if value["rotate"]:
                    duplicate_molecule.randomly_rotate_mol()
                self.molecules.append(duplicate_molecule)
        self.sort_molecules_by_type()

    def sort_molecules_by_type(self) -> None:
        """
        Sort molecules in the mixture by their type.

        Returns:
            None
        """
        self.molecules = sorted(self.molecules, key=lambda x: x.type)

    def update_mixture_information(self) -> None:
        """
        Update mixture information including weight, number of molecules, molecular weight,
        and simulation box dimensions.

        Returns:
            None
        """
        # Update weight and number of molecules
        for molecule in self.molecules:
            self.weight += molecule.mw_gmol
            self.nbr_of_mols += 1

        # Calculate molecular weight
        self.mw_gmol = self.weight / self.nbr_of_mols

        # Calculate final cubic dimension of the box
        self.box_final_cubic_dim = self._calculate_box_final_cubic_dim()

        # Calculate simulation box dimensions
        self.box_dims = [
            self.box_final_cubic_dim,
            self.box_final_cubic_dim,
            self._calculate_box_initial_c_dim(self.box_final_cubic_dim),
        ]

    def _calculate_box_final_cubic_dim(self) -> float:
        """
        Calculate and return the final cubic dimension of the simulation box.

        Returns:
            float: The final cubic dimension of the simulation box.
        """
        return (
            self.mw_gmol
            / 1000
            * self.nbr_of_mols
            / inputs.flt_final_density_in_kgm3
            / inputs.AVOGADRO_NUMBER
        ) ** (1 / 3) * 1e10

    def _calculate_box_initial_c_dim(self, box_cubic_dim: float) -> float:
        """
        Calculate and return the initial length of side 'c' for the simulation box.

        Args:
            box_cubic_dim (float): The cubic dimension of the simulation box.

        Returns:
            float: The initial length of side 'c' for the simulation box.
        """
        return (
            (
                self.nbr_of_mols
                * self.mw_gmol
                / 1000
                / (inputs.initial_low_density_factor * inputs.flt_final_density_in_kgm3)
                / inputs.AVOGADRO_NUMBER
            )
            / (box_cubic_dim * 1e-10)
            / (box_cubic_dim * 1e-10)
            * 1e10
        )

    def generate_sobol_positions(self) -> None:
        """
        Generate evenly distributed points using a Sobol sequence and apply an offset.

        This function generates Sobol sequence positions in x, y, and z dimensions and then
        shifts the positions in the z dimension by an offset/2 units.

        Returns:
            None
        """
        # Generating Sobol positions in x, y, and z.
        (
            self.sobol_x,
            self.sobol_y,
            self.sobol_z,
        ) = backend_static_functions.generate_sobol_positions(
            num_points=self.nbr_of_mols,
            box_dims=(
                self.box_dims[0],
                self.box_dims[1],
                self.box_dims[2] - inputs.layer_offset,
            ),
        )

        # Shifting Sobol points in the z dimension to have offsets offset/2 units long:
        self.sobol_z = [i + inputs.layer_offset / 2 for i in self.sobol_z]

    def translate_molecules_to_sobol_positions(self) -> None:
        """
        Translate molecules to new positions based on Sobol sequence coordinates.

        This function iterates through the molecules and translates each molecule to
        a new position specified by Sobol sequence coordinates (sobol_x, sobol_y, sobol_z).

        Returns:
            None
        """
        for index, molecule in enumerate(self.molecules):
            backend_static_functions.translate_molecule(
                mol_obj=molecule.mol_obj,
                x=self.sobol_x[index],
                y=self.sobol_y[index],
                z=self.sobol_z[index],
            )

    def calculate_lj_potential_energy(self) -> None:
        """
        Calculate the Lennard-Jones potential energy for a system of atoms.

        This function extracts the atoms' positions, computes the Lennard-Jones
        potential energy, and updates the 'potential_energy' and 'accepted' attributes
        of the instance. Epsilon, Sigma, Rcut are set to 1.0, 1.0, 14.0. Exponents 6 and 12.

        Returns:
            None
        """
        # Extracting the atoms' positions:
        (
            atoms_pos_x,
            atoms_pos_y,
            atoms_pos_z,
        ) = backend_static_functions.extract_atom_positions_from_mol_obj_list(
            mol_obj_list=[molecule.mol_obj for molecule in self.molecules]
        )

        # Calculate Lennard-Jones potential energy:
        self.potential_energy = backend_static_functions.compute_total_lj_potential(
            x=np.array(atoms_pos_x),
            y=np.array(atoms_pos_y),
            z=np.array(atoms_pos_z),
            box_dimensions=np.array(self.box_dims),
            rcut=10,
        )

        # Determine if the potential energy is accepted based on a limit:
        self.accepted = self.potential_energy < inputs.potential_energy_limit

    @staticmethod
    def export_molecules(mixture, nbr_of_mixtures_accepted, job_id):
        """
        Export molecules from a mixture to Mol files for LAMMPS Molecular Dynamics simulations.

        Args:
            mixture: The mixture of molecules to export.
            nbr_of_mixtures_accepted: The number of mixtures accepted.
            job_id: The job ID associated with the simulation.

        Returns:
            None
        """
        for molecule in mixture.molecules:
            # Define the filepath for the Mol file
            filepath = importlib.resources.files("scymol").joinpath(
                "output",
                f"{job_id}",
                f"mixture_{nbr_of_mixtures_accepted}",
                "all",
                f"{molecule.name}.mol",
            )

            # Convert the molecule to Mol file format and save it
            Chem.MolToMolFile(molecule.mol_obj, filepath)

            # Call a function to fix the Mol file (assuming backend_static_functions is a valid module)
            backend_static_functions.fix_mol_file(file=filepath)
