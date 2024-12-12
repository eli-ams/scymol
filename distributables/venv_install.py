import argparse
import os
import shutil
import subprocess
import urllib.request
import venv
import zipfile


def create_virtual_environment(venv_dir):
    """Create a virtual environment in the specified directory."""
    print(f"Creating virtual environment at {venv_dir}...")
    venv.create(venv_dir, with_pip=True)
    print("Virtual environment created.")


def download_and_install_package(venv_dir, zip_url):
    """Download and install the package from a GitHub ZIP file."""
    print(f"Downloading package from {zip_url}...")
    zip_file = "scymol.zip"
    urllib.request.urlretrieve(zip_url, zip_file)
    print("Package downloaded.")

    # Extract the ZIP file
    extract_dir = "scymol_repo"
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
    print("Package extracted.")

    # Locate setup.py in the extracted directory
    repo_dir = os.path.join(extract_dir, os.listdir(extract_dir)[0])

    # Install the package using pip
    pip_executable = os.path.join(
        venv_dir,
        "Scripts" if is_windows() else "bin",
        "pip" + (".exe" if is_windows() else ""),
    )
    print("Installing the package...")
    subprocess.check_call([pip_executable, "install", repo_dir])
    print("Package installed.")

    # Clean up
    shutil.rmtree(extract_dir)
    os.remove(zip_file)
    print("Temporary files removed.")


def download_and_install_openmpi_and_lammps(venv_dir, file_url):
    """Download and install OpenMPI and LAMMPS locally in the virtual environment (Windows only)."""
    print("Downloading LAMMPS + MPI for Windows...")
    is_zip = file_url.endswith(".zip")
    local_file = "lammps_mpi.zip" if is_zip else "lammps_mpi.tar.xz"

    urllib.request.urlretrieve(file_url, local_file)
    print("LAMMPS + MPI downloaded.")

    # Extract the entire archive
    extract_dir = "lammps_mpi_src"
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(local_file, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
    print("LAMMPS + MPI extracted.")

    # Copy all files to the virtual environment's bin directory
    target_dir = os.path.join(venv_dir, "Scripts")
    os.makedirs(target_dir, exist_ok=True)
    for root, _, files in os.walk(extract_dir):
        for file in files:
            shutil.copy(os.path.join(root, file), target_dir)

    print(f"LAMMPS + MPI copied to {target_dir}.")

    # Clean up
    shutil.rmtree(extract_dir)
    os.remove(local_file)
    print("Temporary files removed.")


def create_activation_script(venv_dir, script_dir):
    """Create a .sh or .bat script to activate the environment and run scymol."""
    script_name = "run_scymol.bat" if is_windows() else "run_scymol.sh"
    script_path = os.path.join(script_dir, script_name)

    activate_cmd = os.path.join(
        venv_dir, "Scripts" if is_windows() else "bin", "activate"
    )
    run_cmd = "scymol"

    with open(script_path, "w") as script_file:
        if is_windows():
            script_file.write(f"@echo off\n")
            script_file.write(f"call {activate_cmd}\n")
            script_file.write(f"{run_cmd}\n")
        else:
            script_file.write(f"#!/bin/bash\n")
            script_file.write(f"source {activate_cmd}\n")
            script_file.write(f"{run_cmd}\n")

    if not is_windows():
        os.chmod(script_path, 0o755)  # Make script executable on Unix-based systems
    print(f"Activation script created at {script_path}.")


def is_windows():
    """Check if the operating system is Windows (x64)."""
    return os.name == "nt"


def get_dependency_url():
    """Get the appropriate dependency URL based on the operating system."""
    if is_windows():
        return "https://github.com/eli-ams/scymol/raw/refs/heads/master/distributables/lammps+mpi_win64.zip"
    else:
        return "https://github.com/eli-ams/scymol/raw/refs/heads/master/distributables/lammps_ubuntu64.tar.xz"


def prompt_linux_mpi_lammps():
    """Prompt Linux users about the MPI/LAMMPS installation limitations."""
    print(
        "\nWARNING: Installing OpenMPI and LAMMPS locally on Linux is currently in Beta and not recommended."
    )
    print("We recommend one of the following options:")
    print("1) Install without MPI/LAMMPS and set it up manually later.")
    print("2) Install Scymol using Conda, which handles dependencies more effectively.")
    choice = input(
        "Choose 1 to continue without MPI/LAMMPS, or press any other key to exit: "
    )
    return choice.strip() == "1"


def prompt_spaces_in_path():
    """Check for spaces in the current working directory and prompt the user."""
    if " " in os.getcwd():
        print(
            "\nERROR: The installation directory contains spaces, which can cause issues."
        )
        print("Please use a directory path without spaces and try again.")
        exit(1)


def main():
    """Main function to create venv, install package, and handle dependencies."""
    prompt_spaces_in_path()

    parser = argparse.ArgumentParser(
        description="Setup and run Scymol with optional dependencies."
    )
    parser.add_argument(
        "--mpi-lammps",
        action="store_true",
        help="Download and install OpenMPI and LAMMPS locally.",
    )
    args = parser.parse_args()

    # Define the directory for the virtual environment
    venv_dir = os.path.join(os.getcwd(), "scymol", "venv")
    script_dir = os.getcwd()

    # URL for the package
    zip_url = "https://github.com/eli-ams/scymol/archive/refs/heads/master.zip"

    try:
        create_virtual_environment(venv_dir)
        download_and_install_package(venv_dir, zip_url)

        if args.mpi_lammps:
            if is_windows():
                dependency_url = get_dependency_url()
                download_and_install_openmpi_and_lammps(venv_dir, dependency_url)
            else:
                if prompt_linux_mpi_lammps():
                    print("Proceeding without MPI/LAMMPS installation...")
                else:
                    print("Exiting installation.")
                    return

        create_activation_script(venv_dir, script_dir)
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
