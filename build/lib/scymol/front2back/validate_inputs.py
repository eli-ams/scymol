import os
import subprocess
from scymol.logging_functions import log_function_call


def validate_integer(value: int, min_value: int = None, max_value: int = None) -> int:
    """
    Validates that a value is an integer and optionally within a specified range.

    :param value: The value to validate.
    :type value: int
    :param min_value: The minimum allowable value, defaults to None.
    :type min_value: int, optional
    :param max_value: The maximum allowable value, defaults to None.
    :type max_value: int, optional
    :return: The validated integer value.
    :rtype: int
    :raises ValueError: If value is not an integer or not within the specified range.
    """
    if not isinstance(value, int):
        raise ValueError(f"Expected integer, got {type(value).__name__}")
    if min_value is not None and value < min_value:
        raise ValueError(f"Value {value} is less than minimum {min_value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"Value {value} is greater than maximum {max_value}")
    return value


def validate_float(
    value: float, min_value: float = None, max_value: float = None
) -> float:
    """
    Validates that a value is a float and optionally within a specified range.

    :param value: The value to validate.
    :type value: float
    :param min_value: The minimum allowable value, defaults to None.
    :type min_value: float, optional
    :param max_value: The maximum allowable value, defaults to None.
    :type max_value: float, optional
    :return: The validated float value.
    :rtype: float
    :raises ValueError: If value is not a float or not within the specified range.
    """
    if not isinstance(value, float):
        raise ValueError(f"Expected float, got {type(value).__name__}")
    if min_value is not None and value < min_value:
        raise ValueError(f"Value {value} is less than minimum {min_value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"Value {value} is greater than maximum {max_value}")
    return value


def validate_string(value: str, allowed_values: list[str] = None) -> str:
    """
    Validates that a value is a string and optionally one of the allowed values.

    :param value: The value to validate.
    :type value: str
    :param allowed_values: A list of allowable string values, defaults to None.
    :type allowed_values: list[str], optional
    :return: The validated string value.
    :rtype: str
    :raises ValueError: If value is not a string or not one of the allowed values.
    """
    if not isinstance(value, str):
        raise ValueError(f"Expected string, got {type(value).__name__}")
    if allowed_values and value not in allowed_values:
        raise ValueError(f"Value {value} is not an allowed option")
    return value


def validate_path(value: str) -> str:
    """
    Validates that a provided path exists.

    :param value: The path to validate.
    :type value: str
    :return: The validated path.
    :rtype: str
    :raises FileNotFoundError: If the path does not exist.
    """
    if not os.path.exists(os.path.dirname(value)):
        raise FileNotFoundError(f"The path {value} does not exist")
    return value


@log_function_call
def validate_constants(constants: dict[str, float]) -> dict[str, float]:
    """
    Validates a dictionary of constants where keys are strings and values are floats.

    :param constants: The dictionary of constants to validate.
    :type constants: dict[str, float]
    :return: The validated dictionary of constants.
    :rtype: dict[str, float]
    :raises ValueError: If keys are not strings or values are not floats.
    """
    for key, value in constants.items():
        validate_string(key)
        validate_float(value)
    return constants


@log_function_call
def validate_lammps_mpi_environment(
    lammps_path: str, mpi_path: str, dir_to_dummy_lammps_sim: str
) -> None:
    """
    Validates the LAMMPS and MPI environment by running a dummy LAMMPS simulation.

    :param lammps_path: The path to the LAMMPS executable.
    :type lammps_path: str
    :param mpi_path: The path to the MPI executable.
    :type mpi_path: str
    :param dir_to_dummy_lammps_sim: The directory containing the dummy LAMMPS simulation.
    :type dir_to_dummy_lammps_sim: str
    :return: None
    :raises ValueError: If the MPI/LAMMPS environment returns an error during execution.
    """
    os.chdir(dir_to_dummy_lammps_sim)
    # Construct the command with the provided paths
    command = f"{mpi_path} -n 2 {lammps_path} -in stage_1.in"

    try:
        # Execute the command as a subprocess
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Check if the subprocess ended with a non-zero (error) exit status
        result.check_returncode()

        os.chdir("../..")

    except subprocess.CalledProcessError as e:
        os.chdir("../..")
        raise ValueError(f"MPI/LAMMPS returned an error: {e}")
