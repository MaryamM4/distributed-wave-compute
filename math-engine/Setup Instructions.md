# Setup Instructions
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
- ``sudo apt install python3-numpy python3-dev gfortran``
- You may need to exchange ``python`` with ``python3`` in following steps.  

- First switch to the correct folder: ``cd math-engine``
- Compile with f2py. Force it to use the GNU Fortran compiler (gfortran) so it doesn't try to use MSVC:
    ``python -m numpy.f2py -c -m schrodinger_mod schrodinger.f90 --fcompiler=gnu95``

This will generate a Python-importable module:
- Windows: schrodinger_mod.cp310-win_amd64.pyd
- Linux/macOS: schrodinger_mod.cpython-310-x86_64-linux-gnu.so

**The module can then be imported into python with: ``import schrodinger_mod``**
