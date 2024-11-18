import textwrap
import inputs
import scymol.backend.lammps_functions as lf
from typing import List, Tuple

dict_of_variables = {
    "R": "0.00198722",
    "sysvol": "vol",
    "sysmass": "mass(all)/6.0221367e+023",
    "sysdensity": "v_sysmass/v_sysvol/1.0e-24",
    "coulomb": "ecoul+elong",
    "etotal": "etotal",
    "pe": "pe",
    "ke": "ke",
    "evdwl": "evdwl",
    "epair": "epair",
    "ebond": "ebond",
    "eangle": "eangle",
    "edihed": "edihed",
    "eimp": "eimp",
    "lx": "lx",
    "ly": "ly",
    "lz": "lz",
    "xhi": "xhi",
    "yhi": "yhi",
    "zhi": "zhi",
    "xlo": "xlo",
    "ylo": "ylo",
    "zlo": "zlo",
    "Nthermo": "0",
    "cella": "lx",
    "cellb": "sqrt(ly*ly+xy*xy)",
    "cellc": "sqrt(lz*lz+xz*xz+yz*yz)",
    "cellalpha": "acos((xy*xz+ly*yz)/(v_cellb*v_cellc))",
    "cellbeta": "acos(xz/v_cellc)",
    "cellgamma": "acos(xy/v_cellb)",
    "p": "press",
    "pxx": "pxx",
    "pyy": "pyy",
    "pzz": "pzz",
    "pyz": "pyz",
    "pxz": "pxz",
    "pxy": "pxy",
    "sxx": "-pxx",
    "syy": "-pyy",
    "szz": "-pzz",
    "syz": "-pyz",
    "sxz": "-pxz",
    "sxy": "-pxy",
    "fmax": "fmax",
    "fnorm": "fnorm",
    "time": "step*dt+0.000001",
}
list_thermo_style_mda = [
    "step",
    "v_time",
    "press",
    "vol",
    "v_sysdensity",
    "temp",
    "ebond",
    "eangle",
    "edihed",
    "eimp",
    "evdwl",
    "ecoul",
    "etail",
    "elong",
    "pe",
    "ke",
]
std_list_dump_properties = ["id", "mol", "type", "q", "xs", "ys", "zs"]
std_list_avetime_properties_mda = [
    "v_time",
    "c_thermo_temp",
    "c_thermo_press",
    "v_sysvol",
    "v_sysdensity",
    "v_cella",
    "v_cellb",
    "v_cellc",
    "v_etotal",
    "v_pe",
    "v_ke",
    "v_evdwl",
    "v_coulomb",
    "v_sxx",
    "v_syy",
    "v_szz",
    "v_syz",
    "v_sxz",
    "v_sxy",
    "v_xhi",
    "v_yhi",
    "v_zhi",
    "v_xlo",
    "v_ylo",
    "v_zlo",
]

lammps_simulation_stages = inputs.lammps_stages_and_methods


