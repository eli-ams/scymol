# Scymol

**Build molecular systems, design LAMMPS protocols, run simulations, and inspect results in one graphical workspace.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![LAMMPS](https://img.shields.io/badge/MD-LAMMPS-1F4E79)](https://www.lammps.org/)
[![Version](https://img.shields.io/badge/version-2.0.0-00A6A6)](pyproject.toml)
[![License: GPL v3](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)

<p align="center">
  <img src="markdown_resources/results-browser.gif" alt="Scymol playing a LAMMPS trajectory in the integrated 3D viewer">
</p>

Scymol is a PySide6 desktop workbench for molecular simulations with [LAMMPS](https://www.lammps.org/). It keeps molecular definitions, generated structures, protocols, execution history, and results in a portable project directory while leaving all generated inputs open for inspection.

Scymol 2.0 is a complete redesign of the original Scymol: project-based state, direct system import, graphical protocol branches, live execution, integrated 3D inspection, and reproducible artifact tracking now form one five-stage workflow.

```text
Define or import  →  Build or reuse  →  Design protocol  →  Prepare and run  →  Inspect
     System             Structure           Protocol             Run             Results
```

## Highlights

- Draw molecules or enter SMILES; build multi-species systems with explicit counts.
- Import LAMMPS data files and dump trajectories while preserving compatible topology, types, charges, coefficients, and coordinates.
- Generate conformers, pack seeded Sobol distributions with clash rejection, and assign force fields through [PySIMM](https://pysimm.org/).
- Build validated branching protocols; every root-to-leaf path becomes a separate LAMMPS input script.
- Run, monitor, cancel, and retry simulations from the interface.
- Inspect structures, trajectories, logs, tables, statistics, and plots; manifests and signatures flag stale downstream artifacts.

## Workflow

### 1. Define or import a system

In **Build** mode, draw or enter each species, name it, set its copy count, and validate the definition. The 2D editor supports atoms, bonds, chains, rings, cleanup, undo/redo, and image export.

<p align="center">
  <img src="markdown_resources/system-editor.gif" alt="Defining a multi-species molecular system in Scymol">
</p>

In **Import** mode, load a LAMMPS data file, a dump trajectory, or both. A data file provides coordinates, topology, atom types, and any included coefficients. A paired trajectory replaces its coordinates with the last frame while retaining the data-file topology. Without a data file, Scymol can convert the last trajectory frame into a reusable structure and infer connectivity; this approximation must be reviewed. Trajectories contain no force-field coefficients, so direct reuse requires compatible coefficients elsewhere in the LAMMPS input.

### 2. Build or reuse the structure

For a new system, Scymol generates conformers, estimates a box from the target density, places molecules with a seeded Sobol sequence, rejects steric clashes, and optionally applies random rotations. PySIMM assigns the selected force field and charge model and writes `structure.data`.

Current choices are GAFF2, GAFF, Dreiding, and PCFF. Successful generation does not establish that a force field is scientifically suitable for the modeled chemistry. A compatible imported data file with complete topology and coefficients can be reused instead of regenerated.

<p align="center">
  <img src="markdown_resources/structure-viewer.gif" alt="Inspecting a packed and parameterized molecular structure">
</p>

### 3. Design the protocol

The Protocol editor is a directed acyclic graph with nodes for initialization, minimization, velocity creation, NVT, NPT, NVE, and deformation. Each node has typed parameters, immediate validation, and a preview of its LAMMPS commands. Every root-to-leaf branch is compiled into its own `protocol_*.in` file for explicit alternatives and higher-throughput studies.

<p align="center">
  <img src="markdown_resources/protocol-editor.gif" alt="Building and inspecting a LAMMPS protocol graph">
</p>

### 4. Prepare and run LAMMPS

The Run stage copies the selected structure into an independent simulation directory, writes protocol scripts and a manifest, and launches the selected path. The default command is:

```text
lmp -in "{script}"
```

Commands may use `{script}`, `{script_path}`, and `{output_dir}`, allowing local, MPI, or cluster launchers. Standard output and errors appear live; runs can be cancelled, inspected, and retried.

<p align="center">
  <img src="markdown_resources/run-workspace.gif" alt="Following a prepared LAMMPS simulation and its live output">
</p>

### 5. Inspect results

Scymol opens structures and dump trajectories in its 3D viewer; `log.lammps` and other numeric files as tables and plots; and scripts or text files in a text viewer. Numeric columns support descriptive statistics plus line and scatter plots. The ModernGL viewer handles orthogonal and triclinic cells, playback, camera controls, periodic-boundary reconstruction, and large scenes.

## Installation

Scymol requires Python 3.10+ and an OpenGL-capable system for 3D viewing. PySIMM is needed to generate and parameterize structures; LAMMPS is needed to run simulations. Neither is required to edit protocols or inspect compatible existing results. Some GAFF-family systems need a LAMMPS build with `EXTRA-MOLECULE`, including `dihedral_style fourier`; see [`lammps.txt`](lammps.txt).

### Conda on Linux (recommended)

The `eli.ams` package supplies Scymol 2.0.0 and PySIMM 1.1; `conda-forge` supplies the remaining dependencies, OpenMPI, and a tested LAMMPS release:

```bash
conda create -n scymol \
  --override-channels \
  -c eli.ams \
  -c conda-forge \
  scymol=2.0.0
conda activate scymol
scymol
```

`--override-channels` prevents unrelated configured channels from being mixed into the environment. The package constrains LAMMPS to the tested range `>=2024.08.29,<2025.07.22`; configure another compatible executable through **Tools → LAMMPS execution setup** if needed. Verify the bundled command with `lmp -help`.

### pip

Install PySIMM 1.1 from its upstream archive before installing Scymol from PyPI. Pip does not install operating-system LAMMPS or MPI executables.

```bash
python -m pip install --upgrade pip
python -m pip install https://github.com/polysimtools/pysimm/archive/refs/tags/1.1.zip
python -m pip install scymol
scymol
```

Scymol discovers compatible system executables. Inspect, test, or change the selection through **Tools → LAMMPS execution setup**.

### Automated Windows venv installer

On 64-bit Windows with Python 3.10+, download [`windows-venv-setup.py`](distributables/windows-venv-setup.py). It creates a private installation under `%LOCALAPPDATA%\Scymol`:

```powershell
python windows-venv-setup.py
```

Verify the downloaded installer first:

```powershell
Get-FileHash .\windows-venv-setup.py -Algorithm SHA256
```

Expected SHA-256 for the Scymol 2.0.0 installer:

```text
A6668DDBA0A69F667B028FA423F66D78E0014E0FA1F2D9ADDB90A3AC712DB5E9
```

The standard-library installer creates a venv, installs PySIMM 1.1 and Scymol 2.0.0, verifies and extracts the Windows LAMMPS/MPI bundle, checks serial and local MPI execution, and creates `Scymol.bat` and `Scymol-console.bat`. It does not modify the system Python or global `PATH`; use `--install-dir` to choose another location. On first launch, open **Tools → LAMMPS execution setup** and select **Test and save**.

### Manual Windows LAMMPS/MPI bundle

As an alternative for 64-bit Windows, download [`lammps+mpi_win64.zip`](distributables/lammps+mpi_win64.zip), reused from Scymol 1.0, and extract the complete archive so its executables and DLLs remain together. In **Tools → LAMMPS execution setup**, select `LAMMPS.exe` and `mpiexec.exe`, choose the MPI process count, and click **Test and save**. Scymol runs a packaged smoke test before accepting the configuration. This bundle is optional; an existing compatible installation can always be used.

### From source

From a repository clone:

```bash
conda create -n scymol python=3.12
conda activate scymol
python -m pip install https://github.com/polysimtools/pysimm/archive/refs/tags/1.1.zip
python -m pip install -e .
scymol
```

Alternatively run `python run_gui.py`. If LAMMPS is installed, ensure `lmp` is on `PATH` or configure the absolute executable and command, for example `mpiexec -n 8 lmp -in "{script}"`.

## Quick start

1. Launch Scymol and choose **Create a molecular system**.
2. Draw or enter the molecules, set their copy counts, and validate the system.
3. Choose density, packing, force-field, and charge settings; build the structure.
4. Review `structure.data` in the 3D viewer.
5. Build or edit the protocol graph and validate it.
6. Select **Prepare simulation** to generate the scripts.
7. Confirm the execution command and run a protocol path.
8. Inspect trajectories, logs, tables, and plots in Results.

Select the **50-benzene tutorial** at startup, or choose **Help → Guided tutorial**, for a guided example.

## Project format

Scymol keeps editable state and generated artifacts in the user-selected project directory; it does not create a shared global workspace.

```text
my-project/
├── scymol.json
└── output/
    ├── system/
    │   ├── system.pdb
    │   ├── system_manifest.json
    │   ├── molecule_pdbs/
    │   └── imported/
    ├── structure/
    │   ├── structure.data
    │   ├── structure_manifest.json
    │   └── mol_files/
    └── simulation/
        ├── structure.data
        ├── run_manifest.json
        └── protocol_*.in
```

`scymol.json` stores editable project state. Manifests record the settings and sources used to produce generated files; stable signatures warn when upstream changes make downstream artifacts stale.

## Scientific scope

Scymol helps construct, execute, and audit molecular-simulation workflows. It does not decide whether a force field, charge model, ensemble, time step, duration, or observable is appropriate. Review generated structures and LAMMPS scripts before production use, and validate models and protocols against suitable experiments, literature, or trusted calculations.

Scymol is under active development. Import compatibility depends on the available source information; optional scientific backends may impose additional platform and chemistry limits.

## Development

The project model and scientific workflow are separated from the Qt interface:

```text
repository/
├── conda-recipe/
├── distributables/
│   ├── windows-venv-setup.py
│   └── lammps+mpi_win64.zip
├── src/scymol/
│   ├── gui/                 # interface, editors, plots, and 3D viewer
│   ├── resources/           # packaged LAMMPS smoke-test inputs
│   ├── analysis.py          # numeric and LAMMPS-output parsing
│   ├── chemistry.py         # validation, conformers, packing, parameterization
│   ├── lammps.py            # LAMMPS command generation
│   ├── models.py            # serializable project model
│   ├── protocol.py          # graph validation and path generation
│   ├── run_generation.py    # run artifacts and manifests
│   └── system_import.py     # LAMMPS data and trajectory import
├── markdown_resources/
├── tests/
├── pyproject.toml
└── run_gui.py
```

After installing the project in editable mode, run:

```bash
python -m unittest discover -s tests -v
```

Tests needing unavailable graphical or chemistry components may be skipped.

## Contributing

Report bugs and focused proposals through the [issue tracker](https://github.com/eli-ams/scymol/issues). Include the operating system, Python and Scymol versions, reproduction steps, and relevant terminal or LAMMPS output. Contributions should preserve inspectable project files and generated inputs.

## Citation

If Scymol supports your research, please cite:

> Assaf, E. I., Maalouf, E., Liu, X., Lin, P., & Erkens, S. (2025). Scymol: A python-based software package for initializing and running molecular dynamics simulations using LAMMPS. *SoftwareX, 29*, 102044. [https://doi.org/10.1016/j.softx.2025.102044](https://doi.org/10.1016/j.softx.2025.102044)

```bibtex
@article{Assaf2025Scymol,
  author  = {Assaf, Eli I. and Maalouf, Elsa and Liu, Xueyan and Lin, Peng and Erkens, Sandra},
  title   = {Scymol: A python-based software package for initializing and running molecular dynamics simulations using LAMMPS},
  journal = {SoftwareX},
  volume  = {29},
  pages   = {102044},
  year    = {2025},
  doi     = {10.1016/j.softx.2025.102044}
}
```

## License and acknowledgements

Scymol is distributed under the [GNU General Public License v3.0](LICENSE). It was created by Eli I. Assaf, Elsa Maalouf, Xueyan Liu, Peng Lin, and Sandra Erkens and continues the original project's aim of making reproducible molecular-simulation workflows accessible without concealing their LAMMPS inputs.
