# 1.1: Use f2py (numpy) to compile fortran code
## Use conda
Conda simplifies managing Python versions, NumPy and Fortran compilers. 

First check that conda is available: ``conda --version``

If Anaconda is installed but ``conda`` is not found in the shell, 
activate the conda base environment first:
- ``source ~/anaconda3/etc/profile.d/conda.sh``
- ``conda activate``

Create the environment: 
- ``conda create -n schrodinger python=3.10 numpy -y``
- ``conda activate schrodinger``

Install the Fortran compiler and f2py: ``conda install -c conda-forge numpy f2py gfortran -y``
Check the GNU Fortran compiler: ``gfortran --version``

## Compile the fortran module 
NOTE: Even in Python 3.11, f2py on Windows is still tries to load MSVCCompiler first. This is a Windows & numpy.distutils issue, and f2py currently cannot fully bypass the MSVC backend when building. So **if you're on Windows, use WSL for compilation.** (Can use an AWS Linux instance but no need really).
- ``wsl``
- ``sudo apt update``
- ``sudo apt install meson ninja-build gfortran python3-numpy python3-dev -y`` 

- First switch to the correct folder: ``cd math-engine``
- Compile with f2py. Force it to use the GNU Fortran compiler (gfortran) so it doesn't try to use MSVC:
    ``python -m numpy.f2py -c -m schrodinger_mod schrodinger.f90 --fcompiler=gnu95``
    - You may need to exchange ``python`` with ``python3``. 

This will generate a Python-importable module:
- Windows: schrodinger_mod.cp310-win_amd64.pyd
- Linux/macOS: schrodinger_mod.cpython-310-x86_64-linux-gnu.so

# Using the Fortran module in Python
The module can be imported into python with: ``import schrodinger_mod``

As the Fortran kernel doesn't currently support computing partial grids (expects size_n*size_n grid), 
have each worker compute the entire grid at different time steps 
(instead trying to have each worker compute a partition - though boxes might work).

**NOTES:** 
- Despite what you see in the Fortran signature is, f2py often reorders arguments so arrays appear first
    because it needs the array shape before scalar parameters. You may need to swap the paramters. 
    Additionally, the wrapper may interprete positional arguments in a different oder than expected. 
    Make your life easy and use keyword arguments. Ex: ``(matrix=matrix, size_n=grid_size, num_steps=job_index, h_bar=H_BAR, mass=MASS)``. 
- Fortran stores arrays in column-major order, while NumPy by default creates arrays in row-major order (C order).
    For the memory layout to match what Fortran expects, set the ``order="F"`` flag when initializing the input matrix.
