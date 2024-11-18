from typing import Optional


class StandardNptStage:
    def __init__(
        self,
        stage_instance,
        lammps_commands_instance,
        temp_initial: float = 298.15,
        temp_final: float = 298.15,
        temp_ncontrol: int = 100,
        pres_initial: float = 1,
        pres_final: float = 1,
        press_ncontrol: int = 100,
        drag: float = 0,
        nreset: int = 1000,
        nevery: int = 1,
        nrepeat: int = 999,
        nfreq: int = 1000,
        ndump: int = 1000,
        timestep: float = 1,
        nrun: int = 100_000,
        set_timestep: int = 0,
        boxdims_changeto: str = "Last trajectory",
        set_cubic: bool = False,
    ) -> None:
        """
        Initialize the StandardNptStage.

        Args:
            stage_instance: The instance of the stage.
            lammps_commands_instance: The instance of lammps_commands.
            temp_initial (float, optional): Initial temperature. Default is 298.15.
            temp_final (float, optional): Final temperature. Default is 298.15.
            temp_ncontrol (int, optional): Temperature control. Default is 100.
            pres_initial (float, optional): Initial pressure. Default is 1.
            pres_final (float, optional): Final pressure. Default is 1.
            press_ncontrol (int, optional): Pressure control. Default is 100.
            drag (float, optional): Drag parameter. Default is 0.
            nreset (int, optional): Reset interval. Default is 1000.
            nevery (int, optional): Repeat interval. Default is 1.
            nrepeat (int, optional): Number of repetitions. Default is 999.
            nfreq (int, optional): Frequency of calculations. Default is 1000.
            ndump (int, optional): Dump frequency. Default is 1000.
            timestep (float, optional): Timestep value. Default is 1.
            nrun (int, optional): Number of simulation steps. Default is 100000.
            set_timestep (int, optional): Set timestep. Default is 0.
            boxdims_changeto (str, optional): Box dimension change method. Default is 'Last trajectory'.
            set_cubic (bool, optional): Set cubic. Default is False.
        """
        self.stage_instance = stage_instance
        self.lammps_commands_instance = lammps_commands_instance
        self.temp_initial = temp_initial
        self.temp_final = temp_final
        self.temp_ncontrol = temp_ncontrol
        self.pres_initial = pres_initial
        self.pres_final = pres_final
        self.press_ncontrol = press_ncontrol
        self.drag = drag
        self.nreset = nreset
        self.nevery = nevery
        self.nrepeat = nrepeat
        self.nfreq = nfreq
        self.ndump = ndump
        self.timestep = timestep
        self.nrun = nrun
        self.set_timestep = set_timestep
        self.boxdims_changeto = boxdims_changeto
        self.set_cubic = set_cubic

    def run(self) -> None:
        """
        Run the standard NPT stage.
        """
        file_npt = (
            f"{self.stage_instance.stage_nbr}.{self.stage_instance.substage_nbr}_npt"
        )
        self.stage_instance.last_lammpstrj_file = f"{file_npt}.lammpstrj"
        self.stage_instance.last_instantaneous_file = f"{file_npt}_instantaneous.out"

        if self.set_timestep is not None:
            self.lammps_commands_instance.add_set_timestep(
                set_timestep_to=self.set_timestep
            )

        title = "NPT-dynamics"
        numbering = (self.stage_instance.stage_nbr, self.stage_instance.substage_nbr)
        description = (
            f"Run {self.nrun} steps with a timestep of {self.timestep}. "
            f"T from {self.temp_initial} to {self.temp_final}. "
            f"Pressure from {self.pres_initial} to {self.pres_final}."
        )
        self.lammps_commands_instance.add_substage_title(
            title=title, numbering=numbering, description=description
        )

        self.lammps_commands_instance.add_thermo_style(
            style_option="custom",
            lst_properties=self.lammps_commands_instance.list_thermo_style_mda,
        )

        additional_commands = ["mtk yes"]
        self.lammps_commands_instance.add_fix_npt(
            fix_id="1",
            fix_subset="all",
            temp_initial=self.temp_initial,
            temp_final=self.temp_final,
            temp_ncontrol=self.temp_ncontrol,
            pres_initial=self.pres_initial,
            pres_final=self.pres_final,
            pres_ncontrol=self.press_ncontrol,
            drag=self.drag,
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

        self.lammps_commands_instance.add_fix_ave_time(
            fix_id="3",
            fix_subset="all",
            nevery=1,
            nrepeat=int(self.timestep * self.nrun) - 1,
            nfreq=int(self.timestep * self.nrun),
            list_of_properties=["v_xlo v_xhi v_ylo v_yhi v_zlo v_zhi"],
            absolute_path_with_file="",
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
        self.lammps_commands_instance.add_custom_change_box(
            fix_id="3",
            boxdims_changeto_style=self.boxdims_changeto,
            setcubic=bool(self.set_cubic),
        )
        self.lammps_commands_instance.add_unfix(fix_id="1")
        self.lammps_commands_instance.add_unfix(fix_id="2")
        self.lammps_commands_instance.add_unfix(fix_id="3")
        self.lammps_commands_instance.add_undump(dump_id="1")

        self.stage_instance.substage_nbr += 1
