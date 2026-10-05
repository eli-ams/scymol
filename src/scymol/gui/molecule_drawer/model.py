"""Model and undo history for the molecule drawer."""

from copy import deepcopy

from rdkit import Chem

from .constants import BOND_TYPES, SYM2Z


class History:
    def __init__(self, max_states=200):
        self._stack = []
        self.max_states = max_states

    def push(self, atoms, bonds, next_aid, selected_atom, selected_bond, selected_atoms):
        state = (
            deepcopy(atoms),
            deepcopy(bonds),
            next_aid,
            selected_atom,
            selected_bond,
            set(selected_atoms),
        )

        if self._stack and state == self._stack[-1]:
            return

        self._stack.append(state)

        if len(self._stack) > self.max_states:
            self._stack.pop(0)

    def pop(self):
        if not self._stack:
            return None
        return self._stack.pop()

    def clear(self):
        self._stack.clear()


class MoleculeModel:
    def __init__(self):
        self.atoms = {}
        self.bonds = {}
        self.next_aid = 0

    def add_atom(self, x, y, sym):
        aid = self.next_aid
        self.next_aid += 1
        self.atoms[aid] = (float(x), float(y), sym)
        return aid

    def set_atom_sym(self, aid, sym):
        if aid not in self.atoms:
            return

        x, y, _ = self.atoms[aid]
        self.atoms[aid] = (x, y, sym)

    def set_atom_xy(self, aid, x, y):
        if aid not in self.atoms:
            return

        _, _, sym = self.atoms[aid]
        self.atoms[aid] = (float(x), float(y), sym)

    def cycle_or_set_bond(self, a, b, active_order):
        if a == b:
            return

        key = frozenset((a, b))

        if key not in self.bonds:
            self.bonds[key] = int(active_order)
        else:
            order = self.bonds[key]
            self.bonds[key] = 1 if order == 3 else order + 1

    def set_bond_order(self, key, order):
        if key in self.bonds:
            self.bonds[key] = int(order)

    def remove_bond_key(self, key):
        if key in self.bonds:
            del self.bonds[key]

    def remove_bond(self, a, b):
        self.remove_bond_key(frozenset((a, b)))

    def remove_atom(self, aid):
        if aid not in self.atoms:
            return

        del self.atoms[aid]

        for key in list(self.bonds):
            if aid in key:
                del self.bonds[key]

    def clear(self):
        self.atoms.clear()
        self.bonds.clear()
        self.next_aid = 0

    def build_mol(self):
        mol = Chem.RWMol()
        atom_to_idx = {}

        for aid in sorted(self.atoms):
            _, _, sym = self.atoms[aid]
            atom_to_idx[aid] = mol.AddAtom(Chem.Atom(SYM2Z.get(sym, 6)))

        for key, order in self.bonds.items():
            a, b = tuple(key)

            if a not in atom_to_idx or b not in atom_to_idx:
                continue

            if not (1 <= order <= 3):
                continue

            mol.AddBond(atom_to_idx[a], atom_to_idx[b], BOND_TYPES[order - 1])

        out = mol.GetMol()
        Chem.SanitizeMol(out)

        idx_to_atom = {v: k for k, v in atom_to_idx.items()}

        return out, atom_to_idx, idx_to_atom

    def is_valid(self):
        try:
            mol, _, _ = self.build_mol()
            mol.UpdatePropertyCache(strict=True)

            for atom in mol.GetAtoms():
                if atom.GetNumRadicalElectrons():
                    return False

            return True

        except Exception:
            return False
