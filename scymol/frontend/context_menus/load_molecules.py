import os
from PyQt5.QtWidgets import QFileDialog, QDialog, QMenu, QAction

import scymol.static_functions as static_functions
from scymol.frontend.molecule import Molecule
from scymol.frontend.dialog_windows.smiles_window import SmilesWindow
from scymol.logging_functions import print_to_log, log_function_call


class LoadMoleculesContextMenu:
    """
    A context menu for loading molecules into a chemical analysis application.

    This class provides a context menu with options to load molecules from various sources, including SMILES strings,
    .mol files, .pdb files, and RDKit molecule objects.

    :param main_window: The main application window where the context menu is attached.
    :type main_window: MainWindow

    .. note::
        The `MainWindow` type in the `main_window` parameter should be replaced with the actual type of your main window.
    """

    @log_function_call
    def __init__(self, main_window: object) -> None:
        """
        Initialize the LoadMoleculesContextMenu instance.

        :param main_window: The main application window to which this context menu is attached.
        :type main_window: MainWindow
        :return: None
        :rtype: None
        """
        self.main_window = main_window  # Keeping a reference to the MainWindow instance
        self.tab1 = self.main_window.tab1

    @log_function_call
    def create_loadmolecules_menu(self) -> None:
        """
        Create and display the context menu for loading molecules.

        This method sets up a menu with options to load molecules from various sources,
        attaching the appropriate actions for each menu item.

        :return: None
        :rtype: None
        """
        menu = QMenu(self.main_window)
        menu.addAction(
            QAction(
                "Load from SMILES string",
                self.main_window,
                triggered=self.load_molecule_smiles_file,
            )
        )
        menu.addAction(
            QAction(
                "Load from .mol file",
                self.main_window,
                triggered=self.load_molecule_mol_file,
            )
        )
        menu.addAction(
            QAction(
                "Load from .pdb file",
                self.main_window,
                triggered=self.load_molecule_pdb_file,
            )
        )
        menu.exec_(
            self.main_window.addMoleculeButton.mapToGlobal(
                self.main_window.addMoleculeButton.rect().bottomLeft()
            )
        )

    @log_function_call
    def load_molecule_smiles_file(self) -> None:
        """
        Load a molecule from a SMILES string.

        Prompts the user to enter a SMILES string and loads the corresponding molecule.

        :return: None
        :rtype: None
        """
        smiles_window = SmilesWindow(self.main_window)
        if smiles_window.exec_() == QDialog.Accepted:
            try:
                name = smiles_window.input_name
                self.main_window.molecules_objects[name] = Molecule(
                    source_type="smiles",
                    source=smiles_window.input_smiles,
                    hydrogenate=True,
                    minimize=False,
                    generate_image=True,
                )
            except Exception as e:
                static_functions.display_message(
                    title="Error parsing SMILES",
                    message=f"Smiles string [{smiles_window.input_smiles}] could not be parsed using Rdkit.\n{e}",
                    dialog_type="error",
                )
                return
            self.tab1.add_molecule(name=name, number=50, rotate=True)

    @log_function_call
    def load_molecule_mol_file(self) -> None:
        """
        Load a molecule from a .mol file.

        Allows the user to select a .mol file from their file system and loads the molecule from this file.

        :return: None
        :rtype: None
        """
        mol, _ = QFileDialog.getOpenFileName(
            self.main_window, "Open .mol file", "", "MOL files (*.mol)"
        )
        name = os.path.splitext(os.path.basename(mol))[0]
        if mol:
            try:
                self.main_window.molecules_objects[name] = Molecule(
                    source_type="mol",
                    source=mol,
                    hydrogenate=True,
                    minimize=False,
                    generate_image=True,
                )
            except Exception as e:
                static_functions.display_message(
                    title="Error parsing file",
                    message=f"Mol file could not be parsed using Rdkit.\n{e}",
                    dialog_type="error",
                )
                return
            self.tab1.add_molecule(name=name, number=50, rotate=True)

    @log_function_call
    def load_molecule_pdb_file(self) -> None:
        """
        Load a molecule from a .pdb file.

        Allows the user to select a .pdb file from their file system and loads the molecule from this file.

        :return: None
        :rtype: None
        """
        pdb, _ = QFileDialog.getOpenFileName(
            self.main_window, "Open .pdb file", "", "PDB files (*.pdb)"
        )
        name = os.path.splitext(os.path.basename(pdb))[0]
        if pdb:
            try:
                static_functions.display_message(
                    title="Attention: Connectivity in PDB files",
                    message=f"PDB files do not contain connectivity information. "
                    f"Scymol will use Rdkit's function rdDetermineBonds.DetermineBondOrders() "
                    f"to deduce bonds in [{name}]",
                    dialog_type="warning",
                )

                self.main_window.molecules_objects[name] = Molecule(
                    source_type="pdb",
                    source=pdb,
                    hydrogenate=False,
                    minimize=False,
                    generate_image=True,
                )
            except Exception as e:
                static_functions.display_message(
                    title="Error parsing file",
                    message=f"Pdb file could not be parsed using Rdkit.\n{e}",
                    dialog_type="error",
                )
                return
            self.tab1.add_molecule(name=name, number=50, rotate=True)

    @log_function_call
    def load_molecule_rdkitobj(self, name: str, molecule: object) -> None:
        """
        Load a molecule from an RDKit molecule object.

        :param name: The name to assign to the loaded molecule.
        :type name: str
        :param molecule: The RDKit molecule object to be loaded.
        :type molecule: Chem.Mol
        :return: None
        :rtype: None
        """
        try:
            self.main_window.molecules_objects[name] = Molecule(
                source_type="rdkit_mol",
                source=molecule,
                hydrogenate=False,
                minimize=False,
                generate_image=False,
            )
        except Exception as e:
            static_functions.display_message(
                title="Error parsing file",
                message=f"MolObject file could not be parsed using Rdkit.\n{e}",
                dialog_type="error",
            )
            return
        self.tab1.add_molecule(name=name, number=50, rotate=True)
