class StandardNveStage:
    def __init__(
        self,
        stage_instance,
        lammps_commands_instance,
        nreset: int = 1000,
        nevery: int = 1,
        nrepeat: int = 999,
        nfreq: int = 1000,
        ndump: int = 1000,
        timestep: float = 1,
        nrun: int = 100_000,
        set_timestep: int = 0,
    ) -> None:
        """
        Initialize the StandardNveStage.

        Args:
            stage_instance: The instance of the stage.
            lammps_commands_instance: The instance of lammps_commands.
            nreset (int, optional): Reset interval. Default is 1000.
            nevery (int, optional): Repeat interval. Default is 1.
            nrepeat (int, optional): Number of repetitions. Default is 999.
            nfreq (int, optional): Frequency of calculations. Default is 1000.
            ndump (int, optional): Dump frequency. Default is 1000.
            timestep (float, optional): Timestep value. Default is 1.
            nrun (int, optional): Number of simulation steps. Default is 100000.
            set_timestep (int, optional): Set timestep. Default is 0.
        """
        self.stage_instance = stage_instance  # Instance of Stage class
        self.lammps_commands_instance = lammps_commands_instance
        self.nreset = nreset
        self.nevery = nevery
        self.nrepeat = nrepeat
        self.nfreq = nfreq
        self.ndump = ndump
        self.timestep = timestep
        self.nrun = nrun
        self.set_timestep = set_timestep

    def run(self) -> None:
        """
        Run the standard NVE stage.
        """
        file_nve = (
            f"{self.stage_instance.stage_nbr}.{self.stage_instance.substage_nbr}_nve"
        )
        self.stage_instance.last_lammpstrj_file = f"{file_nve}.lammpstrj"
        self.stage_instance.last_instantaneous_file = f"{file_nve}_instantaneous.out"

        if self.set_timestep is not None:
            self.lammps_commands_instance.add_set_timestep(
                set_timestep_to=self.set_timestep
            )

        title = "NVE-dynamics"
        numbering = (self.stage_instance.stage_nbr, self.stage_instance.substage_nbr)
        description = f"Run {self.nrun} steps with a timestep of {self.timestep}."
        self.lammps_commands_instance.add_substage_title(
            title=title, numbering=numbering, description=description
        )

        self.lammps_commands_instance.add_thermo_style(
            style_option="custom",
            lst_properties=self.lammps_commands_instance.list_thermo_style_mda,
        )

        additional_commands = ["mtk yes"]
        self.lammps_commands_instance.add_fix_nve(
            fix_id="1",
            fix_subset="all",
            nreset=self.nreset,
            lst_of_additional_commands=additional_commands,
        )

        properties = self.lammps_commands_instance.std_list_avetime_properties_mda
        self.lammps_commands_instance.add_fix_ave_time(
            fix_id="2",
            fix_subset="all",
            nevery=self.nevery,
            nrepeat=self.nrepeat,
            nfreq=self.nfreq,
            list_of_properties=properties,
            absolute_path_with_file=self.stage_instance.last_instantaneous_file,
        )

        self.lammps_commands_instance.add_dump(
            dump_id="1",
            dump_subset="all",
            style_option="custom",
            ndump=self.ndump,
            absolute_path_with_file=self.stage_instance.last_lammpstrj_file,
            properties=self.lammps_commands_instance.std_list_dump_properties,
        )

        self.lammps_commands_instance.add_timestep(timestep=self.timestep)
        self.lammps_commands_instance.add_run_command(nsteps=self.nrun)

        self._cleanup()

    def _cleanup(self) -> None:
        self.lammps_commands_instance.add_unfix(fix_id="1")
        self.lammps_commands_instance.add_unfix(fix_id="2")
        self.lammps_commands_instance.add_undump(dump_id="1")
        self.stage_instance.substage_nbr += 1
