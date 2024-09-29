from io import BytesIO

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import Draw, Descriptors
from typing import Optional, Union
from logging_functions import print_to_log, log_function_call


class Molecule:
    """
    A class to represent and manipulate molecular data.

    This class provides functionalities to create a molecule from various sources like SMILES strings, .mol files, or .pdb files, and perform operations such as hydrogenation, energy minimization, and image generation.
    It encapsulates the functions in Rdkit to create a Molecule object that can be

    Examples:
        Creating a Molecule object from a SMILES string and performing various operations:

        >>> mol1 = Molecule("smiles", "CCCCCCO", hydrogenate=True, minimize=False, generate_image=True)
        >>> mol1.hydrogenate()
        >>> mol1.generate_image(show_hydrogens=False)

    Parameters:
    ...
    """

    @log_function_call
    def __init__(
        self,
        source_type: str,
        source: Union[str, "Molecule"],
        hydrogenate: bool,
        minimize: bool,
        generate_image: bool,
    ) -> None:
        """
        Initialize a new Molecule object from a source and its type.

        :param source_type: The type of the source. One of 'smiles', 'mol', 'pdb', 'rdkit_mol'.
        :type source_type: str
        :param source: The source of the molecule. Could be a SMILES string, a path to a .mol file, a .pdb file, or another Molecule object.
        :type source: Union[str, 'Molecule']
        :param hydrogenate: Flag to determine whether to add hydrogens to the molecule.
        :type hydrogenate: bool
        :param minimize: Flag to determine whether to perform energy minimization on the molecule.
        :type minimize: bool
        :param generate_image: Flag to determine whether to generate an image of the molecule.
        :type generate_image: bool
        :raises ValueError: If an invalid source type is provided or if the molecule cannot be created from the given source.
        """
        self.smiles: Optional[str] = None
        self.image: Optional[bytes] = None
        self.nbr_atoms: Optional[int] = None
        self.mol_weight: Optional[float] = None
        self.mol_formula: Optional[str] = None
        self.source: Union[str, "Molecule"] = source
        self.source_type: str = source_type.lower()
        self.mol_obj: Optional[Chem.Mol] = None

        if self.source_type == "smiles":
            self.mol_obj = Chem.MolFromSmiles(self.source)
            if self.mol_obj is None:
                raise ValueError("Invalid SMILES string")

        elif self.source_type == "mol":
            with open(self.source, "r") as f:
                mol_block: str = f.read()
            self.mol_obj = Chem.MolFromMolBlock(mol_block)
            if self.mol_obj is None:
                raise ValueError("Invalid .mol file")

        elif self.source_type == "pdb":
            with open(self.source, "r") as f:
                pdb_block: str = f.read()
            self.mol_obj = Chem.MolFromPDBBlock(pdb_block)
            if self.mol_obj is None:
                raise ValueError("Invalid .pdb file")

        elif self.source_type == "rdkit_mol":
            self.mol_obj = self.source.mol_obj
            self.image = self.source.image
            if self.mol_obj is None:
                raise ValueError("Invalid rdkit molecule object (returns None)")
            if not AllChem.CalcMolFormula(self.mol_obj):
                raise ValueError("Invalid rdkit molecule object")
        else:
            raise ValueError(
                "Invalid source type. Must be one of 'smiles', 'mol', 'pdb', 'rdkit_mol"
            )

        if hydrogenate:
            self.hydrogenate()

        if minimize:
            self.minimize()

        if generate_image:
            self.generate_image(show_hydrogens=False)

        self.generate_mol_info()

    @log_function_call
    def __repr__(self) -> str:
        """
        Represent the Molecule object as a string.

        :return: A string representation of the Molecule object.
        :rtype: str
        """
        return f"<Molecule: source={self.source}, source_type={self.source_type}>"

    @log_function_call
    def hydrogenate(self) -> None:
        """
        Add hydrogens to the molecule.

        This method modifies the molecule object to include hydrogen atoms and updates its molecular information.

        :return: None
        :rtype: None
        """
        self.mol_obj = Chem.AddHs(self.mol_obj)

        # Update molecular info:
        self.generate_mol_info()

    @log_function_call
    def minimize(self) -> None:
        """
        Perform energy minimization on the molecule.

        This method uses the Universal Force Field (UFF) to minimize the energy of the molecule and updates its molecular information.

        :return: None
        :rtype: None
        """
        # Use the UFF (Universal Force Field) to minimize
        AllChem.UFFOptimizeMolecule(self.mol_obj)

        # Update molecular info:
        self.generate_mol_info()

    @log_function_call
    def generate_image(self, show_hydrogens: bool = True) -> None:
        """
        Generate an image of the molecule and store it in self.image.

        :param show_hydrogens: Whether to include hydrogens in the image, defaults to True.
        :type show_hydrogens: bool
        :return: None
        :rtype: None
        """
        if show_hydrogens:
            img_mol = self.mol_obj
        else:
            img_mol = Chem.RemoveHs(self.mol_obj)

        img = Draw.MolToImage(img_mol, size=(450, 450), fitImage=True, kekulize=False)
        byte_io = BytesIO()
        img.save(byte_io, format="PNG")
        byte_io.seek(0)
        self.image = byte_io.read()

    @log_function_call
    def show_image(self) -> None:
        """
        Display the generated image of the molecule in a window.

        :return: None
        :rtype: None
        """
        if self.image:
            self.image.show()
        else:
            print_to_log(
                message="Image not generated. Call generate_image() first.",
                level="warning",
            )

    @log_function_call
    def generate_mol_info(self) -> None:
        """
        Generate chemical information about the molecule.

        This method calculates and updates the molecular formula, weight, number of atoms,
        and the SMILES string of the molecule.

        :return: None
        :rtype: None
        """
        # Return the molecular formula
        self.mol_formula = AllChem.CalcMolFormula(self.mol_obj)

        # Return the molecular weight
        self.mol_weight = Descriptors.MolWt(self.mol_obj)

        # Return the number of atoms
        self.nbr_atoms = self.mol_obj.GetNumAtoms()

        # Return the SMILES string of the molecule:
        self.smiles = Chem.MolToSmiles(self.mol_obj)
