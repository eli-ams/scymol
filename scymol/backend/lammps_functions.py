import math
from file_read_backwards import FileReadBackwards


def get_last_trajectory(file_name: str) -> tuple[list[str], list[str]]:
    """
    Get header and data lines from the last LAMMPS MD trajectory in a Dump file.

    Args:
        file_name (str): Name of the Dump file.

    Returns:
        tuple[list[str], list[str]]: Tuple with header and data lines.
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
    return header_lines, data_lines


def parse_trajectory(header: list[str], data: list[str]) -> dict:
    """
    Parse a LAMMPS MD trajectory from header and data lines.

    Args:
        header (list[str]): List of header lines containing attribute information.
        data (list[str]): List of data lines containing numerical values.

    Returns:
        dict: A dictionary containing two keys:
            - 'header': Parsed header information as a dictionary.
            - 'data': Parsed trajectory data as a dictionary with attributes as keys.

    Example:
        trajectory = parse_trajectory(header_lines, data_lines)
    """
    # Extract attribute names from the last line of the header
    attributes = header[-1].split()[2:]  # Ignore 'ITEM:' and 'ATOMS'

    # Initialize an empty list for each attribute
    trajectory_data = {attr: [] for attr in attributes}

    # Parse each line in the data block
    for line in data:
        values = line.split()
        for attr, value in zip(attributes, values):
            # Convert numerical values to the appropriate type
            try:
                num_value = float(value)
                if num_value.is_integer():
                    num_value = int(num_value)
                value = num_value
            except ValueError:
                raise Exception(
                    f"Value {value} from attribute {attr} could not be converted into a number."
                )
            trajectory_data[attr].append(value)

    return {"header": parse_header(header=header), "data": trajectory_data}


def parse_header(header: list[str]) -> dict:
    """
    Parse the header information from a LAMMPS MD trajectory header.

    Args:
        header (list[str]): List of header lines containing trajectory information.

    Returns:
        dict: A dictionary containing parsed header information with the following keys:
            - 'timestep': The timestep as an integer.
            - 'nbr_of_atoms': The number of atoms as an integer.
            - 'box_bounds': List of box boundary values as strings.
            - 'box_dims': List of box dimensions as floats.
            - 'attributes': List of attribute names.

    Example:
        header_info = parse_header(header_lines)
    """
    header_info = {}

    # Extract timestep
    header_info["timestep"] = int(header[1])

    # Extract number of atoms
    header_info["nbr_of_atoms"] = int(header[3])

    # Extract box bounds
    header_info["box_bounds"] = header[4].split()[3:]

    # Extract box dimensions
    dims_lines = header[5:8]
    dims = []
    for line in dims_lines:
        dims.extend([float(val) for val in line.split()])
    header_info["box_dims"] = dims

    # Extract attributes
    header_info["attributes"] = header[8].split()[2:]

    return header_info


def read_avetime_dump_file(file_name: str) -> dict:
    """
    Read and parse an avetime dump file and return the data as a dictionary.

    Args:
        file_name (str): Name of the avetime dump file to read.

    Returns:
        dict: A dictionary containing parsed data with headers as keys and lists of values as values.

    Example:
        data_dict = read_avetime_dump_file("avetime_dump.txt")

        The resulting data_dict may have the following form:
        {'TimeStep': [1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
         'v_time': [501.0, 1501.0, 2501.0, 3501.0, 4501.0],
         'c_thermo_temp': [222.3, 294.504, 298.379, 298.218, 298.227],...}
    """
    data_dict = {}

    with open(file_name, "r") as file:
        for i, line in enumerate(file):
            # Remove '#' character and split the line into elements
            split_line = line.replace("#", "").split()

            if i == 1:  # The second line contains the headers
                headers = split_line  # Now, we do not skip "TimeStep"
                for header in headers:
                    data_dict[header] = []
            elif i > 1:  # The following lines contain the data
                for j, item in enumerate(split_line):
                    data_dict[headers[j]].append(float(item))

    return data_dict


def format_line(line: str, first_column_padding: int = 20) -> str:
    """
    Format a line of text with a specified padding for the first column.

    Args:
        line (str): The input line of text to be formatted.
        first_column_padding (int, optional): The number of spaces to pad the first column.
            Defaults to 20.

    Returns:
        str: The formatted line with the specified padding for the first column.

    Example:
        formatted_line = format_line("Attribute Value1 Value2")
    """
    words = line.split()
    formatted_line = words[0].ljust(first_column_padding)
    formatted_line += " ".join(words[1:])
    return formatted_line


def calculate_strain_rate(
    dim_initial: float,
    dim_final: float,
    strain_style: str,
    telapsed: float,
    wallskin: float = 2.0,
) -> float:
    """
    Calculate the strain rate based on the initial and final dimensions and strain style.

    Args:
        dim_initial (float): Initial dimension of the system.
        dim_final (float): Final dimension of the system.
        strain_style (str): Strain style, 't' for logarithmic strain.
        telapsed (float): Elapsed time for the strain.
        wallskin (float, optional): Width of the wall skin (default is 2.0).

    Returns:
        float: The calculated strain rate.

    Example:
        strain_rate = calculate_strain_rate(1000.0, 38.75, 't', 100.0)
    """
    if strain_style == "t":
        return math.log((dim_final + 2 * wallskin) / dim_initial) / telapsed
