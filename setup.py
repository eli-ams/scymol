from setuptools import setup, find_packages

setup(
    name="scymol",
    version="1.0.0",
    author="Eli I. Assaf",
    author_email="eli.ams@utexas.edu",
    description="A PyQt5-based software for molecular simulations using LAMMPS.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/eli-ams/scymol",
    license="GNU General Public License v3 (GPLv3)",  # Specify the correct license here
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",  # Correct classifier
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
    packages=find_packages(),
    install_requires=[
        "PyQt5",
        "numpy",
        "scipy",
        "matplotlib",
        "psutil",
        "sobol_seq",
        "numba",
        "rdkit",
        "file_read_backwards",
        "pysimm @ https://github.com/polysimtools/pysimm/archive/refs/heads/stable.zip"
    ],
    package_data={
        "scymol": [
            "frontend/uis/*",
            "frontend/lammps_flowchart_window/dialog_windows/*",  # Include all files in the 'frontend/uis/' directory
            "front2back/temp_files/*",
            "front2back/temp_files/dummy_lammps_simulation/*",
            "output/1/**/*",
            "LICENSE",
        ],
    },
    entry_points={
        "console_scripts": [
            "scymol = scymol.main:main"  # Replace with the function you want to call
        ],
    },
)
