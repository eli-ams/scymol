import os
import signal
import subprocess
import sys
import time
from typing import List, Optional
import psutil

from PyQt5.QtCore import QThread, pyqtSignal
from scymol.logging_functions import print_to_log, log_function_call


class BackendThread(QThread):
    """
    A thread for running backend processes.

    This class extends QThread and provides functionality to run backend processes in a separate thread.

    :ivar finished_signal: Signal emitted when the thread is done with an integer return code and a string message.
    :vartype finished_signal: pyqtSignal
    :ivar output_signal: Signal emitted to provide output messages from the running process.
    :vartype output_signal: pyqtSignal
    """

    finished_signal = pyqtSignal(int, str)
    output_signal = pyqtSignal(str)

    @log_function_call
    def __init__(self, command: List[str]) -> None:
        """
        Initialize a BackendThread instance.

        :param command: A list containing the command and arguments to execute.
        :type command: List[str]
        """
        super().__init__()
        self.command = command
        self.process: Optional[subprocess.Popen] = None

    @log_function_call
    def run(self) -> None:
        stderr_output = []  # List to hold lines of stderr output
        try:
            # Configure subprocess arguments based on the operating system
            popen_args = {}

            if sys.platform != "win32":
                popen_args["preexec_fn"] = os.setsid

            self.process = subprocess.Popen(self.command, **popen_args)

            # For debugging, you might want to communicate directly
            stdout, stderr = self.process.communicate()

            if stderr:
                stderr_output.append(stderr.decode("utf-8").strip())

            retcode = self.process.poll()
            if retcode is not None:
                if stderr_output:  # If there are any stderr lines
                    self.finished_signal.emit(retcode, "\n".join(stderr_output))
                else:
                    self.finished_signal.emit(
                        retcode, "Process finished without errors."
                    )

        except Exception as e:
            print("Error during simulation:", e)
            self.finished_signal.emit(-1, "Process initialization error.")

    @log_function_call
    def terminate_process(self) -> None:
        """
        Terminate the running process if it exists.

        This method tries to terminate the process gracefully and then forcefully if it does not terminate within a given time frame.
        """
        if self.process:
            try:
                # On Windows, terminate the entire process tree
                if sys.platform == "win32":
                    parent = psutil.Process(self.process.pid)
                    children = parent.children(recursive=True)

                    # First, try to terminate all child processes gracefully
                    for child in children:
                        child.terminate()
                    gone, alive = psutil.wait_procs(children, timeout=5)

                    if alive:
                        # If some processes are still alive after trying to terminate them, forcefully kill them
                        for child in alive:
                            child.kill()

                    # Finally, terminate the parent process
                    parent.terminate()
                    parent.wait(5)  # Wait for the parent process to terminate

                    if parent.is_running():
                        parent.kill()  # Forcefully kill the parent process if it's still running

                    print("Terminated process and its children.")

                else:
                    # On Unix, use killpg to terminate the process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    print("Attempting graceful termination...")

                    # Wait for a short period to see if the process exits
                    for i in range(5):  # Wait up to 5 seconds
                        if self.process.poll() is not None:
                            print("Process terminated gracefully.")
                            return
                        time.sleep(1)

                    # If the process hasn't exited, forcibly kill it
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    print("Forcefully terminated process.")

            except Exception as e:
                print(f"An error occurred while terminating the process: {e}")
