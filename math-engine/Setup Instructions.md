# 1.1: Use f2py (numpy) to compile fortran code
## Compile the fortran module  (THIS IS DONE BY DOCKERFILE)
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

# 1.2: Using the Fortran module in Python
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

# GitLab CI/CD
For the **variables**:
Project > Settings > CI/CD > Project Variables > CI/CD Variables > Add variable
Variables such as: AWS_ACCESS_KEY_ID, AWS_DEFAULT_REGION, AWS_SECRET_ACCESS_KEY
See: 
- https://docs.gitlab.com/ci/cloud_deployment/ 
- https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html 

User will require **permissions** for pushing & pulling images. 
Go to IAM > Users > Select user > Add permissions > Attatch policy.
(Easiest policy is AmazonEC2ContainerRegistryPowerUser).


To run .gitlab-ci.yml, psh the branch to the GitLab project. It will detect the file and automatically trigger the pipeline. 
- .gitlab-ci.yml should be under root directory. 
'''
git add .gitlab-ci.yml
git commit -m "Add CI pipeline (and blah blah)"
git push origin main
'''
GitLab Validation
- Project > Build > Pipelines on the left sidebar.
- Click the Status icon (Running/Passed) of the latest commit.
- Click the build_image job to see the logs.
- Verify you see "Build Complete!" at the end.


Local check:
``aws configure``
(grab access keys: https://dovzji14roepy.cloudfront.net/ > Login to Account > Access keys)

'''
aws ecr get-login-password --region us-west-2 \
| docker login \
--username AWS \
--password-stdin 123456789012.dkr.ecr.us-west-2.amazonaws.com
'''
