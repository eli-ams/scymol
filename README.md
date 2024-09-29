# Scymol

We present **Scymol**, a Python-based software package specifically designed to facilitate the setup and execution of
molecular simulations in LAMMPS. Scymol comes equipped with a user-friendly interface, which simplifies the process of
initializing molecular systems and defining simulation parameters. Moreover, the software generates and executes LAMMPS
simulation sequences, enabling researchers to establish comprehensive simulation schemes, such as heating or deformation
cycles, in a single run.

While this first iteration is limited to the creation of amorphous mixtures of molecules – mainly of hydrocarbon
nature – Scymol intends to establish a solid foundation that is expandable and adaptable to a multitude of simulation
types, gradually encompassing, in an easy-to-use interface – the vast number of functionalities that comprise the LAMMPS
simulation engine.

Through its successful application in diverse research projects and its modular design, Scymol demonstrates considerable
promise as an indispensable tool for researchers aiming to carry out molecular dynamics simulations without sacrificing
complexity or high-throughput capabilities in their methodologies, making the use of MD accessible to researchers
outside the realm of Physics, Chemistry, or Numerical Computing.
![[resources/picture2.png]](resources/picture2.png)

## Installation

Scymol can be installed using one of two methods: 1) Through the `setup.py` script, which generates a complete directory
for Scymol, including its Python environment, dependencies, and precompiled LAMMPS/MPI binaries necessary for running
simulations, or 2) By manually setting up a Python environment, installing all required libraries and dependencies, and
placing the contents of `src.tar` into the directory of the virtual environment.

### 1. Using setup.py

1. Download Scymol's `setup.py` for [Windows](/data/install/windows/scymol_windows.rar) or for Unix-based
   systems ([Ubuntu](/data/install/ubuntu/scymol_linux.tar.xz)).
