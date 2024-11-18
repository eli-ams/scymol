from typing import Optional, Tuple


class StandardInitializationSubstage:
    def __init__(
        self,
        stage_instance,
        lammps_commands_instance,
        units_style: str = "real",
        boundary_style: Tuple[str, str, str] = ("p", "p", "p"),
    ) -> None:
        """
        Initialize the StandardInitializationSubstage.

        Args:
            stage_instance: The instance of the stage.
            lammps_commands_instance: The instance of lammps_commands.
            units_style (str, optional): Units style. Default is 'real'.
            boundary_style (tuple, optional): Boundary style. Default is ('p', 'p', 'p').
        """
        self.stage_instance = stage_instance
        self.lammps_commands_instance = lammps_commands_instance
        self.units_style = units_style
        self.boundary_style = boundary_style

    def run(self) -> None:
        """
        Run the standard initialization substage.
        """
        title = "Initialization"
        numbering = (self.stage_instance.stage_nbr, self.stage_instance.substage_nbr)
        description = "Initialize LAMMPS run."

        self.lammps_commands_instance.add_substage_title(
            title=title, numbering=numbering, description=description
        )

        self.lammps_commands_instance.add_units(units_style=self.units_style)
        self.lammps_commands_instance.add_boundary(boundary_style=self.boundary_style)
        self.lammps_commands_instance.add_atom_style(atom_style="full")
        self.lammps_commands_instance.add_pair_style(pair_style="lj/cut 12.0")
        self.lammps_commands_instance.add_pair_modify(pair_modify="mix arithmetic")
        self.lammps_commands_instance.add_bond_style(bond_style="harmonic")
        self.lammps_commands_instance.add_angle_style(angle_style="harmonic")
        self.lammps_commands_instance.add_dihedral_style(dihedral_style="fourier")
        self.lammps_commands_instance.add_improper_style(improper_style="cvff")
        self.lammps_commands_instance.add_special_bonds(special_bonds="amber")
        self.lammps_commands_instance.add_read_data(
            absolute_path_with_file="structure.data"
        )
        self.lammps_commands_instance.add_comment(
            comment="Declaring variables:", prepend_new_line=True
        )
        for key, value in self.lammps_commands_instance.dict_of_variables.items():
            self.lammps_commands_instance.add_variable(
                var_name=key, var_expression=value
            )
        self.lammps_commands_instance.add_thermo_style(
            style_option="custom",
            lst_properties=self.lammps_commands_instance.list_thermo_style_mda,
        )
        self.lammps_commands_instance.add_thermo_modify(flush=True)
        self.stage_instance.substage_nbr += 1
