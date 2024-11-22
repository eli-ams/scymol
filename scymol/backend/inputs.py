# Input parameters:
run_mode = 'mixture+pysimm+lammps'
number_of_mixtures_needed = 1
initial_low_density_factor = 0.01
flt_final_density_in_kgm3 = 1000.0
int_multiply_nbr_of_mols_by_factor = 1
distribution_method = 'Sobol'
molecules_flag = 'cco'
layer_offset = 25.0
file_output_name = 'cco'
number_of_trials = 500
potential_energy_limit = 0.0
run_command = 'mpiexec -n 12 lmp -in stage_1.in'
use_forcefield = 'Gaff2'
charges = 'gasteiger'

# Molecules Dictionary:
molecules_dictionary = {
    "naphthalene1": {
        "nbr_of_mols": 50,
        "smiles": "[H]c1c([H])c([H])c2c([H])c([H])c([H])c([H])c2c1[H]",
        "rotate": True
    }
}

# Constants and Unit Conversions:
AVOGADRO_NUMBER = 6.022e+23

# Lammps simulation inputs:
lammps_stages_and_methods = [
    {
        "stage": "stage_1",
        "methods": [
            {
                "name": "add_simulation_title",
                "params": {
                    "title": "",
                    "number": 1,
                    "description": "Created using Scymol 2023."
                }
            },
            {
                "name": "add_echo",
                "params": {
                    "echo_style": "both"
                }
            },
            {
                "name": "standard_initialization_substage",
                "params": {
                    "boundary_style": [
                        "p",
                        "p",
                        "p"
                    ]
                }
            },
            {
                "name": "standard_minimization_substage",
                "params": {}
            },
            {
                "name": "standard_velocities_stage",
                "params": {
                    "temp": 298.15,
                    "random_seed": 1234
                }
            },
            {
                "name": "standard_nvt_stage",
                "params": {
                    "timestep": 1.0,
                    "set_timestep": 0,
                    "nrun": 5000,
                    "temp_initial": 298.15,
                    "temp_final": 298.15,
                    "temp_ncontrol": 100,
                    "nreset": 1000,
                    "drag": 1,
                    "nevery": 1,
                    "nrepeat": 999,
                    "nfreq": 1000,
                    "ndump": 1000
                }
            },
            {
                "name": "standard_uniaxial_deformation_stage",
                "params": {
                    "timestep": 1.0,
                    "set_timestep": 0,
                    "nrun": 100000,
                    "comp_axis": "z",
                    "ndeformation": 1000,
                    "strain_style": "True strain",
                    "temp_initial": 298.15,
                    "temp_final": 298.15,
                    "temp_ncontrol": 100,
                    "nreset": 1000,
                    "drag": 1,
                    "nevery": 1,
                    "nrepeat": 999,
                    "nfreq": 1000,
                    "ndump": 1000
                }
            },
            {
                "name": "standard_npt_stage",
                "params": {
                    "timestep": 1.0,
                    "set_timestep": 0,
                    "nrun": 5000,
                    "temp_initial": 298.15,
                    "temp_final": 298.15,
                    "temp_ncontrol": 100,
                    "nreset": 1000,
                    "drag": 1,
                    "pres_initial": 1.0,
                    "pres_final": 1.0,
                    "press_ncontrol": 100,
                    "nevery": 1,
                    "nrepeat": 999,
                    "nfreq": 1000,
                    "ndump": 1000,
                    "set_cubic": False,
                    "boxdims_changeto": "Last trajectory"
                }
            },
            {
                "name": "standard_nvt_stage",
                "params": {
                    "timestep": 1.0,
                    "set_timestep": 0,
                    "nrun": 5000,
                    "temp_initial": 298.15,
                    "temp_final": 298.15,
                    "temp_ncontrol": 100,
                    "nreset": 1000,
                    "drag": 1,
                    "nevery": 1,
                    "nrepeat": 999,
                    "nfreq": 1000,
                    "ndump": 1000
                }
            },
            {
                "name": "standard_nve_stage",
                "params": {
                    "timestep": 1.0,
                    "set_timestep": 0,
                    "nrun": 5000,
                    "nevery": 1,
                    "nrepeat": 999,
                    "nfreq": 1000,
                    "ndump": 1000
                }
            },
            {
                "name": "standard_minimization_substage",
                "params": {}
            }
        ]
    }
]