2. Extract the contents into a directory, namely `/`.
3. Run `python setup.py` to initiate the set up process. Make sure there is Internet connection. This script will create
   a `/scymol` directory, containing Scymol's source files, virtual environment, and all its dependencies. The script
   will also create a shortcut to run Scymol in `/.` *Note: Make sure [distutils](https://pypi.org/project/setuptools/)
   is installed in the Python used to run `setup.py`.*
4. Run `run_scymol.bat` (Windows) or `run_scymol.sh` (Ubuntu) to run Scymol. You can also activate Scymol's virtual
   environment and execute `main.py` from it, using:
   `cd /scymol/`
   `venv/Scripts/python main.py`
   ![[resources/video1.mp4](resources/video1.mp4)]

### 2. Manual setup

1. Create a Python environment (Using [Python 3.7](https://www.python.org/downloads/) or above).
2. Install the following libraries / dependencies:
    - [PyQt5](https://pypi.org/project/PyQt5/)
    - [numpy](https://pypi.org/project/numpy/)
    - [scipy](https://pypi.org/project/scipy/)
    - [matplotlib](https://pypi.org/project/matplotlib/)
    - [pysimm](https://pysimm.org/)
    - [psutil](https://pypi.org/project/psutil/)
    - [sobol_seq](https://pypi.org/project/sobol-seq/)
    - [numba](https://pypi.org/project/numba/)
    - [rdkit](https://pypi.org/project/rdkit/)
    - [file_read_backwards](https://pypi.org/project/file-read-backwards/)
    - [sigfig](https://pypi.org/project/sigfig/)
1. Extract the contents of `src.tar` (located in `/install`) into an accessible `/` folder.
2. Run `main.py`.
3. Once Scymol opens, go to tab `4. Run` and make sure that the absolute paths
   to [LAMMPS'](https://www.lammps.org/download.html) binaries and the parallelization library (
   e.g., [OpenMPI](https://www.open-mpi.org/)) are typed into fields `4.1 LAMMPS` and `4.2 Parallelization`. The command
   displayed in the `Command to run` field should resemble the one used to run other simulations outside Scymol in your
   computer (e.g., `mpiexec -n 4 lmp input.dat`). Scymol executes this command from within the active job's directory,
   located in `/output/{job_id}/mixture_{mixture_nbr}/`; relative paths are to be used with care.

## MPI & LAMMPS

Scymol relies on [LAMMPS'](https://www.lammps.org/download.html) to run simulations and is best executed with a
parallelization library, such as [OpenMPI](https://www.open-mpi.org/). The
automatic installation files provided with Scymol include a precompiled version of both LAMMPS and OpenMPI for exclusive
use with the software. However, users may opt to use their own global versions of LAMMPS and/or MPI. In such cases, it
is essential to adjust the execution commands in Tab 4 ("Run") within Scymol, ensuring that the absolute paths to the
LAMMPS and/or MPI binaries are correctly specified. The final execution command in `Command to run` should match the
format required to run a simulation on the user's system (e.g., `mpiexec -n 4 lmp input.dat`).

## Sample Simulation

A simple simulation that utilizes all of Scymol's functionalities can be executed to ensure the program operates
correctly. Scymol comes preconfigured with the necessary input parameters to perform such a simulation, which involves
the initialization of a naphthalene molecule from a low-density state to its final, condensed form. The steps to run
this simulation are as follows:

- **Molecule Selection**: Click on `Add` under the `1. Molecule Selection` section, and
  select `Load from SMILES string`.
- The SMILES notation for naphthalene, `c1c2ccccc2ccc1`, is preloaded by Default. Assign a name to the molecule and
  press `Ok`.
- **Mixture Setup**: In the `2. Mixture Setup` section, adjust the number of naphthalene molecules from `50` to `100`.
- **Optional LAMMPS Setup**: In the `3. LAMMPS Setup` section, you may optionally check the `3.2 Stages` box and
  double-click on the `LAMMPS Stage 1` box. This allows you to view the different LAMMPS routines that will be executed.
  You can open and review the configuration parameters for each routine, although they can remain at their Default
  values.
- **Run the Simulation**: Under `4. Run`, ensure that the paths to the LAMMPS binary (e.g., LAMMPS.exe) and
  parallelization library binary (e.g., MPIEXEC.exe) are correctly set. The active working directory when executing a
  Job is set by Default to `/output/{job_id}/mixture_{mixture_nbr}/`, targeting the folder `/lammps+mpi` in the root of
  Scymol's directory. Absolute paths can also be used if preferred.
- Verify that the `Command to run` in `Tab 4` matches the command typically used for running LAMMPS/MPI simulations on
  your system. Then, click `Run`.
- A dialog will appear showing the simulation's progress. Once the simulation is complete, close the dialog. In
  the `5. Postprocessing` section, navigate to the folder corresponding to the latest simulation. Within the `mixture_1`
  folder, select any of the `.out` files (e.g., `1.5_uniaxialcompression_instantaneous.out`). Highlight a property of
  interest (e.g., `v_sysdensity`) and right-click to compute the column `Statistics`. You can also highlight two
  properties (e.g., `TimeStep` and `v_sysdensity`) and generate a XY-scatter plot between them.
- To review the input scripts and output files, explore the directory `/output/{job_id}/mixture_{mixture_nbr}/`.
  ![[resources/video2.mp4]](resources/video2.mp4)

## Software Functionalities

Scymol has a user interface that guides users through the necessary steps for simulation setup, ensuring complete
utilization of the software's features. While the interface is important for gathering and organizing user inputs, the
computational capabilities are primarily contained within the backend architecture. These core functionalities, along
with their respective user interface elements, are presented as follows.

### Tab 1 - Molecule Selection

This tab enables users to create a molecular set for use in their simulation. Molecules can be added either through
their [SMILES](https://en.wikipedia.org/wiki/Simplified_Molecular_Input_Line_Entry_System) notation or from a list of
predefined molecule structure files such as [.mol](https://en.wikipedia.org/wiki/Chemical_table_file#Molfile)
and [.pdb](https://en.wikipedia.org/wiki/Protein_Data_Bank). As molecules are loaded, they are added to
a `1.1 List of Molecules` section, their key chemical information is displayed in a `1.2 Description` section, and an
interactive 2D representation appears in a `1.3 Drawing` section. The order of the molecules in the list, which users
can adjust via drag-and-drop, is reflected in the generated LAMMPS input files.
![[resources/picture3.png]](resources/picture3.png)

### Tab 2 - Mixture Setup

This tab provides tools for configuring a molecular mixture. A `2.1 Setup` table lists the molecules loaded in Tab 1 and
allows users to specify the number of each molecule and their initial orientation. The `2.2 Settings` section offers
parameters crucial for the initial placement of molecules in the simulation box without overlap. An `2.3 Information`
section provides an overview of the mixture, including the total number of molecules, average molecular mass, and
molecular formula. A brief description of the UI elements' functionalities is presented next:
`2.1 Setup`
Name: Name of the molecule assigned when loading it.
Number: Number of molecules to be added to the mixture.
Rotate: Randomly rotate the molecule about its geometric center.
`2.2 Settings`
`2.1.1 Number of Mixtures needed` Number of duplicate simulations to perform.
`2.1.2 Initial Density factor` Initial (often lower) density of the box to place the molecules. Lower means more space,
which reduces the possibility of interparticle overlaps.
`2.1.3 Layer offset` Distance from the Z-axis walls to place the molecules away from.
`2.1.4 Distribution method` Selection of the statistical method to evenly place particles around a simulation box.
`2.1.5 Potential energy threshold` Potential energy limit beyond which systems are discarded. The potential energy is
computed using a Lennard-Jones pseudopotential with parameters all set to 1. Potential energy values below 0 indicate
that attractive forces dominate.
`2.1.6 Final density estimate` A rough estimate of final density of the system. This density is used by the LAMMPS
subroutines in case compression or expansion is involved.

![[resources/picture4.png]](resources/picture4.png)

### Tab 3 - LAMMPS Setup

This tab consists of two sections: `3.1 Force Field` and `3.2 Stages`. The Force Field section offers a selection of
commonly used force fields, namely [GAFF](https://ambermd.org/antechamber/gaff.html)
and [GAFF2](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7728379/), [PCFF](http://www.sklogwiki.org/SklogWiki/index.php/PCFF_force_field), [CHARMM](https://academiccharmm.org/),
and [TIP3P](http://www.sklogwiki.org/SklogWiki/index.php/TIP3P_model_of_water). The program loads the atomic types and
charges and checks if the selected force field is applicable to cover all the interactions in the system. The Stages
list lets users design a sequenced list of LAMMPS stages. Each stage added is expandable, revealing a LAMMPS Flowchart
menu, where users can set up a sequence of LAMMPS substages. A library is included to further aid users in setting up
commonly used LAMMPS sequences (e.g., a heat cycle). Furthermore, each substage can be explored into, presenting
configuration options for each substage (e.g., to set the temperature in an isothermal simulation).
![[resources/picture5.png]](resources/picture5.png)
![[resources/picture8.png]](resources/picture8.png)

#### LAMMPS Routine windows

Scymol currently includes seven predefined stages: `Initialize`, `Minimize`, `Velocities`, `NPT`, NVT, `NVE`,
and `UniaxialDeformation`. Future updates are expected to expand this list to incorporate more sophisticated routines,
such as those for computing Cohesive Energy Density. The goal is to develop fully functional LAMMPS stages encapsulated
as modular components that can process outputs from preceding stages, execute specific tasks, and generate inputs
required for subsequent stages of the simulation. For example, the `UniaxialDeformation` module performs NVT
compressions to the simulation box to bring the initialized, but low density system to its final, condensed state.
![[resources/picture9.png]](resources/picture9.png)

### Tab 4 - Run

This tab allows users to specify the location of LAMMPS (`4.1 LAMMPS`) and the parallelization library (e.g.,
MPI) (`4.2 Parallelization`). By Default, the program includes precompiled versions of LAMMPS and MPIEXEC, but users can
choose their own versions. `4.3 Number of Processes` permits users to select the number of cores to be allocated for the
job. When submitting a job, Scymol spawns a `Dialog` window which keeps track of the process' progress. The process can
be forcefully terminated, and its `std out` and `std err` can be tracked in real time. Closing the `Dialog` forces
the `Job` to be terminated just as if `Terminate` were to be pressed.
![[resources/picture11.PNG]](resources/picture11.PNG)

### Tab 5 - Postprocessing

Although not a primary focus of the program, this tab enables users to view log files from previous jobs and to display
computed properties, thereby offering a preliminary view of both computational and physical aspects of the simulations.
Scymol remains active even when jobs are running, enabling users to track the progress of simulations in real time based
on LAMMPS output. This ensures a more detailed update on the simulations' progress without the program freezing or
becoming unresponsive.
![[resources/picture10.PNG]](resources/picture10.PNG)

## Architecture

Schematic of a standard job execution in the program, detailing directories, files, and class relationships. Bolded
rectangles denote independent processes; blue rectangles specify the core directories in Scymol's root. Solid arrows
indicate direct code interactions, and dashed arrows indicate signal-based communication.
![[resources/picture1.png]](resources/picture1.png)
The software architecture includes several directories and files organized functionally within the root directory `/`,
detailed in the following table.

| **Main Directories/Files**             | **Description**                                                                                                                                                                                                                     |
|----------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **`/main.py`**                         | Initializes UI elements, instantiates `MainWindow` class, configures window properties, and maps interface signals to actions.                                                                                                      |
| **`/frontend/`**                       | Custom module responsible for building the UI, containing various Python modules and subdirectories.                                                                                                                                |
| `/frontend/main_window.py`             | Contains the Python class for constructing the UI of Scymol's `MainWindow` instance, including elements from all tabs and the menu bar.                                                                                             |
| `/frontend/lammps_flowchart_window.py` | Contains Python modules for initializing instances of the `LammpsFlowchartWindow` class, crucial for setting up sequential LAMMPS simulation substages through a drag-and-drop interface. Subdirectory: `frontend/dialog_windows/`. |
| `/frontend/molecule.py`                | Creates molecule instances when a user imports molecules, utilizing RDKit's utilities to ensure compatibility with LAMMPS.                                                                                                          |
| `/frontend/static_functions.py`        | Standalone Python module with utility functions for common tasks like computing chemical information and file I/O operations.                                                                                                       |
| `/frontend/dialog_windows/`            | Contains modules for initializing dialog windows directly triggered from the `MainWindow` instance.                                                                                                                                 |
| `/frontend/custom_widgets/`            | Focuses on the creation and customization of widgets that introduce custom functionalities or override standard widget behavior.                                                                                                    |
| `/frontend/context_menus/`             | Organizes Python files required for initializing instances of context menus, which may offer numerous options and submodules.                                                                                                       |
| **`/front2back/`**                     | Links frontend's state with backend's input requirements for molecular systems, comprising various Python modules.                                                                                                                  |
| `/front2back/BackendConnector.py`      | Translates UI interactions into an `inputs.py` file and manages the lifecycle of backend simulation processes.                                                                                                                      |
| `/front2back/RunningProcessDialog.py`  | Creates a dialog window instance to display simulation output and allows for simulation termination.                                                                                                                                |
| `/front2back/BackendThread.py`         | Spawns a subprocess to run newly submitted jobs, capturing stdout and stderr in a log file for real-time feedback.                                                                                                                  |
| `/front2back/DataExtractor.py`         | Extracts data from UI widgets into a dictionary for generating the `inputs.py` file by `BackendConnector.py`.                                                                                                                       |
| **`/backend/`**                        | Specialized module responsible for executing simulations, functioning independently and relying on the `inputs.py` file.                                                                                                            |
| `/backend/lammps_commands.py`          | Houses the `LammpsCommands` class, offering methods for defining and appending LAMMPS commands to a simulation script.                                                                                                              |
| `/backend/lammps_stages.py`            | Introduces the `LammpsStage` class, central to generating full LAMMPS scripts by calling commands from `LammpsCommands`.                                                                                                            |
| `/backend/molecule.py`                 | Contains the `Molecule` class for creating instances based on SMILES strings, using Rdkit's functionalities for molecule initialization, minimization, and equilibration.                                                           |
| `/backend/mixture.py`                  | Contains the `Mixture` class, providing methods for mixture-wide computations, including molecule sorting, force field assignment, and potential energy calculations.                                                               |
| `/backend/pysimm_system.py`            | Interfaces with the PySIMM library to translate RdKit objects into LAMMPS-compatible inputs.                                                                                                                                        |
| `/backend/inputs.py`                   | Fundamental file containing comprehensive input parameters and configurations for backend operations.                                                                                                                               |
| `/backend/log_functions.py`            | Responsible for logging job executions, creating log files with varying detail levels to aid in debugging and tracking progress.                                                                                                    |
| `/backend/static_functions.py`         | Similar to frontend's module, offering functions for common tasks, ensuring backend's independence.                                                                                                                                 |
| `/backend/main.py`                     | Pivotal for running a complete job, operating independently of frontend and front2back modules, relying solely on the `inputs.py` file.                                                                                             |
| `/backend/lammps_presets_library.py`   | Contains predefined LAMMPS substages, offering options like Initialize, Minimize, Velocities, NPT, NVT, NVE, and Uniaxial Deformation for simulations.                                                                              |
| **`/env/`**                            | Houses the `python/`, `mpi/`, and `lammps/` subdirectories containing precompiled versions of Python, MPI, and LAMMPS, enabling Scymol to run without external dependencies.                                                        |

## License

Scymol is licensed under the GNU General Public License (GPL), which is a widely used free software license that
guarantees end users the freedom to run, study, share, and modify the software. The GPL license aims to ensure that the
software remains free and open-source for all its users. For detailed terms and conditions, please refer to the full
license text. The full text of the GPL license can be found at the official GNU website or included directly within this
documentation. For the full GPL license text, you may visit
the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html) website.

## Credits

Scymol was created by Eli I. Assaf (e.i.assaf@tudelft.nl), Elsa Maalouf (em40@aub.edu.lb), Xueyan Liu (
x.liu@tudelft.nl), and Sandra Erkens (s.m.j.g.erkens@tudelft.nl). To cite, please refer to the manuscript (TBD).