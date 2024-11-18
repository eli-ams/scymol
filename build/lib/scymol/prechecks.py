import json
from typing import List
from scymol.logging_functions import print_to_log, log_function_call


@log_function_call
def check_dependencies() -> List[str]:
    """
    Check if required dependencies are installed.

    This function checks if the following modules are installed:

    - PyQt5
    - numpy
    - scipy
    - matplotlib
    - pysimm
    - psutil
    - sobol_seq
    - numba
    - rdkit
    - file_read_backwards
    - sigfig

    :return: List of missing module names.
    :rtype: List[str]

    :raises ImportError: If a required module cannot be imported.
    """

    # List of modules that are necessary for the application
    required_modules = [
        "PyQt5",
        "numpy",
        "scipy",
        "matplotlib",
        "pysimm",
        "psutil",
        "sobol_seq",
        "numba",
        "rdkit",
        "file_read_backwards",
        "sigfig",
    ]

    # Initialize an empty list to store the names of missing modules
    missing_modules: List[str] = []

    # Iterate through each required module to check its availability
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            # Add to the list if the module is missing
            missing_modules.append(module)

    if not missing_modules:
        print_to_log(
            message=f"All critical Python modules found:\n{json.dumps(required_modules, indent=4)}\n"
        )

    return missing_modules


# Check for missing dependencies and raise an error if any are found
missing_modules = check_dependencies()
if missing_modules:
    print_to_log(
        message=f"Modules\n{json.dumps(missing_modules, indent=4)}\nwere not found.",
        level="critical",
    )
    input(
        f"Modules\n{json.dumps(missing_modules, indent=4)}\nwere not found.\nPress Enter to exit."
    )  # Wait for the user to press Enter
    raise ImportError(f"Modules {missing_modules} were not found.")
