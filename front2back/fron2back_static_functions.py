import fnmatch
import os
import re
from typing import Literal
from PyQt5.QtWidgets import QMessageBox
from logging_functions import print_to_log, log_function_call


@log_function_call
def find_files_with_keywords(
    directory: str, keywords: list[str], reject_with_keywords: list[str] = None
) -> list[str]:
    """
    Searches for files in the given directory that contain all specified keywords in their names.

    :param directory: The directory path where the files will be searched.
    :type directory: str
    :param keywords: The list of keywords that must be included in the file names.
    :type keywords: list[str]
    :param reject_with_keywords: The list of keywords that must not be included in the file names, defaults to None.
    :type reject_with_keywords: list[str], optional
    :return: A list of file names that contain all of the keywords and none of the reject_with_keywords.
    :rtype: list[str]
    """
    matched_files = []
    for file in os.listdir(directory):
        if all(fnmatch.fnmatch(file, f"*{keyword}*") for keyword in keywords) and all(
            not fnmatch.fnmatch(file, f"*{reject_keyword}*")
            for reject_keyword in (reject_with_keywords or [])
        ):
            matched_files.append(os.path.join(directory, file))
    return matched_files


@log_function_call
def get_latest_mixture_folder_by_count(output_dir: str) -> str:
    """
    Returns the folder name with the highest integer 'n' by counting the directories in the output directory.

    :param output_dir: The path to the output directory to scan.
    :type output_dir: str
    :return: The folder name using the counted directories as the integer identifier.
    :rtype: str
    """

    # Filter the list to include only directories
    dir_count = sum(
        os.path.isdir(os.path.join(output_dir, item)) for item in os.listdir(output_dir)
    )

    # Construct the folder name with the latest integer identifier
    latest_mixture_folder_name = f"mixture_{dir_count}"

    return latest_mixture_folder_name


@log_function_call
def calculate_progress(
    directory: str, list_of_progress: list[list[int]]
) -> tuple[float, float]:
    """
    Calculates the progress in a directory based on a list of progress stages and substages.

    :param directory: The path to the directory where progress is to be evaluated.
    :type directory: str
    :param list_of_progress: A list containing lists of integers, each representing substages in a stage.
    :type list_of_progress: list[list[int]]
    :return: A tuple containing the total progress and the total number of substages.
    :rtype: tuple[float, float]
    """
    latest_stage = -1
    latest_substage = -1
    latest_file = ""

    # Calculate the total number of substages
    total_substages = sum(len(stage) for stage in list_of_progress)

    # Compile a regular expression to match files with the naming convention
    file_pattern = re.compile(r"^(\d+)\.(\d+)_")

    # Iterate over the files in the given directory to find the latest file
    for filename in os.listdir(directory):
        # Use the regular expression to search for matches
        match = file_pattern.search(filename)
        if match:
            # Convert the stage and substage to integers and compare
            stage, substage = map(int, match.groups())
            if (stage, substage) > (latest_stage, latest_substage):
                latest_stage, latest_substage = stage, substage
                latest_file = filename

    # If no file is found, return a message indicating no progress
    if not latest_file:
        return 0, total_substages

    # Extract stage and substage from the latest file name
    current_stage, current_substage = latest_stage, latest_substage

    # Calculate the cumulative number of substages up to the current stage
    cumulative_substages = sum(
        len(list_of_progress[i]) for i in range(current_stage - 1)
    )

    # Index of the current substage within its stage
    substage_index = list_of_progress[current_stage - 1].index(current_substage) + 1

    # Overall progress calculation
    total_progress = cumulative_substages + substage_index

    return total_progress, total_substages


@log_function_call
def display_message(
    message: str,
    title: str,
    dialog_type: Literal["error", "warning", "information", "question"],
) -> None:
    """
    Displays a dialog window with a specific icon and message.

    :param message: The text message to be displayed in the dialog.
    :type message: str
    :param title: The title of the dialog window.
    :type title: str
    :param dialog_type: The type of dialog to display, determining the icon used.
    :type dialog_type: Literal["error", "warning", "information", "question"]
    :return: None
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
