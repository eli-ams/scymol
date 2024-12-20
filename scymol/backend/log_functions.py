import datetime
import functools
import os
import warnings
from pathlib import Path


def get_log_file_name(suffix: str = "log.txt") -> str:
    """
    Generate a log file name with a timestamp.

    Args:
        suffix (str, optional): The suffix to be added to the filename. Defaults to "log.txt".

    Returns:
        str: A string representing the log file name with a timestamp.
    """
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    log_file_name = f"{timestamp}_{suffix}"
    return log_file_name


def create_log_file(logdir: str = "", constant: bool = False) -> str:
    """
    Create a log file and return its absolute path.

    Args:
        logdir (str, optional): The directory where the log file will be created. Defaults to the current directory.
        constant (bool, optional): If True, the log file will have a constant name 'log.txt' instead of timestamped. Defaults to False.

    Returns:
        str: The absolute path to the created log file.
    """
    # Convert logdir to a Path object for better path handling
    logdir_path = Path(logdir)

    # Choose log file name based on whether constant is True or False
    if not constant:
        logfile_name = logdir_path / get_log_file_name(suffix="log.txt")
    else:
        logfile_name = logdir_path / "log.txt"

    # Ensure the directory exists
    logfile_name.parent.mkdir(parents=True, exist_ok=True)

    # Get the absolute path of the log file
    absolute_path = logfile_name.resolve()

    # Create and clear the log file
    with open(absolute_path, "w") as log_file:
        log_file.write("")  # Clear the contents of the file by writing an empty string
    return str(absolute_path)


def print_to_log(logfile: str, message: str, warning: bool = False) -> None:
    """
    Print a message to a log file with timestamp and optionally raise a warning.

    Args:
        logfile (str): The path to the log file where the message will be written.
        message (str): The message to be written to the log file.
        warning (bool, optional): If True, raise a warning with the message. Defaults to False.

    Returns:
        None
    """
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H:%M:%S")

    log_message = f"{timestamp} | {message}"

    with open(logfile, "a") as log_file:
        log_file.write(log_message + "\n")

    if warning:
        warnings.warn(log_message)

    print(log_message, flush=True)
