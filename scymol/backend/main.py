import argparse
import copy
import importlib
import json
import os
import shutil
import time

import scymol.backend.backend_static_functions as backend_static_functions
import scymol.backend.inputs as inputs
import scymol.backend.log_functions as log_functions
from scymol.backend.lammps_stages import LammpsStages
from scymol.backend.mixture import Mixture
from scymol.backend.pysimm_system import PysimmSystem


class JobRunner:
    def __init__(self, job_id: str) -> None:
        """
        Initialize a JobRunner instance.

        This constructor method initializes the JobRunner instance with the provided job ID.
        It also sets initial values for instance variables, creates a log file, and prepares for the job.

        :param job_id: The identifier for the current job.
        :type job_id: str
        :return: None
        """

        # Setting up job directory
        try:
            # Create the output/ directory for the job.
            os.makedirs(
                importlib.resources.files("scymol").joinpath("output", f"{args.id}"),
                exist_ok=False,
            )
        except FileExistsError:
            raise FileExistsError(
                f"Directory output/{args.id}/ already exists! Cannot submit a job there."
            )

        # Initialize instance variables with default values.
        self.pysimm_working_dir = None
        self.job_id = job_id
        self.logfile = self.create_log_file()
        self.nbr_of_mixtures_accepted = 0
        self.trial_i = 1

    def create_log_file(self) -> str:
        """
        Create a log file for the current job.

        This method creates a log file in the specified directory and returns the path
        to the created log file.

        :return: The path to the created log file.
        :rtype: str
        """
        log_file = log_functions.create_log_file(
            logdir=str(
                importlib.resources.files("scymol").joinpath("output", f"{self.job_id}")
            ),
            constant=True,
        )
        return log_file

    def create_directories(self) -> None:
        """
        Create directories based on the specified run mode.

        This method checks the `run_mode` specified in `inputs` and creates directories accordingly
        in the 'output' folder.

        :return: None
        """
        # Check the run mode to determine directory structure.
        if inputs.run_mode == "mixture+pysimm+lammps":

            os.makedirs(
                importlib.resources.files("scymol").joinpath(
                    "output",
                    f"{self.job_id}",
                    f"mixture_{self.nbr_of_mixtures_accepted}",
                ),
                exist_ok=True,
            )

        elif inputs.run_mode == "from_previous_lammps":
            # Create directory for 'from_previous_lammps' run mode.
            os.makedirs(
                importlib.resources.files("scymol").joinpath(
                    "output",
                    f"{self.job_id}",
                    f"mixture_{self.nbr_of_mixtures_accepted}",
                ),
                exist_ok=True,
            )

    def generate_pysimm(self, mixture) -> None:
        """
        Generate Pysimm system and LAMMPS inputs for a mixture.

        This method performs the following steps:
        1. Exports molecules in the mixture to *.mol files.
        2. Initializes and sets up a Pysimm system.
        3. Generates LAMMPS topologies (e.g., structure.data file) needed for the simulation.

        :param mixture: The mixture of molecules to be used for the simulation.
        :return: None
        """
        # Create a Pysimm system and set up LAMMPS inputs.
        pysimm_system = PysimmSystem(
            mixture=mixture, working_dir=self.pysimm_working_dir
        )
        pysimm_system.initialize_system()
        pysimm_system.load_all_molecules_into_system()
        pysimm_system.set_box_dimensions()

        # Generating structure data file for LAMMPS simulation from pysimm_system:
        ref_dir = os.getcwd()
        os.chdir(path=f"{self.pysimm_working_dir}/")
        pysimm_system.generate_lammps_inputs()
        os.rename(src="temp.lmps", dst="structure.data")
        os.remove("pysimm.sim.in")
        os.chdir(path=ref_dir)

    def generate_and_run_lammps(self) -> None:
        """
        Generate and run LAMMPS simulations for a mixture.

        This method prepares and runs LAMMPS simulations for the specified stages using the provided
        input methods. It iterates through the stages, runs them, and keeps track of the previous stage
        for data processing.

        :return: None
        """
        # Store the current working directory for later reference.
        ref_dir = os.getcwd()

        # Change directory to the LAMMPS working directory.
        os.chdir(path=f"{self.pysimm_working_dir}/")

        # Initialize previous LAMMPS stage as None.
        previous_lammps_stage = None

        # Iterate through the LAMMPS stages and methods.
        for stage_nbr, stage in enumerate(inputs.lammps_stages_and_methods):
            if previous_lammps_stage is not None:
                # Process data from the previous LAMMPS stage.
                previous_lammps_stage.write_last_trajectory()
                (
                    lammpstrj_data,
                    instantaneous_data,
                ) = previous_lammps_stage.parse_last_trajectory()

            # Create a new LAMMPS stage and call the specified methods.
            lammps_stage = LammpsStages(stage_nbr=stage_nbr + 1, logfile=self.logfile)
            lammps_stage.call_methods(stage)

            # Print messages to the log.
            log_functions.print_to_log(
                logfile=self.logfile,
                message=f"LAMMPS stages:\n{json.dumps(stage, indent=4)}\n",
            )
            log_functions.print_to_log(
                logfile=self.logfile,
                message=f"Mixture {self.nbr_of_mixtures_accepted} | Running LAMMPS stage {stage['stage']}...",
            )

            # Run the LAMMPS stage with the specified settings.
            lammps_stage.run(
                run_command=inputs.run_command.replace("-in stage_1.in",
                                                       f"-in stage_{stage_nbr + 1}.in"),
            )

            # Update the previous LAMMPS stage for data processing.
            previous_lammps_stage = copy.deepcopy(lammps_stage)

        # Change back to the original working directory.
        os.chdir(path=ref_dir)

    def run_trials(self) -> None:
        """
        Run a series of trials to create mixtures and perform simulations.

        This method iterates through multiple trials, creating mixtures and conducting simulations based
        on the specified run mode. It also logs the progress and completion time for each trial.

        :return: None
        """
        while self.trial_i <= inputs.number_of_trials:
            # Record the start time of the current trial.
            trial_start_time = time.time()

            if inputs.run_mode == "mixture+pysimm+lammps":
                # Create a new Mixture instance.
                mixture = Mixture()

                # Log information about the current mixture.
                log_functions.print_to_log(
                    logfile=self.logfile,
                    message=f"Mixture {self.nbr_of_mixtures_accepted + 1} | Initializing atomic positions (Attempt {self.trial_i})",
                )

                # Generate the mixture and proceed if accepted.
                if self.generate_mixture(mixture):
                    self.nbr_of_mixtures_accepted += 1
                    self.trial_i = 0
                    self.create_directories()
                    self.pysimm_working_dir = importlib.resources.files(
                        "scymol"
                    ).joinpath(
                        "output",
                        f"{self.job_id}",
                        f"mixture_{self.nbr_of_mixtures_accepted}",
                    )
                    self.generate_pysimm(mixture)
                    self.generate_and_run_lammps()

                    # Exit loop if the number_of_mixtures_needed has been reached.
                    if (
                        self.nbr_of_mixtures_accepted
                        == inputs.number_of_mixtures_needed
                    ):
                        break

            elif inputs.run_mode == "from_previous_lammps":
                self.nbr_of_mixtures_accepted += 1
                self.create_directories()
                self.pysimm_working_dir = importlib.resources.files("scymol").joinpath(
                    "output",
                    f"{self.job_id}",
                    f"mixture_{self.nbr_of_mixtures_accepted}",
                )
                shutil.copy(
                    os.path.join("front2back/temp_files", "temp.lmps"),
                    os.path.join(f"{self.pysimm_working_dir}", f"structure.data"),
                )

                shutil.copy(
                    os.path.join("front2back/temp_files", "last.lammpstrj"),
                    os.path.join(f"{self.pysimm_working_dir}", f"last.lammpstrj"),
                )

                self.generate_and_run_lammps()

            # Log the completion time for the current trial.
            log_functions.print_to_log(
                logfile=self.logfile,
                message=f"Mixture {self.nbr_of_mixtures_accepted + 1} | "
                f"Mixture completed after {time.time() - trial_start_time: .2f}s.",
            )

            # Increment the trial counter.
            self.trial_i += 1

    @staticmethod
    def generate_mixture(mixture) -> bool:
        """
        Generate a mixture of molecules and calculate LJ potential energy and return True if its energy is below a threshold.

        This method generates a mixture of molecules, performs the following steps:
        1. Generates Sobol positions for the mixture.
        2. Translates molecules to Sobol positions.
        3. Calculates the Lennard-Jones (LJ) potential energy for the mixture.
        4. Returns True if the energy computed is less than 'inputs.potential_energy_limit'.

        :param mixture: The mixture of molecules to be generated and analyzed.
        :return: True if the mixture is accepted, False otherwise.
        :rtype: bool
        """
        # Generate Sobol positions for the mixture.
        mixture.generate_sobol_positions()

        # Translate molecules to Sobol positions.
        mixture.translate_molecules_to_sobol_positions()

        # Calculate the LJ potential energy for the mixture.
        mixture.calculate_lj_potential_energy()

        # Return whether the mixture is accepted.
        return mixture.accepted

    def run(self) -> None:
        """
        Run the program for creating mixtures and conducting trials.

        This method performs the following steps:
        1. Records the start time of the program.
        2. Clears the output/ folder associated with the job.
        3. Creates mixtures and runs trials.
        4. Logs the program's successful termination and runtime.

        :return: None
        """
        # Record the start time of the program.
        start_time = time.time()

        # Clear the output/ folder associated with the job.
        backend_static_functions.clear_folder(
            folder_path=importlib.resources.files("scymol").joinpath(
                "output", f"{self.job_id}"
            )
        )

        # Print a log message indicating the start of mixture creation.
        log_functions.print_to_log(
            logfile=self.logfile, message=f"Creating mixtures..."
        )

        # Run trials to generate mixtures.
        self.run_trials()

        # Calculate and print the program's runtime.
        log_functions.print_to_log(
            logfile=self.logfile,
            message=f"Program run terminated successfully after {time.time() - start_time: .2f}s.",
        )


