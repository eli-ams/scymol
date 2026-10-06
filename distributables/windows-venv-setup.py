"""Install Scymol 2.0 into a private Windows virtual environment.

This bootstrapper intentionally uses only the Python standard library.  It
creates an isolated installation under the current user's Local AppData,
installs Scymol and its Python dependencies, installs the pinned PySIMM source
release, verifies and extracts the optional Windows LAMMPS/MPI bundle, and
creates launchers that expose those binaries only to Scymol.

Run with Python 3.10 or newer on 64-bit Windows::

    python windows-venv-setup.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import venv
import zipfile


SCYMOL_VERSION = "2.0.0"
PYSIMM_VERSION = "1.1"
PYSIMM_ARCHIVE = (
    "https://github.com/polysimtools/pysimm/archive/refs/tags/1.1.zip"
)
SCYMOL_ARCHIVE = (
    "https://github.com/eli-ams/scymol/archive/refs/tags/v2.0.0.zip"
)
LAMMPS_ARCHIVE = (
    "https://github.com/eli-ams/scymol/raw/refs/heads/master/"
    "distributables/lammps%2Bmpi_win64.zip"
)
LAMMPS_SHA256 = "af1ceb1f30cd409de055dfe2ddfe9255ad1b36ec8c8e5f68b59f6cc102e731c1"


class SetupError(RuntimeError):
    """A user-facing installation failure."""


def status(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    printable = subprocess.list2cmdline(command)
    print(f"    {printable}", flush=True)
    try:
        subprocess.run(command, check=True, env=env)
    except FileNotFoundError as exc:
        raise SetupError(f"Required program was not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise SetupError(
            f"Command failed with exit code {exc.returncode}: {printable}"
        ) from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Scymol-Installer/2.0"})
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open(
            "wb"
        ) as output:
            total = int(response.headers.get("Content-Length", "0") or 0)
            received = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                received += len(block)
                if total:
                    print(
                        f"\r    Downloaded {received / 1024 / 1024:.1f} of "
                        f"{total / 1024 / 1024:.1f} MiB",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\r    Downloaded {received / 1024 / 1024:.1f} MiB",
                        end="",
                        flush=True,
                    )
        print()
        temporary.replace(destination)
    except (OSError, urllib.error.URLError) as exc:
        temporary.unlink(missing_ok=True)
        raise SetupError(f"Could not download {url}: {exc}") from exc


def safe_extract(archive: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        members = package.infolist()
        if not members:
            raise SetupError(f"The downloaded archive is empty: {archive}")
        for member in members:
            target = (destination / member.filename).resolve()
            if target != destination_resolved and destination_resolved not in target.parents:
                raise SetupError(
                    f"Unsafe path in downloaded archive: {member.filename}"
                )
        package.extractall(destination)


def write_launchers(install_root: Path, venv_python: Path, binary_dir: Path) -> None:
    pythonw = venv_python.with_name("pythonw.exe")
    if not pythonw.is_file():
        pythonw = venv_python

    common = (
        "@echo off\n"
        "setlocal\n"
        f'set "PATH={binary_dir};%PATH%"\n'
    )
    gui = (
        common
        + f'"{pythonw}" -c "from scymol.app import main; raise SystemExit(main())" %*\n'
    )
    console = (
        common
        + f'"{venv_python}" -c "from scymol.app import main; raise SystemExit(main())" %*\n'
        + "if errorlevel 1 pause\n"
    )
    (install_root / "Scymol.bat").write_text(gui, encoding="utf-8", newline="\r\n")
    (install_root / "Scymol-console.bat").write_text(
        console, encoding="utf-8", newline="\r\n"
    )


def validate_windows() -> None:
    if sys.platform != "win32":
        raise SetupError("This installer is for 64-bit Windows only.")
    if sys.version_info < (3, 10):
        raise SetupError("Python 3.10 or newer is required.")
    if platform.architecture()[0] != "64bit":
        raise SetupError("A 64-bit Python installation is required.")


def install_lammps(script_dir: Path, install_root: Path) -> tuple[Path, Path]:
    local_archive = script_dir / "lammps+mpi_win64.zip"
    downloads = install_root / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    cached_archive = downloads / "lammps+mpi_win64.zip"

    if local_archive.is_file():
        archive = local_archive
        print(f"    Using repository bundle: {archive}")
    else:
        archive = cached_archive
        if not archive.is_file() or sha256(archive) != LAMMPS_SHA256:
            status("Downloading the Windows LAMMPS/MPI bundle")
            download(LAMMPS_ARCHIVE, archive)
        else:
            print(f"    Using verified cached bundle: {archive}")

    actual_hash = sha256(archive)
    if actual_hash != LAMMPS_SHA256:
        raise SetupError(
            "The LAMMPS/MPI archive failed SHA-256 verification.\n"
            f"Expected: {LAMMPS_SHA256}\n"
            f"Received: {actual_hash}"
        )

    binary_dir = install_root / "lammps-mpi"
    status("Extracting the verified Windows LAMMPS/MPI bundle")
    with tempfile.TemporaryDirectory(prefix="lammps-extract-", dir=install_root) as temp:
        staging = Path(temp)
        safe_extract(archive, staging)
        lammps = staging / "LAMMPS.exe"
        mpi = staging / "mpiexec.exe"
        if not lammps.is_file() or not mpi.is_file():
            raise SetupError(
                "The LAMMPS/MPI archive does not contain LAMMPS.exe and mpiexec.exe."
            )
        if binary_dir.exists():
            shutil.rmtree(binary_dir)
        shutil.copytree(staging, binary_dir)

    return binary_dir / "LAMMPS.exe", binary_dir / "mpiexec.exe"


def install_python_packages(venv_python: Path, script_dir: Path) -> str:
    pip = [str(venv_python), "-m", "pip"]
    status("Updating pip and build tools")
    run(pip + ["install", "--upgrade", "pip", "setuptools", "wheel"])

    status("Installing PySIMM 1.1 and its undeclared runtime dependencies")
    run(pip + ["install", "numpy>=1.24", "pandas", PYSIMM_ARCHIVE])

    project_dir = script_dir.parent
    local_project = project_dir / "pyproject.toml"
    if local_project.is_file() and (project_dir / "src" / "scymol").is_dir():
        status("Installing Scymol 2.0.0 from the local repository")
        run(pip + ["install", str(project_dir)])
        source = str(project_dir)
    else:
        status("Installing Scymol 2.0.0")
        try:
            run(pip + ["install", f"scymol=={SCYMOL_VERSION}"])
            source = f"PyPI scymol=={SCYMOL_VERSION}"
        except SetupError:
            print("    PyPI installation was unavailable; trying the tagged GitHub source.")
            run(pip + ["install", SCYMOL_ARCHIVE])
            source = SCYMOL_ARCHIVE

    status("Checking the installed Python packages")
    run(pip + ["check"])
    run(
        [
            str(venv_python),
            "-c",
            (
                "import scymol, pysimm; "
                f"assert scymol.__version__ == '{SCYMOL_VERSION}'; "
                "print('Scymol', scymol.__version__, 'and PySIMM imported successfully')"
            ),
        ]
    )
    return source


def validate_binaries(lammps: Path, mpi: Path, binary_dir: Path) -> None:
    child_env = os.environ.copy()
    child_env["PATH"] = str(binary_dir) + os.pathsep + child_env.get("PATH", "")

    status("Checking the bundled LAMMPS executable")
    run([str(lammps), "-help"], env=child_env)

    status("Checking local MPI execution")
    run(
        [str(mpi), "-localonly", "-n", "1", str(lammps), "-help"],
        env=child_env,
    )


def parse_arguments() -> argparse.Namespace:
    local_app_data = os.environ.get("LOCALAPPDATA")
    default_root = (
        Path(local_app_data) / "Scymol"
        if local_app_data
        else Path.home() / "AppData" / "Local" / "Scymol"
    )
    parser = argparse.ArgumentParser(
        description="Install Scymol 2.0 into a private Windows virtual environment."
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=default_root,
        help=f"installation directory (default: {default_root})",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="do not wait for Enter before closing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    try:
        validate_windows()
        script_dir = Path(__file__).resolve().parent
        install_root = args.install_dir.expanduser().resolve()
        install_root.mkdir(parents=True, exist_ok=True)

        print("Scymol 2.0 Windows installer")
        print(f"Installation directory: {install_root}")

        environment_dir = install_root / "venv"
        status("Creating the private Python virtual environment")
        venv.EnvBuilder(with_pip=True, clear=False).create(environment_dir)
        venv_python = environment_dir / "Scripts" / "python.exe"
        if not venv_python.is_file():
            raise SetupError("The virtual environment did not create python.exe.")

        source = install_python_packages(venv_python, script_dir)
        lammps, mpi = install_lammps(script_dir, install_root)
        validate_binaries(lammps, mpi, lammps.parent)
        write_launchers(install_root, venv_python, lammps.parent)

        manifest = {
            "scymol_version": SCYMOL_VERSION,
            "scymol_source": source,
            "pysimm_version": PYSIMM_VERSION,
            "python": str(venv_python),
            "lammps": str(lammps),
            "mpi": str(mpi),
            "lammps_archive_sha256": LAMMPS_SHA256,
        }
        (install_root / "installation.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        print("\nInstallation completed successfully.")
        print(f"Launch Scymol with: {install_root / 'Scymol.bat'}")
        print(
            "On first launch, open Tools -> LAMMPS execution setup and click "
            "Test and save. The local binaries will already be discoverable."
        )
        return 0
    except (SetupError, OSError, zipfile.BadZipFile) as exc:
        print(f"\nINSTALLATION FAILED\n{exc}", file=sys.stderr)
        return 1
    finally:
        if not args.no_pause and sys.stdin.isatty():
            try:
                input("\nPress Enter to close...")
            except EOFError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
