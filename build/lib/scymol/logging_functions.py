import functools
import importlib
import logging
from typing import Callable

logging.basicConfig(
    filename=importlib.resources.files("scymol").joinpath("program.log"),
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    filemode="w",
)


def print_to_log(message: str, level: str = "info"):
    """
    Function to log a custom message with a specified level.

    :param message: The message to be logged.
    :type message: str
    :param level: The log level ('info', 'warning', 'critical').
    :type level: str
    """
    if level.lower() == "warning":
        logging.warning(message)
    elif level.lower() == "critical":
        logging.critical(message)
    else:
        # Default to info level
        logging.info(message)


def log_function_call(func: Callable) -> Callable:
    """
    Decorator to log the name of a function when it is called, including class name if applicable.

    :param func: The function to be wrapped.
    :type func: Callable

    :return: The wrapped function.
    :rtype: Callable
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check if the function is a method of a class
        if args and hasattr(args[0], "__class__"):
            class_name = args[0].__class__.__name__
            func_name = f"{class_name}.{func.__name__}"
            is_method = True
        else:
            func_name = func.__name__
            is_method = False

        logging.info(func_name)

        # Adjust arguments for class methods, skipping 'self'
        if is_method:
            arg_count = func.__code__.co_argcount - 1
            args = args[: arg_count + 1]

        return func(*args, **kwargs)

    return wrapper