class LammpsCommands:
    def __init__(self):
        self.script = []
        self.dict_of_variables = dict_of_variables
        self.list_thermo_style_mda = list_thermo_style_mda
        self.std_list_dump_properties = std_list_dump_properties
        self.std_list_avetime_properties_mda = std_list_avetime_properties_mda

    def add_simulation_title(self, number: int, title: str, description: str) -> None:
        """
        Add a simulation title to the LAMMPS script.

        Args:
            number (int): Stage number of the simulation.
            title (str): Title of the simulation stage.
            description (str): Description of the stage.

        This function constructs a comment block for a LAMMPS simulation stage and
        appends it to the script.
        """
        # Wrap the description to fit within 76 characters per line
        wrapped_description = textwrap.wrap(description, width=76)

        # Prefix each line with '# ' to create a comment block
        wrapped_description = ["# " + line for line in wrapped_description]

        # Construct the text to be added to the script
        text_to_return = f"#-------------------------------------------------------------------------------\n"
        text_to_return += f"# LAMMPS Stage {number}: {title}\n"
        for line in wrapped_description:
            text_to_return += line + "\n"
        text_to_return += f"#-------------------------------------------------------------------------------"

        # Append the constructed text to the script list
        self.script.append(text_to_return)

    def add_substage_title(
        self, numbering: Tuple[int, int], title: str, description: str
    ) -> None:
        """
        Add a substage title to the LAMMPS script.

        Args:
            numbering (Tuple[int, int]): Substage numbering as a tuple (e.g., (1, 2)).
            title (str): Title of the substage.
            description (str): Description of the substage.

        This function constructs a comment block for a substage in a LAMMPS simulation
        and appends it to the script.
        """
        # Wrap the description to fit within 76 characters per line
        wrapped_description = textwrap.wrap(description, width=76)

        # Prefix each line with '# ' to create a comment block
        wrapped_description = ["# " + line for line in wrapped_description]

        # Construct the text to be added to the script
        text_to_return = f"#-------------------------------------------------------------------------------\n"
        text_to_return += f"# Substage {numbering[0]}.{numbering[1]}: {title}\n"
        for line in wrapped_description:
            text_to_return += line + "\n"
        text_to_return += f"#-------------------------------------------------------------------------------"

        # Append the constructed text to the script list
        self.script.append(text_to_return)

    def add_comment(
        self,
        comment: str,
        prepend_new_line: bool = False,
        append_new_line: bool = False,
    ) -> None:
        """
        Add a comment to the LAMMPS script.

        Args:
            comment (str): The comment text to be added.
            prepend_new_line (bool, optional): Whether to prepend a newline before the comment.
                Default is False.
            append_new_line (bool, optional): Whether to append a newline after the comment.
                Default is False.

        This function constructs a comment block and appends it to the script.
        """
        prepend_nl = "\n" if prepend_new_line else ""
        append_nl = "\n" if append_new_line else ""
        text_to_return = f"{prepend_nl}#-------------------------------------------------------------------------------\n"
        text_to_return += f"# {comment}\n"
        text_to_return += f"#-------------------------------------------------------------------------------{append_nl}"
        self.script.append(text_to_return)

    def add_logfile(self, numbering: Tuple[int, int], substage_type: str) -> None:
        """
        Add a logfile line to the LAMMPS script.

        Args:
            numbering (Tuple[int, int]): Substage numbering as a tuple (e.g., (1, 2)).
            substage_type (str): The type of substage.

        This function appends a logfile line to the LAMMPS script using the provided
        substage numbering and type.
        """
        self.script.append(
            lf.format_line(f"log  {numbering[0]}.{numbering[1]}-{substage_type}.out\n")
        )

    def add_custom_code(self, lst_custom_code_lines: List[str]) -> None:
        """
        Add custom code lines to the LAMMPS script.

        Args:
            lst_custom_code_lines (List[str]): List of custom code lines to be added.

        This function appends custom code lines to the LAMMPS script.
        """
        for custom_line in lst_custom_code_lines:
            self.script.append(lf.format_line(custom_line))

    # def add_read_previous_dump_file(self, absolute_path_with_file: str):
    #     self.script.append(lf.format_line(f"read_dump  {absolute_path_with_file} x y z box yes\n"))

    def add_set_timestep(self, set_timestep_to: float) -> None:
        """
        Set the timestep in the LAMMPS script.

        Args:
            set_timestep_to (float): The timestep value to set.

        This function appends a line to set the timestep in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"reset_timestep  {set_timestep_to}"))

    def add_thermo_style(self, style_option: str, lst_properties: List[str]) -> None:
        """
        Set the thermo style in the LAMMPS script.

        Args:
            style_option (str): The style option for thermo_style.
            lst_properties (List[str]): List of properties to include in thermo_style.

        This function appends a line to set the thermo_style in the LAMMPS script.
        """
        self.script.append(
            lf.format_line(f"thermo_style {style_option} {' '.join(lst_properties)}")
        )

    def add_set_nthermo(self, nthermo: int) -> None:
        """
        Set the number of steps between thermodynamic output in the LAMMPS script.

        Args:
            nthermo (int): The number of steps between thermodynamic output.

        This function appends a line to set the 'nthermo' value in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"nthermo  {nthermo}"))

    def add_fix_npt(
        self,
        fix_id: str,
        fix_subset: str,
        temp_initial: float,
        temp_final: float,
        temp_ncontrol: int,
        pres_initial: float,
        pres_final: float,
        pres_ncontrol: int,
        drag: float,
        nreset: int,
        lst_of_additional_commands: List[str],
    ) -> None:
        """
        Add a fix npt command to the LAMMPS script for temperature and pressure control.

        Args:
            fix_id (str): Unique identifier for the fix command.
            fix_subset (str): Subset of atoms or groups to apply the fix to.
            temp_initial (float): Initial temperature for the NPT ensemble.
            temp_final (float): Target temperature for the NPT ensemble.
            temp_ncontrol (int): Number of control steps for temperature.
            pres_initial (float): Initial pressure for the NPT ensemble.
            pres_final (float): Target pressure for the NPT ensemble.
            pres_ncontrol (int): Number of control steps for pressure.
            drag (float): Drag coefficient for temperature control.
            nreset (int): Frequency at which velocities are reset.
            lst_of_additional_commands (List[str]): List of additional commands to include.

        This function appends a fix npt command to the LAMMPS script for temperature and pressure control.
        """
        self.script.append(
            lf.format_line(
                f"fix  {fix_id} {fix_subset} npt temp {temp_initial} {temp_final} {temp_ncontrol} "
                f"iso {pres_initial} {pres_final} {pres_ncontrol} drag {drag} nreset {nreset} "
                f"{''.join(lst_of_additional_commands)}"
            )
        )

    def add_fix_nvt(
        self,
        fix_id: str,
        fix_subset: str,
        temp_initial: float,
        temp_final: float,
        temp_ncontrol: int,
        drag: float,
        nreset: int,
        lst_of_additional_commands: List[str],
    ) -> None:
        """
        Add a fix nvt command to the LAMMPS script for temperature control.

        Args:
            fix_id (str): Unique identifier for the fix command.
            fix_subset (str): Subset of atoms or groups to apply the fix to.
            temp_initial (float): Initial temperature for the NVT ensemble.
            temp_final (float): Target temperature for the NVT ensemble.
            temp_ncontrol (int): Number of control steps for temperature.
            drag (float): Drag coefficient for temperature control.
            nreset (int): Frequency at which velocities are reset.
            lst_of_additional_commands (List[str]): List of additional commands to include.

        This function appends a fix nvt command to the LAMMPS script for temperature control.
        """
        self.script.append(
            lf.format_line(
                f"fix  {fix_id} {fix_subset} nvt temp {temp_initial} {temp_final} {temp_ncontrol} "
                f"drag {drag} nreset {nreset} {''.join(lst_of_additional_commands)}"
            )
        )

    def add_fix_nve(
        self,
        fix_id: str,
        fix_subset: str,
        nreset: int,
        lst_of_additional_commands: List[str],
    ) -> None:
        """
        Add a fix nve command to the LAMMPS script for constant energy (NVE) simulation.

        Args:
            fix_id (str): Unique identifier for the fix command.
            fix_subset (str): Subset of atoms or groups to apply the fix to.
            nreset (int): Frequency at which velocities are reset.
            lst_of_additional_commands (List[str]): List of additional commands to include.

        This function appends a fix nve command to the LAMMPS script for constant energy (NVE) simulation.
        """
        self.script.append(
            lf.format_line(
                f"fix  {fix_id} {fix_subset} nve nreset {nreset} {''.join(lst_of_additional_commands)}"
            )
        )

    def add_fix_minimize(
        self,
        tol_energy: float,
        tol_force: float,
        max_iterations: int,
        max_evaluations: int,
    ) -> None:
        """
        Add a minimize command to the LAMMPS script for energy and force minimization.

        Args:
            tol_energy (float): Tolerance for energy convergence.
            tol_force (float): Tolerance for force convergence.
            max_iterations (int): Maximum number of iterations.
            max_evaluations (int): Maximum number of force/energy evaluations.

        This function appends a minimize command to the LAMMPS script for energy and force minimization.
        """
        self.script.append(
            lf.format_line(
                f"minimize  {tol_energy} {tol_force} {max_iterations} {max_evaluations}"
            )
        )

    def add_restart_file(self, nsteps: int, absolute_path_with_file: str) -> None:
        """
        Add a restart command to the LAMMPS script to read a restart file.

        Args:
            nsteps (int): Number of timesteps between writing restart files.
            absolute_path_with_file (str): Absolute path to the restart file.

        This function appends a restart command to the LAMMPS script to read a restart file.
        """
        self.script.append(
            lf.format_line(f"restart  {nsteps} {absolute_path_with_file}")
        )

    def add_dump(
        self,
        dump_id: str,
        dump_subset: str,
        style_option: str,
        ndump: int,
        absolute_path_with_file: str,
        properties: List[str],
    ) -> None:
        """
        Add a dump command to the LAMMPS script for outputting simulation data.

        Args:
            dump_id (str): Unique identifier for the dump command.
            dump_subset (str): Subset of atoms or groups to apply the dump to.
            style_option (str): Style option for the dump command.
            ndump (int): Frequency at which data is dumped.
            absolute_path_with_file (str): Absolute path and filename for the dump file.
            properties (List[str]): List of properties to include in the dump.

        This function appends a dump command to the LAMMPS script for outputting simulation data.
        """
        self.script.append(
            lf.format_line(
                f"dump  {dump_id} {dump_subset} {style_option} {ndump} {absolute_path_with_file} "
                f"{' '.join(properties)}"
            )
        )

    def add_timestep(self, timestep: float) -> None:
        """
        Set the timestep in the LAMMPS script.

        Args:
            timestep (float): The timestep value to set.

        This function appends a line to set the timestep in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"timestep  {timestep}"))

    def add_run_command(self, nsteps: int) -> None:
        """
        Add a run command to the LAMMPS script to perform simulation steps.

        Args:
            nsteps (int): The number of simulation steps to run.

        This function appends a run command to the LAMMPS script to perform simulation steps.
        """
        self.script.append(lf.format_line(f"run  {nsteps}"))

    def add_undump(self, dump_id: str) -> None:
        """
        Remove a dump command from the LAMMPS script.

        Args:
            dump_id (str): The unique identifier of the dump command to remove.

        This function appends an undump command to the LAMMPS script to remove a previously defined dump.
        """
        self.script.append(lf.format_line(f"undump  {dump_id}"))

    def add_unfix(self, fix_id: str) -> None:
        """
        Remove a fix command from the LAMMPS script.

        Args:
            fix_id (str): The unique identifier of the fix command to remove.

        This function appends an unfix command to the LAMMPS script to remove a previously defined fix.
        """
        self.script.append(lf.format_line(f"unfix  {fix_id}"))

    def add_velocities(
        self,
        velocities_subset: str,
        temp: float,
        random_seed: int,
        dist_type: str,
        momentum: str,
        rotation: str,
    ) -> None:
        """
        Add a command to set atom velocities in the LAMMPS script.

        Args:
            velocities_subset (str): Subset of atoms or groups to set velocities for.
            temp (float): Temperature for velocity initialization.
            random_seed (int): Random seed for velocity initialization.
            dist_type (str): Type of distribution for initial velocities.
            momentum (str): Momentum value for the initial velocities.
            rotation (str): Rotation value for the initial velocities.

        This function appends a velocity command to the LAMMPS script to set atom velocities.
        """
        self.script.append(
            lf.format_line(
                f"velocity  {velocities_subset} create {temp} {random_seed} dist {dist_type} "
                f"mom {momentum} rot {rotation}"
            )
        )

    def add_min_style(self, style: str) -> None:
        """
        Set the minimization style in the LAMMPS script.

        Args:
            style (str): The style of minimization to be used.

        This function appends a line to set the minimization style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"min_style  {style}"))

    def add_min_modify(self, dmax: float) -> None:
        """
        Modify the settings for minimization in the LAMMPS script.

        Args:
            dmax (float): The maximum allowed displacement during minimization.

        This function appends a line to modify minimization settings in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"min_modify  dmax {dmax}"))

    def add_variable(
        self, var_name: str, var_expression, var_style: str = "equal"
    ) -> None:
        """
        Add a variable definition to the LAMMPS script.

        Args:
            var_name (str): The name of the variable.
            var_expression: The expression defining the variable.
            var_style (str, optional): The style of the variable definition (default is "equal").

        This function appends a variable definition to the LAMMPS script and stores it in a dictionary.
        """
        self.script.append(
            lf.format_line(f"variable {var_name} {var_style} {var_expression}")
        )
        self.dict_of_variables[var_name] = var_expression

    def add_echo(self, echo_style: str) -> None:
        """
        Set the echo style in the LAMMPS script.

        Args:
            echo_style (str): The style of echo to be used.

        This function appends a line to set the echo style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"echo  {echo_style}"))

    def add_units(self, units_style: str) -> None:
        """
        Set the units style in the LAMMPS script.

        Args:
            units_style (str): The style of units to be used.

        Raises:
            Exception: If the provided units_style is not a valid LAMMPS unit style.

        This function appends a line to set the units style in the LAMMPS script.
        """
        valid_unit_styles = [
            "lj",
            "real",
            "metal",
            "si",
            "cgs",
            "electron",
            "micro",
            "nano",
        ]

        if units_style not in valid_unit_styles:
            raise Exception(f"'{units_style}' is not a valid LAMMPS unit style.")

        self.script.append(lf.format_line(f"units  {units_style}"))

    from typing import Tuple

    def add_boundary(self, boundary_style: Tuple[str, str, str]) -> None:
        """
        Set the boundary conditions in the LAMMPS script.

        Args:
            boundary_style (Tuple[str, str, str]): The boundary conditions as a tuple (x, y, z).

        This function appends a line to set the boundary conditions in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"boundary  {' '.join(boundary_style)}"))

    def add_pair_style(self, pair_style: str) -> None:
        """
        Set the pair style in the LAMMPS script.

        Args:
            pair_style (str): The style of pair interaction to be used.

        This function appends a line to set the pair style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"pair_style  {pair_style}"))

    def add_kspace_style(self, kspace_style: str) -> None:
        """
        Set the kspace style in the LAMMPS script.

        Args:
            kspace_style (str): The style of kspace interaction to be used.

        This function appends a line to set the kspace style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"kspace_style  {kspace_style}"))

    def add_pair_modify(self, pair_modify: str) -> None:
        """
        Modify the pair interaction settings in the LAMMPS script.

        Args:
            pair_modify (str): The modification settings for the pair interaction.

        This function appends a line to modify the pair interaction settings in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"pair_modify  {pair_modify}"))

    def add_bond_style(self, bond_style: str) -> None:
        """
        Set the bond style in the LAMMPS script.

        Args:
            bond_style (str): The style of bond interaction to be used.

        This function appends a line to set the bond style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"bond_style  {bond_style}"))

    def add_angle_style(self, angle_style: str) -> None:
        """
        Set the angle style in the LAMMPS script.

        Args:
            angle_style (str): The style of angle interaction to be used.

        This function appends a line to set the angle style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"angle_style  {angle_style}"))

    def add_dihedral_style(self, dihedral_style: str) -> None:
        """
        Set the dihedral style in the LAMMPS script.

        Args:
            dihedral_style (str): The style of dihedral interaction to be used.

        This function appends a line to set the dihedral style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"dihedral_style  {dihedral_style}"))

    def add_improper_style(self, improper_style: str) -> None:
        """
        Set the improper style in the LAMMPS script.

        Args:
            improper_style (str): The style of improper interaction to be used.

        This function appends a line to set the improper style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"improper_style  {improper_style}"))

    def add_special_bonds(self, special_bonds: str) -> None:
        """
        Set the special bonds in the LAMMPS script.

        Args:
            special_bonds (str): The special bonds settings to be used.

        This function appends a line to set the special bonds in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"special_bonds  {special_bonds}"))

    def add_box(self, box: str) -> None:
        """
        Add a box definition to the LAMMPS script.

        Args:
            box (str): The box definition string.

        This function appends a box definition to the LAMMPS script.
        """
        self.script.append(lf.format_line(f"add_box  {box}"))

    def add_read_data(self, absolute_path_with_file: str) -> None:
        """
        Read data from a file and add it to the LAMMPS simulation.

        Args:
            absolute_path_with_file (str): The absolute path to the data file.

        This function appends a read_data command to the LAMMPS script to read data from a file.
        """
        self.script.append(lf.format_line(f"read_data  {absolute_path_with_file}"))

    def add_include(self, absolute_path_with_file: str) -> None:
        """
        Include a file in the LAMMPS script.

        Args:
            absolute_path_with_file (str): The absolute path to the file to be included.

        This function appends an include command to the LAMMPS script to include a file.
        """
        self.script.append(lf.format_line(f"include  {absolute_path_with_file}"))

    def add_neighbor(self, neighbor_style: str) -> None:
        """
        Set the neighbor settings in the LAMMPS script.

        Args:
            neighbor_style (str): The style of neighbor list to be used.

        This function appends a line to set the neighbor settings in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"neighbor  {neighbor_style}"))

    def add_neigh_modify(self, delay: int, nevery: int, check: bool) -> None:
        """
        Modify the neighbor settings in the LAMMPS script.

        Args:
            delay (int): The delay for neighbor list construction.
            nevery (int): The frequency of neighbor list rebuilding.
            check (bool): Whether to check consistency of neighbor list (True for yes, False for no).

        This function appends a line to modify the neighbor settings in the LAMMPS script.
        """
        check_value = "yes" if check else "no"
        self.script.append(
            lf.format_line(
                f"neighbor  delay {delay} every {nevery} check {check_value}"
            )
        )

    def add_thermo_modify(self, flush: bool) -> None:
        """
        Modify the thermo settings in the LAMMPS script.

        Args:
            flush (bool): Whether to flush output during thermo output (True for yes, False for no).

        This function appends a line to modify the thermo settings in the LAMMPS script.
        """
        flush_value = "yes" if flush else "no"
        self.script.append(lf.format_line(f"thermo_modify  flush {flush_value}"))

    def add_thermo(self, nthermo: int) -> None:
        """
        Set the thermo output frequency in the LAMMPS script.

        Args:
            nthermo (int): The frequency of thermo output.

        This function appends a line to set the thermo output frequency in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"thermo  {nthermo}"))

    def add_fix_ave_time(
        self,
        fix_id: str,
        fix_subset: str,
        nevery: int,
        nrepeat: int,
        nfreq: int,
        list_of_properties: list,
        absolute_path_with_file: str,
    ) -> None:
        """
        Add an ave/time fix command to the LAMMPS script.

        Args:
            fix_id (str): The unique identifier for the fix.
            fix_subset (str): Subset of atoms or groups to apply the fix to.
            nevery (int): The frequency of the fix.
            nrepeat (int): Number of times the fix is applied.
            nfreq (int): Number of times to accumulate data.
            list_of_properties (list): List of properties to be calculated and output.
            absolute_path_with_file (str): Absolute path to the output file (can be empty).

        This function appends an ave/time fix command to the LAMMPS script.
        """
        if absolute_path_with_file == "":
            self.script.append(
                lf.format_line(
                    f"fix {fix_id} {fix_subset} ave/time {nevery} {nrepeat} {nfreq} "
                    f"{' '.join(list_of_properties)}"
                )
            )
        else:
            self.script.append(
                lf.format_line(
                    f"fix {fix_id} {fix_subset} ave/time {nevery} {nrepeat} {nfreq} "
                    f"{' '.join(list_of_properties)} file {absolute_path_with_file}"
                )
            )

    def add_atom_style(self, atom_style: str) -> None:
        """
        Set the atom style in the LAMMPS script.

        Args:
            atom_style (str): The style of atom representation to be used.

        This function appends a line to set the atom style in the LAMMPS script.
        """
        self.script.append(lf.format_line(f"atom_style  {atom_style}"))

    from typing import List

    def add_change_box(self, lst_of_new_box_dims: List[str]) -> None:
        """
        Change the dimensions of the simulation box in the LAMMPS script.

        Args:
            lst_of_new_box_dims (List[float]): List of new box dimensions [xlo, xhi, ylo, yhi, zlo, zhi].

        This function appends commands to change the box dimensions in the LAMMPS script.
        """
        lst_of_new_box_dims = [str(i) for i in lst_of_new_box_dims]
        self.add_comment(
            comment=f'Set dimensions of the box to {" ".join(lst_of_new_box_dims)}.',
            prepend_new_line=True,
        )
        self.script.append(
            lf.format_line(
                f"change_box all x final {lst_of_new_box_dims[0]} {lst_of_new_box_dims[1]} "
                f"y final {lst_of_new_box_dims[2]} {lst_of_new_box_dims[3]} "
                f"z final {lst_of_new_box_dims[4]} {lst_of_new_box_dims[5]} "
                f" remap units box"
            )
        )
        self.script.append("\n")

    def add_read_dump(
        self,
        absolute_path_with_file: str = "temp.lammpstrj",
        which_trajectory: int = 1,
        box_option: str = "yes",
    ) -> None:
        """
        Read a dump file and update particle positions in the LAMMPS script.

        Args:
            absolute_path_with_file (str, optional): Absolute path to the dump file. Default is "temp.lammpstrj".
            which_trajectory (int, optional): Which trajectory to read. Default is 1.
            box_option (str, optional): Whether to read the box information. Default is "yes".

        This function appends commands to read a dump file and update particle positions in the LAMMPS script.
        """
        self.add_comment(
            comment=f"Read previous dump file {absolute_path_with_file} and update particle positions.",
            prepend_new_line=True,
        )
        self.script.append(
            lf.format_line(
                f"read_dump {absolute_path_with_file} {which_trajectory} "
                f"x y z box {box_option}"
            )
        )
        self.script.append("\n")

    def add_custom_change_box(
        self, fix_id, boxdims_changeto_style="Last trajectory", setcubic=False
    ) -> None:
        """
        Custom change of simulation box dimensions in the LAMMPS script.

        Args:
            fix_id (str): The identifier of the fix used for box dimension calculations.
            boxdims_changeto_style (str, optional): The style of changing box dimensions. Default is "Last trajectory".
            setcubic (bool, optional): Whether to set the box to a cubic shape. Default is False.

        This function appends commands to customize the change of simulation box dimensions in the LAMMPS script.
        """
        if boxdims_changeto_style == "Last trajectory" and not setcubic:
            return
        elif boxdims_changeto_style == "Last trajectory" and setcubic:
            self.add_variable(
                var_name="lcubic",
                var_expression="abs(((xhi-xlo)*(yhi-ylo)*(zhi-zlo))^(1/3))",
            )
            self.add_change_box(
                lst_of_new_box_dims=[
                    "0",
                    "${lcubic}",
                    "0",
                    "${lcubic}",
                    "0",
                    "${lcubic}",
                ]
            )
        elif boxdims_changeto_style == "Computed ρ(average)" and setcubic:
            self.add_variable(var_name="xloave", var_expression=f"f_{fix_id}[1]")
            self.add_variable(var_name="xhiave", var_expression=f"f_{fix_id}[2]")
            self.add_variable(var_name="yloave", var_expression=f"f_{fix_id}[3]")
            self.add_variable(var_name="yhiave", var_expression=f"f_{fix_id}[4]")
            self.add_variable(var_name="zloave", var_expression=f"f_{fix_id}[5]")
            self.add_variable(var_name="zhiave", var_expression=f"f_{fix_id}[6]")
            self.add_variable(
                var_name="lcubic",
                var_expression="abs(((v_xhiave-v_xloave)*(v_yhiave-v_yloave)*(v_zhiave-v_zloave))^(1/3))",
            )

            self.add_change_box(
                lst_of_new_box_dims=[
                    "${xloave}",
                    "${xhiave}",
                    "${yloave}",
                    "${yhiave}",
                    "${zloave}",
                    "${zhiave}",
                ]
            )
            self.add_change_box(
                lst_of_new_box_dims=[
                    "0",
                    "${lcubic}",
                    "0",
                    "${lcubic}",
                    "0",
                    "${lcubic}",
                ]
            )

        elif boxdims_changeto_style == "Computed ρ(average)" and not setcubic:
            self.add_variable(var_name="xloave", var_expression=f"f_{fix_id}[1]")
            self.add_variable(var_name="xhiave", var_expression=f"f_{fix_id}[2]")
            self.add_variable(var_name="yloave", var_expression=f"f_{fix_id}[3]")
            self.add_variable(var_name="yhiave", var_expression=f"f_{fix_id}[4]")
            self.add_variable(var_name="zloave", var_expression=f"f_{fix_id}[5]")
            self.add_variable(var_name="zhiave", var_expression=f"f_{fix_id}[6]")
            self.add_variable(
                var_name="lcubic",
                var_expression="abs(((v_xhiave-v_xloave)*(v_yhiave-v_yloave)*(v_zhiave-v_zloave))^(1/3))",
            )

            self.add_change_box(
                lst_of_new_box_dims=[
                    "${xloave}",
                    "${xhiave}",
                    "${yloave}",
                    "${yhiave}",
                    "${zloave}",
                    "${zhiave}",
                ]
            )
