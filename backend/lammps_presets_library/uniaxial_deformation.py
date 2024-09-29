class StandardDeformationStage:
    def __init__(
        self,
        stage_instance,
        lammps_commands_instance,
        comp_axis: str,
        ndeformation: int = 1000,
        strain_style: str = "t",
        temp_initial: float = 298.15,
        temp_final: float = 298.15,
        temp_ncontrol: int = 100,
        drag: float = 0,
        nreset: int = 1000,
        nevery: int = 1,
        nrepeat: int = 999,
        nfreq: int = 1000,
        ndump: int = 1000,
        timestep: float = 1,
        nrun: int = 100_000,
        set_timestep: int = 0,
        wallskin: float = 2.0,
    ) -> None:
        """
        Initialize the StandardDeformationStage.

        Args:
            stage_instance: The instance of the stage.
            lammps_commands_instance: The instance of lammps_commands.
            comp_axis (str): The compression axis ('x', 'y', or 'z').
            ndeformation (int, optional): Deformation interval. Default is 1000.
            strain_style (str, optional): Strain style ('t' or 'e'). Default is 't'.
            temp_initial (float, optional): Initial temperature. Default is 298.15.
            temp_final (float, optional): Final temperature. Default is 298.15.
            temp_ncontrol (int, optional): Temperature control. Default is 100.
            drag (float, optional): Drag parameter. Default is 0.
            nreset (int, optional): Reset interval. Default is 1000.
            nevery (int, optional): Repeat interval. Default is 1.
            nrepeat (int, optional): Number of repetitions. Default is 999.
            nfreq (int, optional): Frequency of calculations. Default is 1000.
            ndump (int, optional): Dump frequency. Default is 1000.
            timestep (float, optional): Timestep value. Default is 1.
            nrun (int, optional): Number of simulation steps. Default is 100000.
            set_timestep (int, optional): Set timestep. Default is 0.
            wallskin (float, optional): Wall skin thickness. Default is 2.0.
        """
        self.stage_instance = stage_instance
        self.lammps_commands_instance = lammps_commands_instance
        self.comp_axis = comp_axis
        self.ndeformation = ndeformation
        self.strain_style = strain_style
        self.temp_initial = temp_initial
        self.temp_final = temp_final
        self.temp_ncontrol = temp_ncontrol
        self.drag = drag
        self.nreset = nreset
        self.nevery = nevery
        self.nrepeat = nrepeat
        self.nfreq = nfreq
        self.ndump = ndump
        self.timestep = timestep
        self.nrun = nrun
        self.set_timestep = set_timestep
        self.wallskin = wallskin

    def run(self) -> None:
        """
        Run the standard deformation stage.
        """
        self.preprocess_gui_inputs_into_readable_inputs()

        file_name_base = f"{self.stage_instance.stage_nbr}.{self.stage_instance.substage_nbr}_uniaxialcompression"
        self.stage_instance.last_lammpstrj_file = f"{file_name_base}.lammpstrj"
        self.stage_instance.last_instantaneous_file = (
            f"{file_name_base}_instantaneous.out"
        )

        if self.set_timestep is not None:
            self.lammps_commands_instance.add_set_timestep(
                set_timestep_to=self.set_timestep
            )

        title = "Uniaxial compression dynamics"
        numbering = (self.stage_instance.stage_nbr, self.stage_instance.substage_nbr)
        description = (
            f"Uniaxial compression in the {self.comp_axis} axis for {self.nrun} "
            f"steps with a timestep of {self.timestep}. "
            f"Temperature control from {self.temp_initial} to {self.temp_final} K. "
            f"Deformation applied every {self.ndeformation} steps, "
            f"with an {self.strain_style} strain equal to: XX)"
        )

        self.lammps_commands_instance.add_substage_title(
            title=title, numbering=numbering, description=description
        )

        final_dim = next((char for char in "xyz" if char != self.comp_axis), None)
        self.lammps_commands_instance.add_variable(
            "strainrate",
            f"ln((l{final_dim}+{2 * self.wallskin})/"
            f"l{self.comp_axis})/{self.timestep * self.nrun}",
        )
        self.lammps_commands_instance.add_variable("strainrateconst", "${strainrate}")

        self.lammps_commands_instance.add_thermo_style(
            "custom", self.lammps_commands_instance.list_thermo_style_mda
        )
        self.lammps_commands_instance.add_fix_nvt(
            "1",
            "all",
            self.temp_initial,
            self.temp_final,
            self.temp_ncontrol,
            self.drag,
            self.nreset,
            ["mtk yes"],
        )

        self.lammps_commands_instance.add_fix_ave_time(
            "2",
            "all",
            self.nevery,
            self.nrepeat,
            self.nfreq,
            self.lammps_commands_instance.std_list_avetime_properties_mda,
            self.stage_instance.last_instantaneous_file,
        )

        self.lammps_commands_instance.add_variable(
            f"w{self.comp_axis}high", f'"v_{self.comp_axis}hi - {self.wallskin}"'
        )
        self.lammps_commands_instance.add_variable(
            f"w{self.comp_axis}low", f'"v_{self.comp_axis}lo + {self.wallskin}"'
        )

        custom_fixes = [
            f"fix upperW all indent 10 plane {self.comp_axis} v_w{self.comp_axis}high hi units box",
            f"fix lowerW all indent 10 plane {self.comp_axis} v_w{self.comp_axis}low lo units box",
            f"fix dfrm all deform {self.ndeformation} {self.comp_axis} {self.strain_style}rate "
            "${strainrate} units box remap x",
        ]
        self.lammps_commands_instance.add_custom_code(custom_fixes)

        self.lammps_commands_instance.add_dump(
            "1",
            "all",
            "custom",
            self.ndump,
            self.stage_instance.last_lammpstrj_file,
            self.lammps_commands_instance.std_list_dump_properties,
        )
        self.lammps_commands_instance.add_timestep(self.timestep)
        self.lammps_commands_instance.add_run_command(self.nrun)

        # Unfix and Undump
        for fix_id in ["1", "2", "upperW", "lowerW", "dfrm"]:
            self.lammps_commands_instance.add_unfix(fix_id)
        self.lammps_commands_instance.add_undump("1")

        self.stage_instance.substage_nbr += 1

    def preprocess_gui_inputs_into_readable_inputs(self) -> None:
        """
        Preprocess GUI inputs into readable inputs.
        """
        if "true" in self.strain_style.lower():
            self.strain_style = "t"