def main(job_id: str) -> None:
    """
    Main function to initialize and run a job.

    This function initializes and manages the execution of a job based on a given job ID.
    It ensures that the necessary directories are created, initializes the job runner,
    logs the initialization, and then runs the job.

    Steps:
    1. Creates the output/ directory for the job.
    2. Initializes a JobRunner instance for the specified job.
    3. Logs the successful initialization of the program.
    4. Runs the JobRunner to execute the job.

    This script can be used independently of the frontend and front2back modules,
    as long as the inputs.py file exists and contains all the information necessary to run a simulation.
    To execute a simulation using only the backend, the user must call:

    Example Usage:
    ```python
    if __name__ == "__main__":
        job_id = sys.argv[1]
        main(job_id)
    ```

    The `job_id` should be an integer that uniquely identifies the job's output/ directory.
    The results will be stored in the 'output/' directory as 'output/{job_id}/'.

    :param job_id: The identifier for the current job.
    :type job_id: str
    :return: None
    :raises FileExistsError: If the output/ directory for the job already exists.
    """
    # Initialize a JobRunner instance for the job.
    job_runner = JobRunner(job_id)

    # Log a message indicating successful program initialization.
    log_functions.print_to_log(
        logfile=job_runner.logfile, message=f"Successfully initialized program."
    )

    # Run the JobRunner to execute the job.
    job_runner.run()


if __name__ == "__main__":
    try:
        job_directory = os.getcwd()
        print("job dir: ", job_directory)
        parser = argparse.ArgumentParser(description="Run a job with a specified ID.")
        parser.add_argument(
            "--id", required=True, help="The identifier for the current job."
        )
        args = parser.parse_args()
        main(args.id)
    except RuntimeError as e:
        raise RuntimeError(f"Error: {e}")
