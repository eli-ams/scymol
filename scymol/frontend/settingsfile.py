import json
import os
from scymol.logging_functions import print_to_log, log_function_call


class SettingsFile:
    """
    Represents a settings file manager for storing and retrieving configuration settings.

    This class provides methods for loading or creating a settings file, updating individual settings,
    and saving the settings to a JSON file.

    Parameters:
        filename (str, optional): The name of the settings file. Default is "config.json".

    Attributes:
        filename (str): The name of the settings file.
        settings (dict): A dictionary containing the configuration settings.

    Methods:
        __init__(self, filename="config.json"):
            Initializes a SettingsFile object with the specified filename and loads or creates
            the settings file.

        load_or_create_settings(self):
            Loads existing settings from the settings file if it exists, otherwise creates
            default settings and saves them to the file.

        create_default_settings(self):
            Creates default configuration settings and saves them to the settings file.

        load_settings(self):
            Loads configuration settings from the settings file.

        update_class_variables(self):
            Updates class attributes with the values from the loaded settings.

        update_setting(self, key, value):
            Updates a specific setting identified by its key with the provided value.

        save_settings(self):
            Saves the current configuration settings to the settings file in JSON format.
    """

    @log_function_call
    def __init__(self, filename: str = "config.json") -> None:
        """
        Initializes a SettingsFile object with the specified filename and loads or creates
        the settings file.

        :param filename: The name of the settings file. Default is "config.json".
        :type filename: str
        """
        self.filename = filename
        self.load_or_create_settings()

    @log_function_call
    def load_or_create_settings(self) -> None:
        """
        Loads existing settings from the settings file if it exists, otherwise creates
        default settings and saves them to the file.

        :return: None
        :rtype: None
        """
        if not os.path.exists(self.filename):
            self.create_default_settings()
            print_to_log("File is not there, create")
        else:
            print_to_log("Loaded settings.")
            self.load_settings()

    @log_function_call
    def create_default_settings(self) -> None:
        """
        Creates default configuration settings and saves them to the settings file.

        :return: None
        :rtype: None
        """
        self.settings = {
            "resolution_width": 960,
            "resolution_height": 540,
            "lammps_location": "lmp",
            "mpi_location": "mpiexec",
            "recent_files": [],
        }
        if os.name == "nt":  # for Windows
            print_to_log("Loading settings for Windows-like systems")
            self.settings["lammps_location"] = "lammps.exe"
            # The -localonly flag is necessary for Windows systems to run MPI tasks locally,
            # without requiring elevation.
            self.settings["mpi_location"] = "mpiexec.exe -localonly"
        else:  # Unix and Unix-like platforms
            print_to_log("Loading settings for Unix-like systems")
            self.settings["lammps_location"] = "lmp"
            self.settings["mpi_location"] = "mpiexec"

        self.save_settings()

    @log_function_call
    def load_settings(self):
        """
        Load configuration settings from the specified settings file.

        This method reads the contents of the settings file in JSON format and updates the
        `settings` attribute of the SettingsFile object. Additionally, it updates class attributes
        with the values from the loaded settings.

        Raises:
            FileNotFoundError: If the specified settings file does not exist.

        Example:
            To load settings from a file named "custom_settings.json" and update the class attributes:

            >>> settings_manager = SettingsFile("config.json")
            >>> settings_manager.load_settings()
        """
        with open(self.filename, "r") as file:
            self.settings = json.load(file)
        self.update_class_variables()

    @log_function_call
    def update_class_variables(self):
        """
        Update class attributes with values from the loaded configuration settings.

        This method iterates through the key-value pairs in the `settings` attribute and
        sets the corresponding class attributes to the values from the loaded settings.

        Example:
            To update class attributes with settings loaded from a file:

            >>> settings_manager = SettingsFile()
            >>> settings_manager.load_settings()
            >>> settings_manager.update_class_variables()
        """
        for key, value in self.settings.items():
            setattr(self, key, value)

    @log_function_call
    def update_setting(self, key, value):
        """
        Update a specific configuration setting identified by its key.

        This method allows you to update a specific configuration setting by providing its
        key and the new value. It then updates both the `settings` dictionary and the
        corresponding class attribute with the new value.

        Parameters:
            key (str): The key of the setting to be updated.
            value: The new value to assign to the setting.

        Example:
            To update the "resolution_width" setting to 1024:

            >>> settings_manager = SettingsFile()
            >>> settings_manager.load_settings()
            >>> settings_manager.update_setting("resolution_width", 1024)
        """
        self.settings[key] = value
        self.update_class_variables()
        # self.save_settings()  # Uncomment this line if you want to save the changes immediately.

    @log_function_call
    def save_settings(self):
        """
        Save the current configuration settings to the settings file in JSON format.

        This method writes the current configuration settings stored in the `settings` attribute
        to the specified settings file in JSON format. It ensures that the settings are neatly
        formatted with an indentation of 4 spaces.

        Example:
            To save the current configuration settings to the file "custom_settings.json":

            >>> settings_manager = SettingsFile("custom_settings.json")
            >>> settings_manager.save_settings()
        """
        with open(self.filename, "w") as file:
            json.dump(self.settings, file, indent=4)
