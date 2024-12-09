import os
import platform
import subprocess
import venv
import urllib.request
import zipfile
import tarfile
import shutil
import argparse

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
    pip_executable = os.path.join(venv_dir, "Scripts" if is_windows() else "bin", "pip" + (".exe" if is_windows() else ""))
    print("Installing the package...")
    subprocess.check_call([pip_executable, "install", repo_dir])
    print("Package installed.")

    # Clean up
    shutil.rmtree(extract_dir)
    os.remove(zip_file)
    print("Temporary files removed.")

def download_and_extract_dependency(venv_dir, file_url):
    """Download and extract the LAMMPS+MPI dependency, flattening the structure."""
    print(f"Downloading dependency from {file_url}...")
    is_zip = file_url.endswith(".zip")
    local_file = "lammps_mpi.zip" if is_zip else "lammps_mpi.tar.xz"

    urllib.request.urlretrieve(file_url, local_file)
    print("Dependency downloaded.")

    # Determine target directory
    target_dir = os.path.join(venv_dir, "Scripts" if is_windows() else "bin")
    os.makedirs(target_dir, exist_ok=True)

    if is_zip:
        extract_zip(local_file, target_dir)
    else:
        extract_tar_xz(local_file, target_dir)

    # Clean up the downloaded file
    os.remove(local_file)
    print("Temporary files removed.")

def extract_zip(zip_file, target_dir):
    """Extract and flatten a .zip file."""
    print(f"Extracting {zip_file}...")
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        for member in zip_ref.namelist():
            # Get the base name (file name only) to flatten the structure
            filename = os.path.basename(member)
            if filename:  # Only process files, skip directories
                source = zip_ref.open(member)
                target = open(os.path.join(target_dir, filename), "wb")
                with source, target:
                    shutil.copyfileobj(source, target)
    print(f"{zip_file} extracted to {target_dir}.")

def extract_tar_xz(tar_file, target_dir):
    """Extract a .tar.xz file preserving the original structure, symlinks, and permissions."""
    print(f"Extracting {tar_file}...")
    
    # Ensure the target directory exists
    os.makedirs(target_dir, exist_ok=True)
    
    # Open the tar file and extract all members
    with tarfile.open(tar_file, "r:xz") as tar_ref:
        tar_ref.extractall(path=target_dir)
    
    print(f"{tar_file} extracted to {target_dir} preserving symlinks and permissions.")

def create_activation_script(venv_dir, script_dir):
    """Create a .sh or .bat script to activate the environment and run scymol."""
    script_name = "run_scymol.bat" if is_windows() else "run_scymol.sh"
    script_path = os.path.join(script_dir, script_name)

    activate_cmd = os.path.join(venv_dir, "Scripts" if is_windows() else "bin", "activate")
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
    """Check if the operating system is Windows."""
    return os.name == "nt"

def get_dependency_url():
    """Get the appropriate dependency URL based on the operating system."""
    if is_windows():
        return "https://github.com/eli-ams/scymol/raw/refs/heads/master/distributables/lammps+mpi_win64.zip"
    else:
        return "https://github.com/eli-ams/scymol/raw/refs/heads/master/distributables/lammps+mpi_ubuntu64.tar.xz"

def main():
    """Main function to create venv, install package, and handle dependencies."""
    parser = argparse.ArgumentParser(description="Setup and run Scymol with optional dependencies.")
    parser.add_argument("--mpi-lammps", action="store_true", help="Download and install the LAMMPS+MPI dependency.")
    args = parser.parse_args()

    # Define the directory for the virtual environment
    venv_dir = os.path.join(os.getcwd(), "scymol", "venv")
    script_dir = os.getcwd()

    # URLs for the package and the dependency
    zip_url = "https://github.com/eli-ams/scymol/archive/refs/heads/master.zip"
    file_url = get_dependency_url()

    try:
        create_virtual_environment(venv_dir)
        download_and_install_package(venv_dir, zip_url)
        if args.mpi_lammps:
            download_and_extract_dependency(venv_dir, file_url)
        create_activation_script(venv_dir, script_dir)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
