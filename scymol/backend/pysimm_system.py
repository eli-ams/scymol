import importlib
import os
from pathlib import Path

from pysimm import lmps
from rdkit import Chem
import pysimm
import scymol.backend.backend_static_functions as backend_static_functions
from typing import Optional


class PysimmSystem:
    def __init__(self, mixture, working_dir: str) -> None:
        """
        Initialize a new pysimm instance.

        Args:
            mixture: The mixture to be used in the pysimm instance.
            working_dir (str): The working directory where temporary files will be stored.
        """
        self.pysimm_system: Optional[object] = None
        self._mixture = mixture
        self._forcefield = mixture.forcefield
        self._charges = mixture.charges
        self._temp_mol_file = (
            Path(importlib.resources.files("scymol")) / working_dir / "temp.mol"
        )
        self.current_mol: Optional[object] = None
        self.current_mol_index: int = 0
        self._parent_molecule: Optional[object] = None

    def _write_temp_mol(self, index: Optional[int] = None) -> None:
        """
        Write the current molecule to a temporary MOL file.

        Args:
            index (Optional[int]): The index of the current molecule in the mixture (default is None).
        """
        if index is None:
            index = self.current_mol_index
        self._write_temp_mol_file(
            self._mixture.molecules[index].mol_obj, self._temp_mol_file
        )

    def initialize_system(self) -> None:
        """
        Create a new pysimm system.

        This method performs the following steps:
        1. Writes the current molecule to a temporary MOL file.
        2. Loads the molecule from the MOL file and applies the specified forcefield.
        3. Copies the loaded molecule as the current molecule.
        4. Copies the current molecule as the parent molecule.
        """
        self._write_temp_mol()
        self.pysimm_system = self._load_molecule(
            mol_file=self._temp_mol_file,
            forcefield=self._forcefield,
            charges=self._charges,
        )
        self.current_mol = self.pysimm_system.copy()
        self._parent_molecule = self.current_mol.copy()

    def load_current_molecule(self, index: int) -> None:
        """
        Load the current molecule of the specified index.

        Args:
            index (int): The index of the molecule to load.

        This method performs the following steps:
        1. Writes the molecule at the specified index to a temporary MOL file.
        2. Compares the types of the current molecule and the new molecule.
        3. If the types match, it copies positions from the parent molecule to the current molecule.
        4. If the types do not match, it loads the new molecule and applies the forcefield.
        5. Updates the current molecule and current molecule index.
        """
        self._write_temp_mol(index)
        molecule_type_current = self._mixture.molecules[self.current_mol_index].type
        molecule_type_new = self._mixture.molecules[index].type

        if molecule_type_new == molecule_type_current:
            # Molecule is a duplicate. Force field types and charges are obtained from the parent molecule.
            self.current_mol = self._apply_positions(
                self._parent_molecule.copy(),
                self._load_molecule(
                    mol_file=self._temp_mol_file,
                    forcefield=None,
                    charges=None,
                ),
            )
        else:
            self.current_mol = self._load_molecule(
                mol_file=self._temp_mol_file,
                forcefield=self._forcefield,
                charges=self._charges,
            )
            self._parent_molecule = self.current_mol.copy()

        self.current_mol_index = index

    def add_current_molecule_to_system(self) -> None:
        """Add current molecule to the system."""
        self.pysimm_system.add(self.current_mol, change_dim=True)

    def set_box_dimensions(self) -> None:
        """Update dimensions of the PySIMM system to box_dimensions."""
        self.pysimm_system.dim.xlo = 0
        self.pysimm_system.dim.ylo = 0
        self.pysimm_system.dim.zlo = 0
        self.pysimm_system.dim.xhi = self._mixture.box_dims[0]
        self.pysimm_system.dim.yhi = self._mixture.box_dims[1]
        self.pysimm_system.dim.zhi = self._mixture.box_dims[2]

    def load_all_molecules_into_system(self) -> None:
        """
        Load every molecule in the mixture into the pysimm system.

        This method iterates through all molecules in the mixture, loads each molecule,
        and adds it to the pysimm system.
        """
        for index in range(1, len(self._mixture.molecules)):
            self.load_current_molecule(index=index)
            self.add_current_molecule_to_system()

    def generate_lammps_inputs(self) -> None:
        """
        Generate LAMMPS inputs for simulation.

        This method creates a LAMMPS simulation object using the pysimm system,
        sets the name of the simulation, and attempts to run the simulation,
        saving the input files.
        """
        # Generate LAMMPS simulation
        simulation = lmps.Simulation(self.pysimm_system, name="my_simulation")
        try:
            simulation.run(save_input=True)
        except TypeError as e:
            print(f"Warning: TypeError {e} caught and skipped.")

    @staticmethod
    def _write_temp_mol_file(mol_obj, temp_mol_file: str) -> None:
        """
        Write the molecule object to a temporary MOL file.

        Args:
            mol_obj: The molecule object to be written.
            temp_mol_file (str): The path to the temporary MOL file.
        """
        Chem.MolToMolFile(mol_obj, temp_mol_file)
        backend_static_functions.fix_mol_file(file=temp_mol_file)

    @staticmethod
    def _load_molecule(
        mol_file: str,
        forcefield: Optional[str] = None,
        charges: Optional[str] = "default",
    ) -> object:
        """
        Load a molecule from a file and apply a forcefield to it. Assigning types and charges is computationally
        intensive. If the molecule is a duplicate, force field types and charges are obtained from the parent molecule.

        Args:
            mol_file (str): The path to the molecule file to be loaded.
            forcefield (Optional[str]): The forcefield to apply to the loaded molecule (default is None).

        Returns:
            object: The loaded molecule system.
        """
        mol_system = pysimm.system.read_mol(mol_file)
        if forcefield:
            mol_system.apply_forcefield(f=forcefield, charges=charges)
        return mol_system

    @staticmethod
    def _apply_positions(system1: object, system2: object) -> object:
        """
        Copy positions from system2 to system1.

        Args:
            system1 (object): The destination system to which positions will be copied.
            system2 (object): The source system from which positions will be copied.

        Returns:
            object: The modified destination system with updated positions.
        """
        for p1, p2 in zip(system1.particles, system2.particles):
            p1.x, p1.y, p1.z = p2.x, p2.y, p2.z
        return system1
