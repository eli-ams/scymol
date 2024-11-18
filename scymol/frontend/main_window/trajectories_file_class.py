import copy
from scymol.logging_functions import print_to_log, log_function_call


class TrajectoriesClass:
    """
    Class for handling and analyzing trajectory data from LAMMPS simulations.

    This class provides functionalities to parse, store, and analyze trajectory data
    such as atomic positions and simulation headers.

    Attributes:
        density_profiles (list): List of density profiles.
        nbr_of_trajectories_loaded (int): Number of trajectories loaded.
        header (dict): Parsed header information of the trajectory file.
        atom_data (dict): Parsed atomic data from the trajectory file.
        instantaneous (dict): Parsed instantaneous properties.
        file_pointer (file): File pointer to the trajectory file.
        trajectories (list): Collection of trajectories.
        counter (int): A counter for the number of trajectories processed.

    Examples:
        How to use TrajectoriesClass to read and analyze trajectory data:

        ```python

        trajectory = TrajectoriesClass()
        directory = "output/"
        trajectory.initialize_trajectory_file(directory + "lammps_trajectory_file.lammpstrj")
        trajectory.next()
        trajectory.go_to(n=1)
        print(trajectory.trajectories[-1]["atom_data"])
        trajectory.close_file()
        del trajectory
        ```
    """

    @log_function_call
    def __init__(self):
        """
        Initialize the TrajectoriesClass instance.
        """
        self.density_profiles = []
        self.nbr_of_trajectories_loaded = None
        self.header = {}
        self.atom_data = {}
        self.instantaneous = {}
        self.file_pointer = None
        self.trajectories = []  # Added variable to store the collection of trajectories
        self.counter = 0

    def parse_header(self, lines):
        """
        Parse header information from lines of a LAMMPS trajectory file.

        :param lines: Lines containing the header information.
        :type lines: list
        :return: Parsed header information.
        :rtype: dict
        """
        header = {}
        for i, line in enumerate(lines):
            line = line.strip()
            if i == 1:
                header["TIMESTEP"] = int(line)
            elif i == 3:
                header["NUMBER OF ATOMS"] = int(line)
            elif i >= 5 and i <= 7:
                bounds_key = f"BOX BOUNDS {i - 4}"
                header[bounds_key] = list(map(float, line.split()))
            elif i == 8:
                header["ITEMS"] = line.split()[2:]

        new_zlo = header["BOX BOUNDS 3"][
            0
        ]  # - statistics.mean([header['BOX BOUNDS 3'][0], header['BOX BOUNDS 3'][1]])
        new_zhi = header["BOX BOUNDS 3"][
            1
        ]  # - statistics.mean([header['BOX BOUNDS 3'][0], header['BOX BOUNDS 3'][1]])
        header["BOX BOUNDS 3"][0] = new_zlo
        header["BOX BOUNDS 3"][1] = new_zhi
        return header

    def parse_atom_data(self, lines):
        """
        Parse atom data from lines of a LAMMPS trajectory file.

        :param lines: Lines containing the atom data.
        :type lines: list
        :return: Parsed atom data.
        :rtype: dict
        """
        n_atoms = len(lines)
        items = self.header["ITEMS"]
        atom_data = {item: [] for item in items}

        for line in lines:
            atom_info = list(map(float, line.split()))
            for i, item in enumerate(items):
                atom_data[item].append(atom_info[i])

        return atom_data

    @log_function_call
    def initialize_trajectory_file(self, file_path: str) -> None:
        """
        Initialize reading from a trajectory file.

        :param file_path: Path to the trajectory file.
        :type file_path: str
        """
        self.file_pointer = open(file_path, "r")

    def store_current_trajectory(self) -> None:
        """
        Store the current trajectory in memory.
        :return: None
        :rtype: None
        """
        # Append the new trajectory to the collection
        self.trajectories.append(
            {
                "header": copy.deepcopy(self.header),
                "atom_data": copy.deepcopy(self.atom_data),
                "instantaneous": copy.deepcopy(self.instantaneous),
                "density_profiles": copy.deepcopy(self.density_profiles),
            }
        )

    @log_function_call
    def go_to(self, n: int) -> None:
        """
        Go to a specific trajectory index in the file.

        :param n: Index of the trajectory to go to.
        :type n: int
        """
        # Verify that the file_pointer has been initialized
        if self.file_pointer is None:
            raise RuntimeError(
                "File pointer is not initialized. Use 'initialize_trajectory_file' first."
            )

        # Calculate the line where the nth trajectory starts
        lines_per_trajectory = 9 + self.header["NUMBER OF ATOMS"]
        start_line = n * lines_per_trajectory

        # Move the file pointer to the start line
        self.file_pointer.seek(0)  # Rewind the file to the beginning
        for _ in range(start_line):
            self.file_pointer.readline()

        # Read the new trajectory
        self.next()

    @log_function_call
    def next(self) -> None:
        """
        Read the next trajectory in the file.
        :return: None
        :rtype: None
        """
        header_lines = [self.file_pointer.readline() for _ in range(9)]
        self.header = self.parse_header(header_lines)

        n_atoms = self.header["NUMBER OF ATOMS"]
        atom_data_lines = [self.file_pointer.readline() for _ in range(n_atoms)]
        self.atom_data = self.parse_atom_data(atom_data_lines)
        self.sort_atoms_by_key(key="id")
        if not self.nbr_of_trajectories_loaded:
            self.nbr_of_trajectories_loaded = 1
        else:
            self.nbr_of_trajectories_loaded += 1

        self.store_current_trajectory()
        self.counter += 1

    @log_function_call
    def read_all_trajectories(self) -> None:
        """
        Read all trajectories from the file.
        :return: None
        :rtype: None
        """
        while True:
            try:
                self.next()
            except:
                break

    @log_function_call
    def sort_atoms_by_key(self, key: str) -> None:
        """
        Sort atoms based on a specified key.

        :param key: The key to sort by.
        :type key: str
        """
        if key not in self.atom_data:
            raise KeyError(f"Key '{key}' is not present in the atom_data dictionary.")

        sorted_indices = sorted(
            range(len(self.atom_data[key])), key=lambda k: self.atom_data[key][k]
        )

        for item in self.atom_data:
            self.atom_data[item] = [self.atom_data[item][i] for i in sorted_indices]

    @log_function_call
    def close_file(self) -> None:
        """
        Close the trajectory file.
        :return: None
        :rtype: None
        """
        if self.file_pointer:
            self.file_pointer.close()

    @log_function_call
    def write_lammps_dump_file(self, filename: str) -> None:
        """
        Write the trajectories to a LAMMPS dump file. This function was used in testing stages of the program's
        development, but it is not currently used in Scymol.

        :param filename: Name of the file to write to.
        :type filename: str
        """
        # Open file for writing
        with open(filename, "w") as f:
            # Iterate through the stored trajectories
            for trajectory in self.trajectories:
                # Write header
                f.write("ITEM: TIMESTEP\n")
                f.write(f"{trajectory['header']['TIMESTEP']}\n")
                f.write("ITEM: NUMBER OF ATOMS\n")
                f.write(f"{trajectory['header']['NUMBER OF ATOMS']}\n")
                f.write("ITEM: BOX BOUNDS pp pp ff\n")
                for i in range(1, 4):
                    bounds_key = f"BOX BOUNDS {i}"
                    f.write(
                        f"{trajectory['header'][bounds_key][0]} {trajectory['header'][bounds_key][1]}\n"
                    )

                # Write atom data header
                f.write("ITEM: ATOMS " + " ".join(trajectory["header"]["ITEMS"]) + "\n")

                # Write atom data
                n_atoms = trajectory["header"]["NUMBER OF ATOMS"]
                for i in range(n_atoms):
                    atom_data_str = " ".join(
                        str(trajectory["atom_data"][key][i])
                        for key in trajectory["header"]["ITEMS"]
                    )
                    f.write(f"{atom_data_str}\n")
