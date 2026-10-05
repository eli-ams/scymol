"""Shared constants for the molecule drawer."""

import math

from rdkit import Chem

BOND_LEN = 50.4
SNAP = math.radians(30.0)

NEAR_ATOM = 9.0
NEAR_BOND = 6.5
BOND_PICK_TRIM_FRACTION = 0.28
COMPONENT_GRID_GAP = 1.8 * BOND_LEN

ZOOM_STEP = 1.1
ZOOM_MIN = 0.18
ZOOM_MAX = 2.50
UNITED_ATOM_ZOOM_THRESHOLD = 0.35

SYM2Z = {
    "H": 1,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "P": 15,
    "S": 16,
    "Cl": 17,
    "Br": 35,
    "I": 53,
}
Z2SYM = {v: k for k, v in SYM2Z.items()}

BOND_TYPES = [Chem.BondType.SINGLE, Chem.BondType.DOUBLE, Chem.BondType.TRIPLE]
