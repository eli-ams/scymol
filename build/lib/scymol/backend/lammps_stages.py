import os
import subprocess
import time
import lammps_functions as lf
import log_functions
from scymol.backend.lammps_presets_library.uniaxial_deformation import (
    StandardDeformationStage,
)
from scymol.backend.lammps_presets_library.nvt import StandardNvtStage
from scymol.backend.lammps_presets_library.npt import StandardNptStage
from scymol.backend.lammps_presets_library.velocities import StandardVelocitiesStage
from scymol.backend.lammps_presets_library.minimization import (
    StandardMinimizationSubstage,
)
from scymol.backend.lammps_presets_library.initialization import (
    StandardInitializationSubstage,
)
from scymol.backend.lammps_presets_library.nve import StandardNveStage
from scymol.backend.lammps_commands import LammpsCommands
from typing import Dict, Any, Tuple, Optional


class LammpsStages:
    stage_nbr = 0

    def __init__(
        self,
        last_lammpstrj_file: str = None,
        last_instantaneous_file: str = None,
        stage_nbr: int = None,
        logfile: str = None,
        **kwargs,
    ):
        """
        Initialize a LammpsStages instance.

        Args:
            last_lammpstrj_file (str, optional): The path to the last LAMMPS trajectory file.
            last_instantaneous_file (str, optional): The path to the last instantaneous data file.
            stage_nbr (int, optional): The stage number.
            logfile (str, optional): Name of the log file.
            **kwargs: Additional keyword arguments.

        Attributes:
            lammps_commands_instance (LammpsCommands): An instance of the LammpsCommands class.
            substage_nbr (int): The substage number (initialized to 1).
            params (dict): Additional parameters specified as keyword arguments.
            last_lammpstrj_file (str): The path to the last LAMMPS trajectory file.
            last_instantaneous_file (str): The path to the last instantaneous data file.
            last_instantaneous_data (Any): Parsed instantaneous data (initialized to None).
            last_lammpstrj_data (Any): Parsed trajectory data (initialized to None).
            lammps_input_script_file (str): The path to the LAMMPS input script file (initialized to None).

        Note:
            The `**kwargs` parameter allows you to pass additional parameters as keyword arguments,
            which will be stored in the `params` attribute.
        """
        self.lammps_commands_instance = LammpsCommands()
        self.stage_nbr = stage_nbr
        self.logfile = logfile
        self.substage_nbr = 1
        self.params = kwargs
        self.last_lammpstrj_file = last_lammpstrj_file
        self.last_instantaneous_file = last_instantaneous_file
        self.last_instantaneous_data = None
        self.last_lammpstrj_data = None
        self.lammps_input_script_file = None

    def call_methods(self, stage: Dict[str, Any]) -> None:
        """
        Generate a LAMMPS script for a given stage with specified methods and parameters.

        Args:
            stage (dict): A dictionary containing information about the stage.
                It should have keys 'stage' (str) and 'methods' (list of dicts).
                Each method dictionary should have keys 'name' (str) and 'params' (dict).

        Raises:
            AttributeError: If the specified method is not found in the current class or LammpsCommands.

        Returns:
            None
        """
        stage_name = stage["stage"]

        log_functions.print_to_log(
            logfile=self.logfile,
            message=f"Generating LAMMPS script for stage: {stage_name}.",
        )

        for method_config in stage["methods"]:
            method_name = method_config["name"]
            params = method_config["params"]
            try:
                # Try to get the method from the current instance (self)
                method_to_call = getattr(self, method_name)
            except AttributeError:
                try:
                    # If it fails, try to get the method from the LammpsCommands class
                    method_to_call = getattr(self.lammps_commands_instance, method_name)
                except AttributeError:
                    raise AttributeError(
                        f"Error: Method {method_name} not "
                        f"found in {self.__class__.__name__} or LammpsCommands"
                    )
            method_to_call(**params)
        self.write_script(lammps_input_script_file=f"{stage_name}.in")

    def write_script(self, lammps_input_script_file: str) -> None:
        """
        Write a LAMMPS input script to a specified file.

        Args:
            lammps_input_script_file (str): The name of the file where the LAMMPS input script will be written.

        Returns:
            None
        """
        with open(lammps_input_script_file, "w") as f:
            f.write("\n".join(self.lammps_commands_instance.script))
        self.lammps_input_script_file = lammps_input_script_file

    def standard_initialization_substage(self, **params: Any) -> None:
        """
        Perform standard initialization substage for LAMMPS Molecular Dynamics simulations.

        Args:
            **params: Keyword arguments for configuring the initialization substage.

        Returns:
            None
        """
        minimization_stage_instance = StandardInitializationSubstage(
            stage_instance=self,
            lammps_commands_instance=self.lammps_commands_instance,
            **params,
        )
        minimization_stage_instance.run()

    def standard_minimization_substage(self, **params: Any) -> None:
        """
        Perform standard minimization substage for LAMMPS Molecular Dynamics simulations.

        Args:
            **params: Keyword arguments for configuring the minimization substage.

        Returns:
            None
        """
        minimization_stage_instance = StandardMinimizationSubstage(
            stage_instance=self,
            lammps_commands_instance=self.lammps_commands_instance,
            **params,
        )
        minimization_stage_instance.run()

    def standard_velocities_stage(self, **params: Any) -> None:
        """
        Perform standard velocities stage for LAMMPS Molecular Dynamics simulations.

        Args:
            **params: Keyword arguments for configuring the velocities stage.

        Returns:
            None
        """
        velocities_stage_instance = StandardVelocitiesStage(
            stage_instance=self,
            lammps_commands_instance=self.lammps_commands_instance,
            **params,
        )
        velocities_stage_instance.run()

    def standard_npt_stage(self, **params: Any) -> None:
        """
        Perform standard NPT (constant Number, Pressure, and Temperature) stage for LAMMPS Molecular Dynamics simulations.

        Args:
            **params: Keyword arguments for configuring the NPT stage.

        Returns:
            None
        """
        npt_stage_instance = StandardNptStage(
            stage_instance=self,
            lammps_commands_instance=self.lammps_commands_instance,
            **params,
        )
        npt_stage_instance.run()

    def standard_nvt_stage(self, **params: Any) -> None:
        """
        Perform standard NVT (constant Number, Volume, and Temperature) stage for LAMMPS Molecular Dynamics simulations.

        Args:
            **params: Keyword arguments for configuring the NVT stage.

        Returns:
            None
        """
        nvt_stage_instance = StandardNvtStage(
            stage_instance=self,
            lammps_commands_instance=self.lammps_commands_instance,
            **params,
        )
        nvt_stage_instance.run()

    def standard_nve_stage(self, **params: Any) -> None:
        """
        Perform standard NVE (constant Number, Volume, and Energy) stage for LAMMPS Molecular Dynamics simulations.

        Args:
            **params: Keyword arguments for configuring the NVE stage.

        Returns:
            None
        """
        nve_stage_instance = StandardNveStage(
            stage_instance=self,
            lammps_commands_instance=self.lammps_commands_instance,
            **params,
        )
        nve_stage_instance.run()

    def standard_uniaxial_deformation_stage(self, **params: Any) -> None:
        """
        Perform standard uniaxial deformation stage for LAMMPS Molecular Dynamics simulations.

        Args:
            **params: Keyword arguments for configuring the uniaxial deformation stage.

        Returns:
            None
        """
        deformation_stage_instance = StandardDeformationStage(
            stage_instance=self,
            lammps_commands_instance=self.lammps_commands_instance,
            **params,
        )
        deformation_stage_instance.run()

    def run(
        self,
        run_command: str,
    ) -> None:
        """
        Run a LAMMPS simulation using the specified number of CPU cores.

        Args:
            run_command (str): The command that is going to be executed (e.g., "mpiexec -n 4 lmp -in stage_1.in")

        Raises:
            Exception: If the LAMMPS run fails, an exception is raised with an error message.

        Returns:
            None
        """
        time_init = time.time()

        # Construct the command. Split into a list of commands instead of one string of command.
        cmd = run_command.split(" ")

        # Run the command and capture the error message if there is one
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Capture the standard output from LAMMPS
        lammps_out = proc.stdout.decode()

        if proc.returncode != 0:
            try:
                # with open(file='../../log.txt', mode='a') as f:
                #     f.write(lammps_out)
                pass
            except FileNotFoundError:
                pass

            error_message = proc.stderr.decode()
            raise Exception(
                f"LAMMPS run failed with return code: {proc.returncode}. Error message: {error_message}"
            )
        else:
            # with open(file='../../log.txt', mode='a') as f:
            #     f.write(lammps_out)
            log_functions.print_to_log(
                logfile=self.logfile,
                message=f"LAMMPS run completed after {time.time() - time_init: .2f} s.",
            )

    def write_last_trajectory(self) -> None:
        """
        Read the last trajectory from a file and write it into a new file named 'last.lammpstrj'.

        Raises:
            FileNotFoundError: If the last LAMMPS trajectory file is not found.

        Returns:
            None
        """
        # Check if the last_lammpstrj_file is None
        if self.last_lammpstrj_file is None:
            raise FileNotFoundError("Last LAMMPS trajectory file is not specified.")

        # Read the last trajectory from the specified file
        header, data = lf.get_last_trajectory(file_name=self.last_lammpstrj_file)

        # Modify the timestep in the header
        header[1] = "0"

        # Write the last trajectory into 'last.lammpstrj' file
        with open(file="last.lammpstrj", mode="w") as f:
            f.write("\n".join(header + data))

    def parse_last_trajectory(self) -> Tuple[Optional[Any], Optional[Any]]:
        """
        Parse the last LAMMPS trajectory and instantaneous data if available.

        Returns:
            Tuple[Optional[Any], Optional[Any]]: A tuple containing parsed trajectory data
            and parsed instantaneous data (if available). Both elements are optional.
        """
        # Check if the last_lammpstrj_file is None
        if self.last_lammpstrj_file is None:
            raise FileNotFoundError("Last LAMMPS trajectory file is not specified.")

        # Assuming header and data are needed to parse trajectory information,
        # so get them again here. Consider more efficient methods if needed.
        header, data = lf.get_last_trajectory(file_name=self.last_lammpstrj_file)

        # Parsing trajectory information:
        self.last_lammpstrj_data = lf.parse_trajectory(header=header, data=data)

        # Reading and parsing instantaneous data:
        if "minimization" in self.last_lammpstrj_file.lower():
            self.last_instantaneous_data = None
        else:
            self.last_instantaneous_data = lf.read_avetime_dump_file(
                file_name=self.last_instantaneous_file
            )

        return self.last_lammpstrj_data, self.last_instantaneous_data
