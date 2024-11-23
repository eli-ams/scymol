import os
import shutil
import venv
import zipfile
import sys
import subprocess
from urllib.request import urlopen
from io import BytesIO

def create_shortcut(link_name, target, scymol_dir="scymol"):
    """
    Creates a shortcut in the current directory pointing to the target.

    :param link_name: Name of the shortcut to be created.
    :param target: Target command to execute.
    """
    current_dir = os.getcwd()

    if os.name == "posix":
        # For Unix-like systems (Linux, macOS)
        script_filename = "run_app.sh"
        script_path = os.path.join(current_dir, script_filename)
        with open(script_path, "w") as file:
            file.write("#!/bin/bash\n")
            file.write(f"cd {os.path.join(current_dir, scymol_dir)}\n")
            file.write(f"{target}\n")
        os.chmod(script_path, 0o755)  # Make the script executable

    elif os.name == "nt":
        # For Windows
        script_filename = "run_app.bat"
        script_path = os.path.join(current_dir, script_filename)
        with open(script_path, "w") as file:
            file.write(f"@echo off\n")
            file.write(f"cd {os.path.join(current_dir, scymol_dir)}\n")
            file.write(target.replace("/", "\\") + "\n")

def get_executable_path(env_dir, executable):
    """Returns the path to the executable within the virtual environment."""
    if os.name == "nt":  # Windows
        return os.path.join(env_dir, "Scripts", executable + ".exe")
    else:  # Unix-like platforms (Linux, macOS)
        return os.path.join(env_dir, "bin", executable)

def download_github_repo_as_zip(repo_url, branch, target_dir):
    """
    Downloads a GitHub repository as a ZIP file and extracts its contents.

    :param repo_url: URL of the GitHub repository (e.g., 'https://github.com/eli-ams/scymol').
    :param branch: Branch to download from (e.g., 'master').
    :param target_dir: Directory where the repository contents should be extracted.
    """
    repo_name = repo_url.split('/')[-1]
    zip_url = f"{repo_url}/archive/{branch}.zip"
    absolute_target_dir = os.path.abspath(target_dir)

    try:
        print(f"Downloading repository archive from {zip_url}...")
        with urlopen(zip_url) as response:
            zip_data = BytesIO(response.read())

        print(f"Extracting repository contents to '{absolute_target_dir}'...")
        with zipfile.ZipFile(zip_data) as zip_ref:
            zip_ref.extractall(absolute_target_dir)

        # Move the extracted files to the correct location
        extracted_dir = os.path.join(absolute_target_dir, f"{repo_name}-{branch}")
        for item in os.listdir(extracted_dir):
            shutil.move(os.path.join(extracted_dir, item), absolute_target_dir)
        shutil.rmtree(extracted_dir)  # Clean up intermediate directory

        print(f"Repository downloaded and extracted to '{absolute_target_dir}'.")

    except Exception as e:
        print(f"Error: Failed to download or extract the repository. {e}")
        sys.exit(1)

def extract_lammps_binaries(scymol_dir):
    """
    Extracts LAMMPS+MPI binaries for Windows or Linux based on the OS.

    :param scymol_dir: Base directory where the binaries should be extracted.
    """
    # Define the distributables directory and target path for extraction
    distributables_dir = os.path.join(scymol_dir, "distributables")
    target_dir = os.path.join(scymol_dir, "lammps+mpi")

    if not os.path.exists(distributables_dir):
        print(f"Error: Distributables directory '{distributables_dir}' not found.")
        sys.exit(1)

    # Select the correct archive based on the OS
    if os.name == "nt":  # Windows
        archive_name = "lammps+mpi_win64.zip"
    elif os.name == "posix":  # Linux
        archive_name = "lammps+mpi_ubuntu.zip"
    else:
        print("Unsupported operating system.")
        sys.exit(1)

    archive_path = os.path.join(distributables_dir, archive_name)

    if not os.path.exists(archive_path):
        print(f"Error: Archive '{archive_path}' not found.")
        sys.exit(1)

    # Extract the archive
    try:
        print(f"Extracting '{archive_name}' to '{target_dir}'...")
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        print(f"Extraction complete. Binaries are available in '{target_dir}'.")
    except Exception as e:
        print(f"Error: Failed to extract '{archive_path}'. {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Define the GitHub repository URL and branch
    repo_url = "https://github.com/eli-ams/scymol"
    branch = "master"
    scymol_dir = os.path.abspath("scymol/")  # Use absolute path for robustness

    # Download and extract the repository as a ZIP file
    if os.path.exists(scymol_dir):
        shutil.rmtree(scymol_dir)
    download_github_repo_as_zip(repo_url, branch, scymol_dir)

    # Define the virtual environment directory
    venv_dir = os.path.join(scymol_dir, "venv")

    # Create the virtual environment if it doesn't exist
    if not os.path.exists(venv_dir):
        print(f"Creating virtual environment in '{venv_dir}'...")
        venv.create(venv_dir, with_pip=True)

    # Paths to the Python executable in the virtual environment
    python_executable = get_executable_path(venv_dir, "python")

    # Upgrade pip to the latest version
    print("Upgrading pip...")
    subprocess.run([python_executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)

    # Install the project using the setup.py file
    print("Installing the Scymol project...")
    subprocess.run([python_executable, "-m", "pip", "install", "."], cwd=scymol_dir, check=True)

    # Extract LAMMPS/MPI binaries based on the operating system
    extract_lammps_binaries(scymol_dir)

    # Create a shortcut to run the application
    print("Creating Scymol's shortcuts...")

    if os.name == "posix":
        create_shortcut(
            link_name="scymol.sh",
            target=f"{python_executable} main.py",
            scymol_dir=scymol_dir,
        )
    elif os.name == "nt":
        create_shortcut(
            link_name="scymol.bat",
            target=f"venv\\Scripts\\python main.py",
            scymol_dir=scymol_dir,
        )

    print("Setup complete.")