import os
import subprocess
import urllib.request
import zipfile
import argparse
import shutil
import tarfile


def create_conda_environment(env_dir, dependencies):
    """
    Create a Conda environment in a specified directory with the given dependencies.

    Parameters:
        env_dir (str): Path to the directory where the environment should be created.
        dependencies (list): List of dependencies to include in the environment.
    """
    print(f"Creating Conda environment in '{env_dir}' with custom channels...")
    channels = ["-c", "conda-forge", "-c", "defaults", "-c", "anaconda", "-c", "numba"]
    subprocess.check_call(
        ["conda", "create", "--prefix", env_dir, "-y"] + channels + dependencies
    )
    print(f"Conda environment created in '{env_dir}'.")


def install_package_from_github(env_dir, zip_url):
    """
    Install the Scymol package from a GitHub ZIP file into the specified Conda environment.

    Parameters:
        env_dir (str): Path to the Conda environment where the package will be installed.
        zip_url (str): URL to the ZIP file of the Scymol package.
    """
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

    # Determine the path to pip executable in the environment
    pip_executable = (
        os.path.join(env_dir, "Scripts", "pip.exe")  # Windows
        if os.name == "nt"
        else os.path.join(env_dir, "bin", "pip")  # Unix-based systems
    )

    # Ensure pip exists in the environment
    if not os.path.exists(pip_executable):
        raise FileNotFoundError(
            f"'pip' executable not found in the environment: {pip_executable}"
        )

    # Install the package using pip within the Conda environment
    print("Installing the package...")
    subprocess.check_call([pip_executable, "install", repo_dir])
    print("Package installed.")

    # Clean up
    shutil.rmtree(extract_dir)
    os.remove(zip_file)
    print("Temporary files removed.")


def download_and_extract_dependency(env_dir, file_url):
    """
    Download and extract the LAMMPS+MPI dependency, placing binaries in the specified Conda environment.

    Parameters:
        env_dir (str): Path to the Conda environment where binaries will be placed.
        file_url (str): URL to the dependency file.
    """
    print(f"Downloading dependency from {file_url}...")
    local_file = "lammps_mpi.zip" if file_url.endswith(".zip") else "lammps_mpi.tar.xz"

    urllib.request.urlretrieve(file_url, local_file)
    print("Dependency downloaded.")

    # Determine the Scripts or bin directory
    scripts_dir = (
        os.path.join(env_dir, "bin")
        if os.name != "nt"
        else os.path.join(env_dir, "Scripts")
    )
    os.makedirs(scripts_dir, exist_ok=True)

    # Extract and place binaries in the Scripts or bin directory
    if local_file.endswith(".zip"):
        extract_zip(local_file, scripts_dir)
    else:
        extract_tar_xz(local_file, scripts_dir)

    # Clean up the downloaded file
    os.remove(local_file)
    print("Temporary files removed.")


def extract_zip(zip_file, target_dir):
    """
    Extract and flatten a .zip file.

    Parameters:
        zip_file (str): Path to the ZIP file to extract.
        target_dir (str): Directory where the extracted files will be placed.
    """
    print(f"Extracting {zip_file}...")
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        for member in zip_ref.namelist():
            filename = os.path.basename(member)
            if filename:  # Only process files, skip directories
                with zip_ref.open(member) as source:
                    target_path = os.path.join(target_dir, filename)
                    with open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
    print(f"{zip_file} extracted to {target_dir}.")


def extract_tar_xz(tar_file, target_dir):
    """
    Extract a .tar.xz file.

    Parameters:
        tar_file (str): Path to the tar.xz file to extract.
        target_dir (str): Directory where the extracted files will be placed.
    """
    print(f"Extracting {tar_file}...")
    with tarfile.open(tar_file, "r:xz") as tar_ref:
        tar_ref.extractall(path=target_dir)
    print(f"{tar_file} extracted to {target_dir}.")


def create_activation_script(env_dir, script_dir):
    """
    Create a script to activate the environment and run Scymol.

    Parameters:
        env_dir (str): Path to the Conda environment.
        script_dir (str): Directory where the activation script will be created.
    """
    script_name = "run_scymol.bat" if os.name == "nt" else "run_scymol.sh"
    script_path = os.path.join(script_dir, script_name)

    with open(script_path, "w") as script_file:
        if os.name == "nt":
            script_file.write(f"@echo off\n")
            script_file.write(f"CALL activate.bat {env_dir}\n")
            script_file.write(f"scymol\n")
        else:
            script_file.write(f"#!/bin/bash\n")
            script_file.write(f"source activate {env_dir}\n")
            script_file.write(f"scymol\n")

    if os.name != "nt":
        os.chmod(script_path, 0o755)  # Make script executable on Unix-based systems
    print(f"Activation script created at {script_path}.")


def get_dependency_url():
    """
    Get the appropriate dependency URL based on the operating system.

    Returns:
        str: URL to the dependency file.
    """
    if os.name == "nt":
        return "https://github.com/eli-ams/raw/refs/heads/master/distributables/lammps+mpi_win64.zip"
    else:
        return "https://github.com/eli-ams/scymol/raw/refs/heads/master/distributables/lammps+mpi_ubuntu64.tar.xz"


def main():
    """
    Main function to create Conda environment, install Scymol, and handle dependencies.
    """
    parser = argparse.ArgumentParser(description="Setup and run Scymol with Conda.")
    parser.add_argument(
        "--mpi-lammps", action="store_true", help="Install LAMMPS and MPI."
    )
    parser.add_argument(
        "--no-scymol", action="store_true", help="Skip Scymol installation."
    )
    # parser.add_argument("--env-name", type=str, required=True, help="Specify the name of the Conda environment.")
    args = parser.parse_args()

    # Define environment directory
    env_dir = os.path.abspath(os.path.join(os.getcwd(), "scymol"))

    # Define dependencies
    dependencies = ["python=3.10", "pip"]
    if args.mpi_lammps and os.name != "nt":
        dependencies += ["lammps", "openmpi"]

    # URLs for the Scymol package and dependencies
    zip_url = "https://github.com/eli-ams/scymol/archive/refs/heads/master.zip"
    file_url = get_dependency_url()

    try:
        # Step 1: Create the Conda environment
        create_conda_environment(env_dir, dependencies)

        # Step 2: Install Scymol unless --no-scymol is specified
        if not args.no_scymol:
            install_package_from_github(env_dir, zip_url)

        # Step 3: Install LAMMPS+MPI binaries if requested
        if args.mpi_lammps and os.name == "nt":
            download_and_extract_dependency(env_dir, file_url)

        # Step 4: Create an activation script
        create_activation_script(env_dir, os.getcwd())

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
