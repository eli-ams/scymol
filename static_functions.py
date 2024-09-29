import csv
import json
import pickle
from typing import List, Dict, Any, Optional, Tuple
from typing import Literal
from PyQt5.QtWidgets import QMessageBox
from file_read_backwards import FileReadBackwards
from rdkit import Chem
from logging_functions import print_to_log, log_function_call


@log_function_call
def translate_simulation_inputs_to_lammps_stages(
    run_mode: str, simulation_inputs: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Translates simulation inputs into a list of LAMMPS stages.

    :param run_mode: The run mode for LAMMPS simulation.
    :type run_mode: str
    :param simulation_inputs: A dictionary containing simulation inputs.
    :type simulation_inputs: Dict[str, Any]

    :return: A list of LAMMPS stages, each represented as a dictionary.
    :rtype: List[Dict[str, Any]]
    """
    lammps_stages = []
    stage_counter = 1
    for stage_name, stage_data in simulation_inputs.items():
        # Ignore keys that are not LAMMPS stages
        if stage_name.startswith("LAMMPS Stage"):
            # Initialize a new stage
            new_stage = {
                "stage": f"stage_{stage_counter}",
                "methods": [
                    {
                        "name": "add_simulation_title",
                        "params": {
                            "title": "",
                            "number": stage_counter,
                            "description": "Created using Scymol 2023.",
                        },
                    },
                    {"name": "add_echo", "params": {"echo_style": "both"}},
                ],
            }

            # Translate individual methods and their params
            for method_name, method_params in stage_data.get(
                "lammpsWindows", {}
            ).items():
                new_method = create_new_lammps_method(method_name, method_params)
                new_stage["methods"].append(new_method)

                # Read last stage's trajectories into the new stage:
                if "initialize" in method_name.lower() and (
                    stage_counter >= 2 or run_mode == "from_previous_lammps"
                ):
                    new_method = {
                        "name": "add_read_dump",
                        "params": {
                            "absolute_path_with_file": "last.lammpstrj",
                            "which_trajectory": 0,
                        },
                    }
                    new_stage["methods"].append(new_method)

            # Append the new stage to the list of translated stages
            lammps_stages.append(new_stage)

            # Increment the stage counter
            stage_counter += 1

    return lammps_stages


def create_new_lammps_method(
    method_name: str, method_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a new LAMMPS method based on the given method name and parameters.

    :param method_name: The name of the LAMMPS method.
    :type method_name: str
    :param method_params: A dictionary containing parameters for the LAMMPS method.
    :type method_params: dict

    :return: A dictionary representing the new LAMMPS method.
    :rtype: dict
    """

    if "initialize" in method_name.lower():
        new_method = {
            "name": "standard_initialization_substage",
            "params": {"boundary_style": []},
        }
        for param_key, param_value in method_params.items():
            new_param_key = param_key.lower()
            # Add the param to the method
            # Initialize 1, combobox_xboundaries, Periodic (P)
            if "boundaries" in param_key.lower():
                if "periodic" in param_value.lower():
                    new_method["params"]["boundary_style"].append("p")
                elif "fixed" in param_value.lower():
                    new_method["params"]["boundary_style"].append("f")
                else:
                    new_method["params"]["boundary_style"].append("s")

    elif "minimize" in method_name.lower():
        new_method = {"name": "standard_minimization_substage", "params": {}}

    elif "velocities" in method_name.lower():
        new_method = {"name": "standard_velocities_stage", "params": {}}
        for param_key, param_value in method_params.items():
            # Initialize 1, combobox_xboundaries, Periodic (P)
            if "temperature" in param_key.lower():
                new_method["params"]["temp"] = param_value
            if "randomseed" in param_key.lower():
                new_method["params"]["random_seed"] = param_value

    elif "nve" in method_name.lower():
        new_method = {"name": "standard_nve_stage", "params": {}}
        key_mapping = {
            "timestep": "timestep",
            "timereset": "set_timestep",
            "nrun": "nrun",
            "nevery": "nevery",
            "nrepeat": "nrepeat",
            "nfreq": "nfreq",
            "ndump": "ndump",
        }
        for param_key, param_value in method_params.items():
            # Make the key lowercase to make the search case-insensitive
            lower_param_key = param_key.lower()

            # Search for the lowercased key in the mapping table
            for key_substring, mapped_key in key_mapping.items():
                if key_substring in lower_param_key:
                    new_method["params"][mapped_key] = param_value
                    break  # Stop searching once a match is found

    elif "nvt" in method_name.lower():
        new_method = {"name": "standard_nvt_stage", "params": {}}
        key_mapping = {
            "timestep": "timestep",
            "timereset": "set_timestep",
            "nrun": "nrun",
            "initialtemperature": "temp_initial",
            "finaltemperature": "temp_final",
            "controltevery": "temp_ncontrol",
            "temperaturenreset": "nreset",
            "temperaturecontroldrag": "drag",
            "nevery": "nevery",
            "nrepeat": "nrepeat",
            "nfreq": "nfreq",
            "ndump": "ndump",
        }
        for param_key, param_value in method_params.items():
            # Make the key lowercase to make the search case-insensitive
            lower_param_key = param_key.lower()

            # Search for the lowercased key in the mapping table
            for key_substring, mapped_key in key_mapping.items():
                if key_substring in lower_param_key:
                    new_method["params"][mapped_key] = param_value
                    break  # Stop searching once a match is found

    elif "npt" in method_name.lower():
        new_method = {"name": "standard_npt_stage", "params": {}}
        key_mapping = {
            "timestep": "timestep",
            "timereset": "set_timestep",
            "nrun": "nrun",
            "initialtemperature": "temp_initial",
            "finaltemperature": "temp_final",
            "controltevery": "temp_ncontrol",
            "temperaturenreset": "nreset",
            "temperaturecontroldrag": "drag",
            "initialpressure": "pres_initial",
            "finalpressure": "pres_final",
            "controlpevery": "press_ncontrol",
            "nevery": "nevery",
            "nrepeat": "nrepeat",
            "nfreq": "nfreq",
            "ndump": "ndump",
            "combobox_rhoaverage": "boxdims_changeto",
            "checkbox_setcubic": "set_cubic",
        }
        for param_key, param_value in method_params.items():
            # Make the key lowercase to make the search case-insensitive
            lower_param_key = param_key.lower()

            # Search for the lowercased key in the mapping table
            for key_substring, mapped_key in key_mapping.items():
                if key_substring in lower_param_key:
                    new_method["params"][mapped_key] = param_value
                    break  # Stop searching once a match is found

    elif "deformation" in method_name.lower():
        new_method = {"name": "standard_uniaxial_deformation_stage", "params": {}}
        key_mapping = {
            "timestep": "timestep",
            "timereset": "set_timestep",
            "nrun": "nrun",
            "combobox_axis": "comp_axis",
            "spinbox_ndeformations": "ndeformation",
            "combobox_strainratetype": "strain_style",  # change t to true.
            # "combobox_stopat": "comp_axis",
            "initialtemperature": "temp_initial",
            "finaltemperature": "temp_final",
            "controltevery": "temp_ncontrol",
            "temperaturenreset": "nreset",
            "temperaturecontroldrag": "drag",
            "nevery": "nevery",
            "nrepeat": "nrepeat",
            "nfreq": "nfreq",
            "ndump": "ndump",
        }
        for param_key, param_value in method_params.items():
            # Make the key lowercase to make the search case-insensitive
            lower_param_key = param_key.lower()

            # Search for the lowercased key in the mapping table
            for key_substring, mapped_key in key_mapping.items():
                if key_substring in lower_param_key:
                    new_method["params"][mapped_key] = param_value
                    break  # Stop searching once a match is found
    else:
        raise Exception(f"Method {method_name.lower()} type not found!")

    return new_method


@log_function_call
def generate_mixture_information(
    mixture_table: Dict[str, dict], molecules_objects: Dict[str, Any]
) -> str:
    """
    Calculate and generate information about a molecular mixture.

    :param mixture_table: A dictionary containing information about the mixture composition.
    :type mixture_table: dict
    :param molecules_objects: A dictionary containing molecular objects with their properties.
    :type molecules_objects: dict

    :return: Information about the molecular mixture, including total count and average molecular weight.
    :rtype: str
    """
    total_weight = 0.0  # Sum of molecular weights, considering the number of each type
    total_count = 0  # Total number of molecules in the mixture

    for name, data in mixture_table.items():
        number = data["number"]
        if number == 0:
            continue  # Skip if the molecule count is zero
        molecular_weight = molecules_objects[
            name
        ].mol_weight  # Get molecular weight from the molecule object
        total_weight += molecular_weight * number  # Multiply by number and add to total
        total_count += number  # Add the number to the total count

    if total_count == 0:
        info_text = "No molecules in the mixture."
    else:
        average_weight = total_weight / total_count  # Compute the average weight
        info_text = f"Total Number of Molecules: {total_count}\nMolecular Weight: {average_weight:.2f} Da"

    return info_text


@log_function_call
def generate_mixture_with_smiles(
    mixture_table: Dict[str, dict], molecules_objects: Dict[str, Any]
) -> Dict[str, dict]:
    """
    Generate a new dictionary with SMILES information for molecules in a mixture.

    :param mixture_table: A dictionary containing information about the mixture composition.
    :type mixture_table: dict
    :param molecules_objects: A dictionary containing molecular objects with SMILES data.
    :type molecules_objects: dict

    :return: A new dictionary with SMILES information added for each molecule.
    :rtype: dict
    """
    # Create a new dictionary to store the mixture data
    new_mixture_data = {}

    for name, data in mixture_table.items():
        # Make a deep copy of the existing data for each molecule
        new_data = data.copy()

        # Add the SMILES string to the data for this molecule
        new_data["smiles"] = molecules_objects[name].smiles

        # Add the updated data to the new_mixture_data dictionary
        new_mixture_data[name] = new_data

    return new_mixture_data


@log_function_call
def convert_molecule_dict(original_dict: Dict[str, dict]) -> Dict[str, dict]:
    """
    Convert a dictionary containing molecular information into a simplified format.

    :param original_dict: A dictionary containing detailed molecular information.
    :type original_dict: dict

    :return: A simplified dictionary format with the number of molecules and SMILES strings.
    :rtype: dict
    """
    converted_dict = {}
    for key, value in original_dict.items():
        new_value = {}
        new_value["nbr_of_mols"] = value["number"]
        new_value["smiles"] = value["smiles"]
        new_value["rotate"] = bool(value["rotate"])
        converted_dict[key] = new_value
    return converted_dict


@log_function_call
def write_inputs_to_file(file_path: str, **kwargs: Any) -> None:
    """
    Write input parameters to a file in a structured format.

    :param file_path: The path to the output file.
    :type file_path: str
    :param kwargs: Keyword arguments representing various input parameters.

    :return: None
    :rtype: None
    """
    with open(file_path, "w") as f:
        f.write("# Input parameters:\n")

        for key, value in kwargs.items():
            if key in [
                "constants",
                "lammps_stages_and_methods",
                "molecules_dictionary",
            ]:
                continue

            if isinstance(value, str):
                f.write(f"{key} = '{value}'\n")
            else:
                f.write(f"{key} = {value}\n")

        if "molecules_dictionary" in kwargs:
            f.write("\n# Molecules Dictionary:\n")
            molecules_dictionary_str = json.dumps(
                kwargs["molecules_dictionary"], indent=4
            )
            molecules_dictionary_str = molecules_dictionary_str.replace(
                "true", "True"
            ).replace("false", "False")
            f.write(f"molecules_dictionary = {molecules_dictionary_str}\n")

        if "constants" in kwargs:
            f.write("\n# Constants and Unit Conversions:\n")
            for key, value in kwargs["constants"].items():
                f.write(f"{key.upper()} = {value}\n")

        if "lammps_stages_and_methods" in kwargs:
            f.write("\n# Lammps simulation inputs:\n")
            lammps_stages_and_methods_str = json.dumps(
                kwargs["lammps_stages_and_methods"], indent=4
            )

            # json is a language-independent data format, Booleans True and False are true and false.
            lammps_stages_and_methods_str = lammps_stages_and_methods_str.replace(
                "true", "True"
            ).replace("false", "False")
            f.write(f"lammps_stages_and_methods = {lammps_stages_and_methods_str}\n")


@log_function_call
def save_pickle_object_as_file(
    file_name: str, molecules_objects: Dict[str, dict], mixture_table: Dict[str, dict]
) -> None:
    """
    Save a collection of molecular objects and mixture table as a pickle file.

    :param file_name: The name of the pickle file to be created or overwritten.
    :type file_name: str
    :param molecules_objects: A dictionary containing molecular objects.
    :type molecules_objects: dict
    :param mixture_table: A dictionary containing information about the mixture composition.
    :type mixture_table: dict

    :return: None
    :rtype: None
    """
    if not file_name.endswith(".pkl"):  # Append .pkl extension if not provided
        file_name += ".pkl"

    flattened_dictionary = {}

    # Iterate over the molecules in the mixture table
    for molecule_name, mixture_data in mixture_table.items():
        # Fetch the molecule object from the molecules objects dictionary
        molecule_object = molecules_objects.get(molecule_name)

        # Construct the flattened dictionary entry
        if molecule_object:
            flattened_dictionary[molecule_name] = {
                "object": molecule_object,
                "number": mixture_data["number"],
                "rotate": mixture_data["rotate"],
            }

    with open(file_name, "wb") as f:
        pickle.dump(flattened_dictionary, f)


@log_function_call
def load_pickle_object_from_file(file_name: str) -> Any:
    """
    Load a pickle object from a file.

    :param file_name: The name of the pickle file to be loaded.
    :type file_name: str

    :return: The deserialized object stored in the pickle file.
    :rtype: Any
    """
    with open(file_name, "rb") as f:
        return pickle.load(f)


def clean_string(input_string: str) -> str:
    """
    Clean a string by removing leading and trailing white spaces and replacing spaces in the middle with underscores.

    :param input_string: The input string to be cleaned.
    :type input_string: str

    :return: The cleaned string.
    :rtype: str
    """
    # Remove leading and trailing white spaces
    trimmed_string = input_string.strip()

    # Replace spaces in the middle with underscores
    cleaned_string = trimmed_string.replace(" ", "_")

    return cleaned_string


@log_function_call
def csv_to_dict(file_path: str) -> Dict[str, dict]:
    """
    Read a CSV file and convert it into a dictionary with the first column as keys
    and the second column as values.

    :param file_path: The path to the CSV file.
    :type file_path: str

    :return: A dictionary with the first column of the CSV as keys and the second as values.
    :rtype: dict
    """
    with open(file_path, mode="r", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)
        loaded_molecules = {}
        for molecule in reader:
            name = clean_string(molecule[0])
            smiles = clean_string(molecule[1])
            number = int(clean_string(molecule[2]))
            rotate = bool(clean_string(molecule[3]).lower())
            loaded_molecules[name] = {
                "smiles": smiles,
                "number": number,
                "rotate": rotate,
            }
        return loaded_molecules


@log_function_call
def is_valid_smiles(smiles: str) -> bool:
    """
    Check if a SMILES string is valid and can be processed by RDKit.

    :param smiles: The SMILES string to check.
    :type smiles: str

    :return: True if the SMILES is valid, False otherwise.
    :rtype: bool
    """
    try:
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is not None:
            return True
        else:
            return False
    except Exception as e:
        return False


@log_function_call
def get_last_trajectory(
    file_name: str, output_file: Optional[str] = None
) -> Tuple[List[str], List[str]]:
    """
    Extract the last trajectory data from a LAMMPS output file.

    :param file_name: The name of the LAMMPS output file.
    :type file_name: str
    :param output_file: The name of the output file to save the last trajectory data (optional).
    :type output_file: str, optional

    :return: A tuple containing header lines and data lines of the last trajectory.
    :rtype: Tuple[List[str], List[str]]
    """
    with FileReadBackwards(file_name, encoding="utf-8") as frb:
        lines = []
        for line in frb:
            lines.append(line)
            if "TIMESTEP" in line:
                break

    # Reverse to keep the original order
    lines = lines[::-1]
    header_lines = lines[:9]  # First 9 lines as the header
    data_lines = lines[9:]  # Rest of the lines as the data

    if output_file:
        # Writing last trajectory into last.lammpstrj:
        header_lines[1] = "0"
        with open(file=output_file, mode="w") as f:
            f.write("\n".join(header_lines + data_lines))

    return header_lines, data_lines


@log_function_call
def display_message(
    message: str,
    title: str,
    dialog_type: Literal["error", "warning", "information", "question"],
) -> None:
    """
    Displays a dialog window with a specified icon and message.

    :param message: The text message to be displayed in the dialog.
    :type message: str
    :param title: The title of the dialog window.
    :type title: str
    :param dialog_type: The type of dialog to display.
        This determines the icon used in the dialog.
    :type dialog_type: Literal['error', 'warning', 'information', 'question']

    :return: None
    :rtype: None
    """

    dialog = QMessageBox()
    dialog.setText(message)
    dialog.setWindowTitle(title)

    # Set the icon based on the dialog_type
    if dialog_type == "error":
        dialog.setIcon(QMessageBox.Critical)
    elif dialog_type == "warning":
        dialog.setIcon(QMessageBox.Warning)
    elif dialog_type == "information":
        dialog.setIcon(QMessageBox.Information)
    elif dialog_type == "question":
        dialog.setIcon(QMessageBox.Question)
    else:
        dialog.setIcon(QMessageBox.NoIcon)

    dialog.exec_()
