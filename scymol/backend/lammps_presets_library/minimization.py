from typing import Optional


class StandardMinimizationSubstage:
    def __init__(
        self, stage_instance, lammps_commands_instance, set_timestep: int = 0
    ) -> None:
        """
        Initialize the StandardMinimizationSubstage.

        Args:
            stage_instance: The instance of the stage.
            lammps_commands_instance: The instance of lammps_commands.
            set_timestep (int, optional): Timestep value. Default is 0.
        """
        self.stage_instance = stage_instance
        self.set_timestep = set_timestep
        self.last_lammpstrj_file = f"{self.stage_instance.stage_nbr}.{self.stage_instance.substage_nbr}_minimization.lammpstrj"
        self.lammps_commands_instance = lammps_commands_instance

    def run(self) -> None:
        """
        Run the standard minimization substage.
        """
        if self.set_timestep is not None:
            self.lammps_commands_instance.add_set_timestep(
                set_timestep_to=self.set_timestep
            )

        title = "Minimization"
        numbering = (self.stage_instance.stage_nbr, self.stage_instance.substage_nbr)
        description = "Initialize LAMMPS run."
        self.lammps_commands_instance.add_substage_title(
            title=title, numbering=numbering, description=description
        )

        self.lammps_commands_instance.add_min_style(style="cg")
        self.lammps_commands_instance.add_min_modify(dmax=0.05)
        self.lammps_commands_instance.add_thermo_style(
            style_option="custom",
            lst_properties=[
                "step",
                "fmax",
                "fnorm",
                "press",
                "vol",
                "v_sysdensity",
                "v_sxx",
                "v_syy",
                "v_szz",
                "v_syz",
                "v_sxz",
                "v_sxy",
                "pe",
                "v_cella",
                "v_cellb",
                "v_cellc",
                "v_cellalpha",
                "v_cellbeta",
                "v_cellgamma",
            ],
        )

        properties = self.lammps_commands_instance.std_list_dump_properties
        self.lammps_commands_instance.add_dump(
            dump_id="minrun",
            dump_subset="all",
            style_option="custom",
            ndump=1000,
            absolute_path_with_file=self.last_lammpstrj_file,
            properties=properties,
        )

        self.lammps_commands_instance.add_thermo(nthermo=100)
        self.lammps_commands_instance.add_fix_minimize(
            tol_energy=0.0, tol_force=0.0, max_iterations=1000, max_evaluations=10_000
        )

        self.lammps_commands_instance.add_undump(dump_id="minrun")
        self.stage_instance.substage_nbr += 1
