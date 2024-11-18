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
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU GENERAL PUBLIC LICENSE",
        "Operating System :: OS Independent",
    ],
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
        "sigfig",
        "pysimm @ git+https://github.com/polysimtools/pysimm.git",  # Replace with actual URL and branch or commit
    ],
    entry_points={
        "console_scripts": [
            "scymol = scymol.main:main"  # Replace with the function you want to call
        ],
    },
)
