from collections import defaultdict
from typing import Dict, Any
import numpy as np
from rdkit import Chem
from rdkit.Chem import rdMolTransforms, AllChem
from rdkit.Geometry import Point3D
from typing import Type

from scipy.stats import special_ortho_group


class Molecule:
    global_counter: int = 0
    molecule_counter = defaultdict(lambda: 0)

    def __init__(self, name: str, info: Dict[str, Any]) -> None:
        """Initialize a new Molecule instance.

        Args:
            name (str): The name or type of the molecule.
            info (Dict[str, Any]): A dictionary containing molecule information,
                including the SMILES representation.

        Returns:
            None

        Note:
            This constructor initializes a new instance of the Molecule class.
            It increments the global counter and updates the molecule-specific
            counter based on the provided name. It also calculates molecular
            properties such as the molecule's ID, name, SMILES representation,
            and molecular weight in g/mol.

        """
        Molecule.global_counter += 1
        Molecule.molecule_counter[name] += 1
        self.type: str = name
        self.id: tuple = (Molecule.global_counter, Molecule.molecule_counter[self.type])
        self.name: str = f"{self.id[0]}_{self.type}_{self.id[1]}"
        self.smiles: str = info["smiles"]
        self.rotate: str = info["rotate"]
        self.mol_obj = self._smiles_to_obj_mol(self.smiles)
        self.generate_lowest_energy_conformer()
        self.mw_gmol: float = Chem.rdMolDescriptors.CalcExactMolWt(self.mol_obj)

    def update_name_and_id(self) -> None:
        """Update molecule name and ID.

        Returns:
            None

        Note:
            This method updates the name and ID of the molecule based on the
            global counter and molecule type. It increments the global counter,
            updates the molecule-specific counter, and constructs a new name
            for the molecule in the format "global_counter_type_molecule_counter".

        """
        Molecule.global_counter += 1
        Molecule.molecule_counter[self.type] += 1
        self.id = (Molecule.global_counter, Molecule.molecule_counter[self.type])
        self.name = f"{self.id[0]}_{self.type}_{self.id[1]}"

    def center_molecule_at_origin(self) -> None:
        """Center the molecule object at the origin.

        Returns:
            None

        Note:
            This method calculates the centroid of the molecule's conformer
            and then translates all atom positions to center the molecule
            at the origin (0, 0, 0) in 3D space.

        """
        conf = self.mol_obj.GetConformer()
        center = rdMolTransforms.ComputeCentroid(conf)
        for i in range(conf.GetNumAtoms()):
            pos = conf.GetAtomPosition(i)
            conf.SetAtomPosition(
                i, (pos.x - center.x, pos.y - center.y, pos.z - center.z)
            )

    def translate_molecule(self, x: float, y: float, z: float) -> None:
        """Translate the molecule in 3D space.

        Args:
            x (float): The translation distance along the x-axis.
            y (float): The translation distance along the y-axis.
            z (float): The translation distance along the z-axis.

        Returns:
            None

        Note:
            This method translates the molecule in 3D space by the specified
            distances along the x, y, and z axes. It updates the positions of
            all atoms in the molecule accordingly.

        """
        conformer = self.mol_obj.GetConformer()
        num_atoms = self.mol_obj.GetNumAtoms()
        for i in range(num_atoms):
            position = conformer.GetAtomPosition(i)
            new_position = Point3D(position.x + x, position.y + y, position.z + z)
            conformer.SetAtomPosition(i, new_position)

    def randomly_rotate_mol(self) -> Any:
        """Randomly rotate the molecule object about its center.

        Returns:
            None

        Note:
            This method performs a random rotation of the molecule in 3D space.
            It first calculates the center of the molecule and translates it to
            the origin. Then, it generates random rotation angles around the x, y,
            and z axes and creates rotation matrices for each axis. The molecule's
            coordinates are rotated accordingly, and it is translated back to its
            original center.

        """
        conf = self.mol_obj.GetConformer()

        # Create an array of the coordinates
        coordinates = np.array(
            [list(conf.GetAtomPosition(i)) for i in range(conf.GetNumAtoms())]
        )

        # Calculate the center of the molecule
        center = np.mean(coordinates, axis=0)

        # Translate the molecule so that the center is at the origin
        translated_coordinates = coordinates - center

        # Generate random angles
        pi = np.pi
        angle_x = np.random.uniform(-pi, pi)
        angle_y = np.random.uniform(-pi, pi)
        angle_z = np.random.uniform(-pi, pi)

        # Create rotation matrices
        rot_x = np.array(
            [
                [1, 0, 0],
                [0, np.cos(angle_x), -np.sin(angle_x)],
                [0, np.sin(angle_x), np.cos(angle_x)],
            ]
        )

        rot_y = np.array(
            [
                [np.cos(angle_y), 0, np.sin(angle_y)],
                [0, 1, 0],
                [-np.sin(angle_y), 0, np.cos(angle_y)],
            ]
        )

        rot_z = np.array(
            [
                [np.cos(angle_z), -np.sin(angle_z), 0],
                [np.sin(angle_z), np.cos(angle_z), 0],
                [0, 0, 1],
            ]
        )

        # Perform the rotations
        rotated_coordinates = np.dot(translated_coordinates, rot_x)
        rotated_coordinates = np.dot(rotated_coordinates, rot_y)
        rotated_coordinates = np.dot(rotated_coordinates, rot_z)

        # Translate the molecule back to its original center
        final_coordinates = rotated_coordinates + center

        # Update the molecule's particle coordinates
        for i, coord in enumerate(final_coordinates):
            conf.SetAtomPosition(i, tuple(coord))

    def generate_lowest_energy_conformer(self, num_conformers=10, prune_rms_thresh=0.25, max_iterations=5000):
        """
        Generate multiple diverse conformers, optimize their geometry, and find the lowest-energy one.

        Parameters:
        - smiles (str): SMILES string of the molecule.
        - num_conformers (int): Number of conformers to generate.
        - prune_rms_thresh (float): RMSD threshold for pruning similar conformers.
        - max_iterations (int): Maximum iterations for MMFF optimization.

        Returns:
        - lowest_energy_mol (Mol): Molecule with the lowest-energy conformation.
        - energies (list): List of (conformer_id, energy) tuples.
        """
        # Embed multiple conformers with diversity control
        conformer_ids = AllChem.EmbedMultipleConfs(
            self.mol_obj,
            numConfs=num_conformers,
            randomSeed=42,
            pruneRmsThresh=prune_rms_thresh
        )

        # Initialize MMFF properties
        mmff_props = AllChem.MMFFGetMoleculeProperties(self.mol_obj)
        energies = []

        for conf_id in conformer_ids:
            try:
                # Optimize each conformer using MMFF and calculate its energy
                ff = AllChem.MMFFGetMoleculeForceField(self.mol_obj, mmff_props, confId=conf_id)
                ff.Minimize(maxIts=max_iterations, forceTol=0.0001, energyTol=1e-6)
                energy = ff.CalcEnergy()
                energies.append((conf_id, energy))
            except Exception as e:
                print(f"Failed to process Conformer ID {conf_id}: {e}")

        if not energies:
            raise RuntimeError("No valid conformers generated or optimized!")

        # Find the lowest-energy conformer
        lowest_energy_id, lowest_energy = min(energies, key=lambda x: x[1])

        # Return molecule with the lowest-energy conformer highlighted
        lowest_energy_mol = Chem.Mol(self.mol_obj)

        return lowest_energy_mol

    @classmethod
    def reset_counters(cls: Type["Molecule"]) -> None:
        """Reset the global_counter and molecule_counter to their initial states."""
        cls.global_counter = 0
        cls.molecule_counter = defaultdict(lambda: 0)

    @staticmethod
    def _smiles_to_obj_mol(smiles_string: str) -> Chem.Mol:
        """Convert SMILES to a molecule object.

        Args:
            smiles_string (str): A SMILES string representing the molecule.

        Returns:
            Chem.Mol: A molecule object generated from the SMILES input.

        Raises:
            ValueError: If the provided SMILES string is invalid.

        Note:
            This static method converts a SMILES string into a molecule object
            using RDKit library functions. It adds hydrogen atoms, embeds the
            molecule, and performs MMFF optimization.

        """
        mol = Chem.MolFromSmiles(smiles_string)

        if mol is None:
            raise ValueError("Invalid SMILES string provided.")

        mol_with_h = Chem.AddHs(mol)

        return mol_with_h
