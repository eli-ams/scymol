import os
import subprocess
import urllib.request
import zipfile
import argparse
import shutil


def create_conda_environment(env_name, dependencies):
    """Create a Conda environment with the specified dependencies."""
    print(f"Creating Conda environment '{env_name}' with custom channels...")
    channels = ["-c", "conda-forge", "-c", "defaults", "-c", "anaconda", "-c", "numba"]
    subprocess.check_call(["conda", "create", "--name", env_name, "-y"] + channels + dependencies)
    print(f"Conda environment '{env_name}' created.")


def install_package_from_github(env_name, zip_url):
    """Install the Scymol package from a GitHub ZIP file."""
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

    # Install the package using pip within the Conda environment
    print("Installing the package...")
    subprocess.check_call(["conda", "run", "--name", env_name, "pip", "install", repo_dir])
    print("Package installed.")

    # Clean up
    shutil.rmtree(extract_dir)
    os.remove(zip_file)
    print("Temporary files removed.")


def download_and_extract_dependency(env_name, file_url):
    """Download and extract the LAMMPS+MPI dependency, placing binaries in the Conda environment."""
    print(f"Downloading dependency from {file_url}...")
    local_file = "lammps_mpi.zip" if file_url.endswith(".zip") else "lammps_mpi.tar.xz"

    urllib.request.urlretrieve(file_url, local_file)
    print("Dependency downloaded.")

    # Determine the Conda environment's Scripts directory
    env_path = subprocess.check_output(["conda", "info", "--envs"]).decode()
    env_dir = [
        line.split()[0] for line in env_path.splitlines() if env_name in line
    ][0]
    scripts_dir = os.path.join(env_dir, "Scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    # Extract and place binaries in the Scripts directory
    if local_file.endswith(".zip"):
        extract_zip(local_file, scripts_dir)
    else:
        extract_tar_xz(local_file, scripts_dir)

    # Clean up the downloaded file
    os.remove(local_file)
    print("Temporary files removed.")


def extract_zip(zip_file, target_dir):
    """Extract and flatten a .zip file."""
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
    """Extract a .tar.xz file."""
    print(f"Extracting {tar_file}...")
    with tarfile.open(tar_file, "r:xz") as tar_ref:
        tar_ref.extractall(path=target_dir)
    print(f"{tar_file} extracted to {target_dir}.")


def get_conda_base():
    """Dynamically get the base directory of Conda."""
    try:
        # Run `conda info --base` to get the base path
        conda_base = subprocess.check_output(["conda", "info", "--base"], universal_newlines=True).strip()
        return conda_base
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Failed to determine Conda base directory. Is Conda installed and in your PATH?") from e

def create_activation_script(env_name, script_dir):
    """Create a script to activate the environment and run Scymol."""
    conda_base = get_conda_base()  # Dynamically find Conda base directory
    script_name = "run_scymol.bat" if os.name == "nt" else "run_scymol.sh"
    script_path = os.path.join(script_dir, script_name)

    with open(script_path, "w") as script_file:
        if os.name == "nt":
            script_file.write(f"@echo off\n")
            script_file.write(f"CALL {os.path.join(conda_base, 'condabin', 'conda.bat')} activate {env_name}\n")
            script_file.write(f"scymol\n")
        else:
            script_file.write(f"#!/bin/bash\n")
            # Source the Conda initialization script
            script_file.write(f"source {os.path.join(conda_base, 'etc', 'profile.d', 'conda.sh')}\n")
            script_file.write(f"conda activate {env_name}\n")
            script_file.write(f"scymol\n")

    if os.name != "nt":
        os.chmod(script_path, 0o755)  # Make script executable on Unix-based systems
    print(f"Activation script created at {script_path}.")



def get_dependency_url():
    """Get the appropriate dependency URL based on the operating system."""
    if os.name == "nt":
        return "https://github.com/eli-ams/scymol/raw/refs/heads/master/distributables/lammps+mpi_win64.zip"
    else:
        return "https://github.com/eli-ams/scymol/raw/refs/heads/master/distributables/lammps+mpi_ubuntu64.tar.xz"


def main():
    """Main function to create Conda environment, install Scymol, and handle dependencies."""
    parser = argparse.ArgumentParser(description="Setup and run Scymol with Conda.")
    parser.add_argument("--mpi-lammps", action="store_true", help="Install LAMMPS and MPI.")
    parser.add_argument("--no-scymol", action="store_true", help="Skip Scymol installation.")
    parser.add_argument("--env-name", type=str, required=True, help="Specify the name of the Conda environment.")
    args = parser.parse_args()

    # Get environment name from the argument
    env_name = args.env_name

    # Define dependencies
    dependencies = ["python=3.10", "pip"]

    if args.mpi_lammps and os.name != "nt":
        dependencies += ["lammps", "openmpi"]

    # URLs for the Scymol package and dependencies
    zip_url = "https://github.com/eli-ams/scymol/archive/refs/heads/master.zip"
    file_url = get_dependency_url()

    try:
        # Step 1: Create the Conda environment
        create_conda_environment(env_name, dependencies)

        # Step 2: Install Scymol unless --no-scymol is specified
        if not args.no_scymol:
            install_package_from_github(env_name, zip_url)

        # Step 3: Install LAMMPS+MPI binaries if requested and on Windows
        if args.mpi_lammps and os.name == "nt":
            download_and_extract_dependency(env_name, file_url)

        # Step 4: Create an activation script
        create_activation_script(env_name, os.getcwd())

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()




if __name__ == "__main__":
    main()
