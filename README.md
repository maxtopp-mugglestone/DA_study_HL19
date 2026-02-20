# Dynamics aperture study template

This repository contains a template that allows users to compute the dynamics aperture of a collider
under different parametric scenarios.

Jobs can be efficiently stored and parallelized using the
[Tree Maker](https://github.com/xsuite/tree_maker) package, while collider generation and particle tracking harness the power of [XSuite](https://github.com/xsuite/xsuite).

ℹ️ If you do not need to do large parametric scans, this repository is probably not what you're looking for.

## Installation instructions

### Cloning the repository and its submodules

Run the following command to clone the repository and all the relevant submodules:

```bash
git clone --recurse-submodules https://github.com/xsuite/example_DA_study.git
```

If you missed this step and clone the repository without the submodules, you can do _a posteriori_:

```bash
git submodule update --init --recursive
```
### Python installation

1) You can create a miniforge environment, look for instructions: https://github.com/conda-forge/miniforge.
Or use:
```
cd
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b  -p ./miniforge -f
rm -f Miniforge3-Linux-x86_64.sh
source miniforge/bin/activate
```

4) In the example_DA_study repository there is a file requirements.txt 

Manual packages installation:

```bash
pip install -r requirements.txt
```

3) Then we need to zip the envirnment for easier transfer later to the nodes.
Use:
```bash
pip install conda-pack
conda-pack miniforge envs.tar.gz (The name of the folder where your environment is stored. If you are using eos store it there! NOT on AFS please!)
```

Then you should be set.

### Paths modification

In the repository studies/scripts/ you need to modify the config.yaml. 

```
"root":
  setup_env_script: "none"
  # Following parameter is ignored when run_on is not htc_docker or slurm_docker
  singularity_image: "/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cdroin/da-study-docker:74ed75ec"
  # use_eos_for_large_files: true
  eos_python: "root://eosuser.cern.ch//eos/user/a/aradosla/envs/envs.tar.gz" # PUT YOUR python path
  generations:
    1: # Build the particle distribution and base collider
      job_folder: "../../template_jobs/1_build_distr_and_collider"
      job_executable: 1_build_distr_and_collider.py
      files_to_clone: # relative to the template folder
        - optics_specific_tools.py
      files_to_copy_node:
        - 1_build_distr_and_collider.py
        - config.yaml
        - optics_specific_tools.py
        - "/afs/cern.ch/work/a/aradosla/private/example_DA_study_50Hz/studies/optics/optics.zip"  # Generally you need a zipped optics.zip, in the current setup you can remove this line. The optics files are in: /afs/cern.ch/eng/lhc/optics/runIII/RunIII_dev/Proton_2025/NomH_RPV/opticsfile.46 for example.
      files_to_return:
        - collider.json.zip
        - output_python.txt
        - error_python.txt
        - tree_maker.json
        - tree_maker.log
        - particles
        - config_gen1.yaml
      run_on: "htc" # "local_pc" 'htc_docker' #'htc' #'slurm' #'slurm_docker'
      context: "cpu" # 'cupy' # opencl # how to run the simulation
      # Following parameter is ignored when run_on is not htc or htc_docker
      htc_job_flavor: "microcentury" # optional parameter to define job flavor, default is espresso
    2: # Launch the pymask and prepare the colliders
      job_folder: "../../template_jobs/2_configure_and_track"
      job_executable: 2_configure_and_track.py # has to be a python file
      files_to_clone:
        - misc.py
      files_to_copy_node:
        - 2_configure_and_track.py
        - config.yaml
        - misc.py
        - "/afs/cern.ch/work/a/aradosla/private/runIII_2025/studies/filling_scheme" # change with  ../../../../filling_scheme
        - "../config_gen1.yaml"
        - "../collider.json.zip"
        - "../particles"
      files_to_return:
        - output_particles.parquet
        - output_python.txt
        - error_python.txt
        - tree_maker.json
        - tree_maker.log
        - config_final.yaml
      context: "cpu" # 'cupy' # opencl # how to run the simulation
      run_on: "htc" # 'local_pc' # 'htc_docker' #'htc' #'slurm' #'slurm_docker'
      # Following parameter is ignored when run_on is not htc or htc_docker
      htc_job_flavor: "tomorrow" # optional parameter to define job flavor, default is espresso

```

## Running the study

- Change the parameters in studies/scripts/1_create_study.py

1) Inside you have the optics, octupoles, tunes etc. You can run tune scans for example by changing
```
array_qx = np.round(np.arange(62.305, 62.330, 0.001), decimals=4)
array_qy = np.round(np.arange(60.305, 60.330, 0.001), decimals=4)
```
2) Then you run this script and it will create folders in studies/scan/example_tunescan/base_collider/
There are multiple jobs with mutated configs with some of the tunes you want to scan.

3) Now we can launch the study. We need to run Run studies/scripts/2_run_jobs.py two times!
   It constists of 2 generations: The first launch is going to build the basic collider that will be stored in the folder studies/scan/example_tunescan/base_collider/. After it is completed, run studies/scripts 2_run_jobs.py again! This launches the second generation and the real study.

4) The output_particles.parquet file is the result of studies/scripts 2_run_jobs.py running properly stored in studies/scan/example_tunescan/base_collider/xtrack_0000 - xtrack_9999.
Some jobs are not going to run and it is normal! The tunes or in general parameters in that region are not stable and no result is produced. Simply ignore.

5) In order to get the DA result we need to process the results: run studies/scripts 3_postprocessing.py.
   It creates a da.parquet in the studies/scan/example_tunescan/

6) Plot the results example DA vs tune: folder my_scripts contains a DA_plot.py.


UNTIL HERE
### Installing with Poetry SKIP THIS IF YOU INSTALL WITHOUT POETRY!

If not already done, install Poetry following the tutorial [here](https://python-poetry.org/docs/). Note that Poetry must have access to Python 3.9 or above for the rest of the tutorial to work. More importantly, the executable of Python must be accessible from a cluster node (e.g. located on AFS when submitting jobs to HTCondor) for a submission to work. Ideally, Poetry should use a Python distribution located on your local machine (shared acress all of your projects), and then use another Python distribution (e.g. miniforge or miniconda) on AFS for the simulations (which can be shared across projects or not, depending on the needs).

You can check the base executable of Python that Poetry is using by running the following command:

```bash
poetry env info
```

If needed (for instance, if your Python base executable is not on AFS), you can change the exectutable with e.g:

```bash
poetry env use /path/to/python
```

For easier submission later, also impose the virtual environment to be created in the repository folder by running the following command:

```bash
poetry config virtualenvs.in-project true
```

If you're not interested in using GPUs, you can jump directly to the [Installing packages](#installing-packages) section. Otherwise, follow the next section.

### Installing with Poetry for GPUs

Using Poetry along with GPUs is a bit more complicated, as conda is not natively supported by Poetry. However, not all is lost as a simple trick allows to bypass this issue. First, from your (hopefully conda-compatible) Python environment, create a virtual environment with the following command:

```bash
conda create -n gpusim python=3.9
conda activate gpusim
```

⚠️ **Make sure that the Python version is 3.9 as, for now, a bug with Poetry prevents using 3.10 or above.**

Now configure Poetry to use the virtual environment you just created:
  
```bash
poetry config virtualenvs.in-project false
poetry config virtualenvs.path $CONDA_ENV_PATH
poetry config virtualenvs.create false
```

Where ```$CONDA_ENV_PATH``` is the path to the base envs folder (e.g. ```/home/user/miniforge3/envs```).  

You can then install the CUDA toolkit and the necessary packages (e.g. ```cupy```) in the virtual environment (from [Xsuite documentation](https://xsuite.readthedocs.io/en/latest/installation.html#gpu-multithreading-support) ):

```bash
conda install mamba -n base -c conda-forge
mamba install cudatoolkit=11.8.0
```

Finally, you need to modify the path to the virtual environment in the ```source_python.sh``` file. 

Replace the line 17 ```source $SCRIPT_DIR/.venv/bin/activate``` with the path to the conda environment you just used to create the virtual environment (e.g. ```source /home/user/miniforge3/bin/activate```, and add below ```conda activate gpusim```).

You're now good to go with the next section, as Poetry will automatically detect that the conda virtual environment is activated and use it to install the packages.

### Installing packages

Finally, install the dependencies by running the following command:

```bash
poetry install
```

At this point, ensure that a `.venv` folder has been created in the repository folder (except if you modified the procedure to use GPUs, as explained above). If not, follow the fix described in the next section.

Finally, you can make xsuite faster by precompiling the kernel, with:

```bash
poetry run xsuite-prebuild regenerate
```

To run any subsequent Python command, either activate the virtual environment (activate a shell within Poetry) with:

```bash
poetry shell
```

or run the command directly with Poetry:

```bash
poetry run python my_script.py
```

### Fix the virtual environment path

If, for some reason, your virtual environment is not in a `.venv`folder inside of your repository, you will have to
update the submitting script to point to the correct virtual environment. To that end, run the following command:

```bash
poetry env list --full-path
```

Identify the virtual environment that is being used and copy the corresponding path. Now, open the file `source_python.sh` and replace the line `source $SCRIPT_DIR/.venv/bin/activate`with the path to the virtual environment you just found (e.g. `source /path/to/your/virtual/environment/bin/activate`).



## Running a simple parameter scan simulation

This section introduces the basic steps to run a simple parameter scan simulation. The simulation consists in tracking a set of particles for a given number of turns, and computing the dynamics aperture for each particle. To get a more refined understanding of what the scripts used below are actually doing, please check the section [What happens under the hood](#what-happens-under-the-hood).

### Setting up the study

You can select the range of parameters you want to scan by editing the ```studies/scripts/1_create_study.py``` script, under the section ```Machine parameters being scanned```. For example, you can edit the following lines to do a tune scan of your liking (here, only the first 6 tunes are selected, in order not to create too many jobs):

```python
array_qx = np.round(np.arange(62.305, 62.330, 0.001), decimals=4)[:6]
array_qy = np.round(np.arange(60.305, 60.330, 0.001), decimals=4)[:6]
```

Note that, if the parameter ```only_keep_upper_triangle``` is set to True, most of the jobs in the grid defined above will be automatically skipped as the corresponding working points are too close to resonance, or are unreachable in the LHC.

In addition, since this is a toy simulation, you also want to keep a low number of turns simulated (e.g. 200 instead of 1000000):

```python
n_turns = 200
```

you can give the study you're doing the name of your choice by editing the following line:

```python
study_name = "example_tunescan"
```

### Building the tree

You are now ready to create the folder structure (the _tree_) of your study. The tree structure can be checked in ```studies/scripts/config.yaml```. As you can see, there are only 2 generations here :

- the first generation generates the particles distribution and build a collider with just the optics (which we call "base collider" from now on).
- the second generation sets all the other collider parameters, including the ones that are being scanned, and tracks the particles for a given number of turns.

For now, you might want to keep the jobs running on your local machine, on the cpu, to ensure everything runs fine. To do so, ensure that in the file ```studies/scripts/config.yaml```, there is, for both generations:

```yaml
run_on: 'local_pc'
context: 'cpu'
```

If not already done, activate the conda environment:

```bash
poetry shell
```

Now, move to the master_study folder, and run to script to build the tree and write it on disk:

```bash
cd studies/scripts/
python 1_create_study.py
```

This should create a folder named after ```study_name``` in ```studies/scans```. This folder contains the tree structure of your study: the parent generation is in the subfolder ```base_collider```, while the subsequent children are in the ```xtrack_iiii```. The tree_maker ```.json``` and ```.log``` files are used by tree_maker to keep track of the jobs that have been run and the ones that are still to be run.

Each node of each generation contains a ```config.yaml``` file that contains the parameters used to run the corresponding job (e.g. the particle distributions parameters or the collider crossing-angle for the first generation, and, e.g. the tunes and number of turns simulated for the second generation).

You should be able to run each job individually by executing the following command in the corresponding folder:

```bash
source run.sh
```

Note that, to run without errors, children nodes will most likley need the files output by the parent nodes. Therefore, you should run the parent nodes first, and then the children nodes. However, this is all done automatically by the ```studies/scripts/2_run_jobs.py``` script (cf. upcoming section), such that running manually the ```run.sh``` should be done only for debugging purposes.

### Running the jobs

First, update the study name in ```studies/scripts/2_run_jobs.py```. You can now execute the script:

```bash
python 2_run_jobs.py
```

Here, this will run the first generation (```base_collider```), which consists of only one job (building the particles distribution and the base collider).

In a general way, once the script is finished running, executing it again will check that the jobs have been run successfully, and re-run the ones that failed. If no jobs have failed, it will run the jobs from the next generation. Therefore, executing it again should launch all the tracking jobs (several for each tune, as the particle distribution is split in several files).

⚠️ **If the generation of the simulation you're launching comprises many jobs, ensure that you're not running them on your local machine (i.e. you don't use ```run_on: 'local_pc'``` in ```studies/scripts/config.yaml```). Otherwise, as the jobs are run in parallel, you will most likely saturate the cores and/or the RAM of your machine.**

### Analyzing the results

Once all jobs of all generations have been computed, the results from the simulations can be gathered in a single dataframe by running the ```studies/scripts/3_postprocess.py``` script. First, make sure to update the study name in the script. Then, ensure that the jobs will be grouped by the variable that have been scanned (here, the tunes) by editing the following line:

```python
groupby = ["qx", "qy"]
```

Finally, run the script:

```bash
python 3_postprocess.py
```

This should output a parquet dataframe in ```studies/scans/study_name/```. This dataframe contains the results of the simulations (e.g. dynamics aperture for each tune), and can be used for further analysis. Note that, in the toy example above, since we simulate for a very small number of turns, the resulting dataframe will be empty as no particles will be lost during the simulation.

## What happens under the hood

The aim of this set of scripts is to run sets of simulations in a fast and automated way, while keeping the possibility to run each simulation individually.

### Tree structure

Since simulations all make use of the same base collider, the base collider only needs to be built once, as the optics is never "scanned". However, each simulation corresponds to a different set of parameters, meaning that the base collider needs to be tailored ("tuned") to each simulation. Therefore, the base collider will correspond to generation 1, and the subsequent tracking simulations with different parameters will correspond to generation 2.

This is described in the file ```studies/scripts/config.yaml```:

```yaml
'root':
  setup_env_script: 'none'
  generations:
    1: # Build the particle distribution and base collider
      job_folder: "../../template_jobs/1_build_distr_and_collider"
      job_executable: 1_build_distr_and_collider.py
      files_to_clone:
        - optics_specific_tools.py
      run_on: "local_pc"
      context: "cpu"
      # Following parameter is ignored when run_on is not htc or htc_docker
      htc_job_flavor: 'tomorrow'
      # Following parameter is ignored when run_on is not htc_docker or slurm_docker
      singularity_image: "/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cdroin/da-study-docker:7844a437"
      
    2: # Launch the pymask and prepare the colliders
      job_folder: "../../template_jobs/2_configure_and_track"
      job_executable: 2_configure_and_track.py
      files_to_clone:
        - misc.py
      run_on: "local_pc"
      context: "cpu"
      # Following parameter is ignored when run_on is not htc or htc_docker
      htc_job_flavor: 'tomorrow' 
      # Following parameter is ignored when run_on is not htc_docker or slurm_docker
      singularity_image: "/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cdroin/da-study-docker:7844a437"
  # Children will be added below in the script 001_make_folders.py
  children:
```

This file defines the structure of the tree of jobs, which python files must be called at each generation, with which parameters, with which python distribution, and on which machine/cluster. More precisely:

- ```setup_env_script``` is the path to the conda environment that will be used to run Python in the simulations. By default, is set to ```none```, but is updated by the ```1_create_study.py``` script to point to the conda environment.
- ```job_folder```: for each generation, this describes the folder containing the files used to run the simulation. There should be at least a python script, and a ```config.yaml``` file. The python script then reads the parameters of the currunt simulation in the ```config.yaml file```, and runs the simulation accordingly.
- ```job_executable```, this is the name of the python script that will be run at each generation.
- ```files_to_clone```: this is a list of files that will be copied from the ```job_folder``` to the simulation folder. This is useful to copy files that are common to all simulations.
- ```run_on```: this is the machine/cluster on which the simulations will be run. At the moment, the following options are available (see section [Using computing clusters](#using-computing-clusters) below for more details):
  - ```local_pc```: the simulations will be run on the local machine. This is useful when running small number of jobs, or debugging purposes.
  - ```htc```: the simulations will be run on the HTCondor cluster at CERN. This is useful to run large sets of simulations.
  - ```slurm```: the simulations will be run on the Slurm cluster at CNAF.INFN. This is useful to run large sets of simulations.
  - ```htc_docker```: the simulations will be run on the HTCondor cluster at CERN, using Docker images. This is useful to run large sets of simulations, and/or to ensure reproducibility.
  - ```slurm_docker```: the simulations will be run on the Slurm cluster at CNAF.INFN, using Docker images. This is useful to run large sets of simulations, and/or to ensure reproducibility.
- ```context```: this is the python distribution that will be used to run the simulations. At the moment, the following options are available:
  - ```cpu```: the simulations will be run on the CPU. This is the default option, and is useful when running simulations with small number of particles, or for debugging purposes.
  - ```cupy```: the simulations will be run on the GPU using CUDA. This is useful to run simulations with large number of particles (you need to have cupy installed), especially on HTCondor. However, note that simulations must use Docker when running on HTCondor with GPU.
  - ```opencl```: the simulations will be run on the GPU using OpenCL. This is useful to run simulations with large number of particles (you need to have pyopencl installed), especially on the Bologna cluster.
- ```htc_job_flavor```: this is an optional parameter that can be used to define the job flavor on HTCondor. Long jobs (>8h, <24h) should most likely use ```tomorrow```. See all flavours [here](https://batchdocs.web.cern.ch/local/submit.html).
- ```singularity_image```: this is an optional parameter that can bmust be specified when running a simulation with ```htc_docker``` or ```slurm_docker```. This is useful to ensure reproducibility. See section [Using computing clusters](#using-computing-clusters) below for more details.
- ```children```: this is a list of children for each generation. More precisely, this contains the set of parameters used by each job of each generation. This is generated by the ```1_create_study.py``` script, and should not be modified manually.

To get a better idea of how this file is used, you can check the json mutated version at the root of each scan (i.e. ```studies/scans/study_name/tree_maker.json```).

Here, only two generations are used, but it is possible to add more generations if needed. For instance, if one wants to run intricated grid searches, e.g. check the dynamics aperture for each tune and each crossing angle, one could build the tree such that the tunes are scanned at generation 2, and the crossing angles at generation 3. However, this is not implemented yet, you will have to modify the scripts yourself.

### Overall pipeline

When doing a parameter scan, the following steps are performed:

1. Running the ```1_create_study.py``` script. This creates the folder structure for the simulations, and generate the ```config.yaml``` files for each simulation. It also generates the ```tree_maker.json``` file at each generation of the scan. In this file, the following parameters are set:
    - the base parameters for the collider, that is, the parameters of the collider that might be changed from one study to the other (e.g. optics being used), but that will be the same for all simulations of the study (parameters being scanned excluded).
    ⚠️ **It is possible that you need to update other collider parameters (e.g. ```on_a5```). In this case, you can either update directly the master configuration file in ```studies/template_jobs/1_build_distr_and_collider/config.yaml```, or adapt the ```1_create_study.py``` script to update the collider parameters you need.**
    - the parameters for the initial particles distribution. One parameter that is important here is ```n_split```, as it sets how much a given working point will be split into different simulations, each containing a subset of the inital particles distribution. That is, ```n_split``` is actually responsible to a large extent for the parallelization of the simulations.
  
    All these parameters are added to the root of the main configuration file (```studies/scans/study_name/config.yaml```). The tree_maker package then takes care of providing the right set of parameters to the right python file for each generation. In practice, the template jobs (located in ```studies/template_jobs```) are copied to the simulation folders, and the corresponding ```config.yaml``` (e.g. ```studies/template_jobs/1_build_distr_and_collider/config.yaml```) file is adapted (mutated) for each generation and each simulation, according to the main tree_maker configuration file, which has been generated at the same time as the simulation folders (e.g. in ```studies/scans/study_name/tree_maker.json```).

2. Running the ```2_run_jobs.py``` script. This script will run the simulations in parallel, and output a file (e.g. a collider json file, or a dataframe containing the result of the tracking) for each simulation. In practice, it calls each ```run.sh``` script in each simulation folder, which in turn calls the python script defined in the ```job_executable``` parameter of the ```studies/scripts/config.yaml``` file. The python script makes use of the proper set of parameters, set in the mutated ```config.yaml``` files (one per job, e.g. ```studies/scans/study_name/base_collider/xtrack_0001/config.yaml```).
3. Running the ```3_postprocess.py``` script. This script will analyse the results of the simulations, and output a summary dataframe at the root of the study.

### More information

More information, although possibly outdated, can be gathered from the explanations provided in previous versions of this repository, e.g. [in the previous README](https://github.com/xsuite/example_DA_study/blob/release/v0.1.1/README.md) and [the Tree Maker tutorial](https://github.com/xsuite/example_DA_study/blob/release/v0.1.1/tree_tutorial.md).

The code is now well formatted and well commented, such that any question should be relatively easily answered by looking at the code itself. If you have any question, do not hesitate to contact me (colas.noe.droin at cern.ch) or open an issue.

## Parameters that can be scanned

At the moment, all the collider parameters can be scanned without requiring extensive scripts modifications. This includes (but is not limited to):

- intensity (```num_particles_per_bunch```)
- crossing-angle (```on_x1, on_x5```)
- tune (```qx, qy```)
- chromaticity (```dqx, dqy```)
- octupole current (```i_oct_b1, i_oct_b2```)
- bunch being tracked (```i_bunch_b1, i_bunch_b2```)

At generation 1, the base collider is built with a default set of parameters for the optics (which are explicitely set in ```1_create_study.py```). At generation 2, the base collider is tailored to the parameters being scanned. That is, the tune and chroma are matched, the luminosity leveling is computed (if leveling is required), and the beam-beam lenses are configured.

It should be relatively easy to accomodate the scripts for other parameters. In addition, to prevent any complication, only the simulation of beam 1 is possible, but this should also be relatively easy to adapt.

## Using computing clusters

### General procedure

The scripts in the repository allows for an easy deployment of the simulations on HTCondor (CERN cluster) and Slurm (CNAF.INFN cluster). Please consult the corresponding tutorials ([here](https://abpcomputing.web.cern.ch/guides/htcondor/), and [here](https://abpcomputing.web.cern.ch/computing_resources/hpc_cnaf/)) to set up the clusters on your machine.

Once, this is done, jobs can be executed on HTCondor by setting ```run_on: 'htc'``` instead of ```run_on: 'local_pc'``` in ```studies/scripts/config.yaml```. Similarly, jobs can be executed on the CNAF cluster by setting ```run_on: 'slurm'```.

### Using Docker images

For reproducibility purposes and/or limiting the load on AFS or EOS drive, one can use Docker images to run the simulations. A registry of Docker images is available at ```/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/```, and some ready-to-use for DA simulations Docker images are available at ```/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cdroin/da-study-docker``` (for now, this is the default directory for images in the ```2_run_jobs.py``` file). To learn more about building Docker images and hosting them on the CERN registry, please consult the [corresponding tutorial](https://abpcomputing.web.cern.ch/guides/docker_on_htcondor/) abd the [corresponding repository](https://gitlab.cern.ch/unpacked/sync).

An repository containing a working Docker image with both HTCondor and Bologna is available [here](https://gitlab.cern.ch/cdroin/da-study-docker).

#### HTCondor

When running simulations on HTCondor, Docker images are be pulled directly from CVMFS through the submit file. No additional configuration is required, except for setting ```run_on: 'htc_docker'``` in ```studies/scripts/config.yaml```.

#### Slurm

Things are a bit tricker with Slurm, as the Docker image must first be manually pulled from CVMFS, and then loaded on the node after Singularity-ize it. The pulling of the image is only needed the first time, and can be done with e.g. (for the image ```cdroin/da-study-docker```):
  
  ```bash
  singularity pull docker://gitlab-registry.cern.ch/cdroin/da-study-docker:1afb04d3
  ```

However, due to unknown reason, only some nodes of INFN-CNAF will correctly execute this command. For instance, it didn't work on the default CPU CERN node (```hpc-201-11-01-a```), but it did on an alternative one (```hpc-201-11-02-a```). We recommand using either ```hpc-201-11-02-a``` or a GPU node (e.g. ```hpc-201-11-35```) to pull the image. Once the image is pulled, it will be accessible from any node.

For testing purposes, one can then run the image with Singularity directly on the node (not required):
  
  ```bash
  singularity run da-study-docker_1afb04d3.sif
  ```

In practice, the ```2_run_jobs.py``` script will take care of mouting the image and running it on the node with the correct miniforge distribution. All you have to do is change the ```run_on``` parameter in ```studies/scripts/config.yaml``` to ```run_on: 'slurm_docker'```.

⚠️ **The slurm docker scripts are a still experimental**. For instance, at the time of writing this documentation, symlinks path in the front-end node of INFN-CNAF are currently broken, meaning that some temporary fixs are implemented. This will hopefully be fixed in the future, and the fixs should not prevent the scripts from running anyway.

## Using GPUs

When simulating massive number of particles, using GPUs can prove to be very useful for speeding up the simulations. The use of GPUs should be as transparent as possible to the user, through the parameter ```context``` in ```studies/scripts/config.yaml```. As explained above, (default) CPU computations are performed with ```context: 'cpu'```, while GPU computations are performed with ```context: 'cupy'``` or ```context: 'opencl'```. The last two cases require the installation of the corresponding packages (```cupy``` or ```pyopencl```). When using GPUs on clusters, keep in mind that:

- HTCondor uses CUDA, and therefore requires ```context: 'cupy'```.
- Bologna uses OpenCL, and therefore requires ```context: 'opencl'```.

It is strongly advised to use a Docker image to run simulations on clusters (i.e. ```run_on: htc_docker```or ```run_on: slurm_docker```), as this will ensure reproducibility and avoid any issue with the installation of the packages. In addition, the Docker image will automatically mount the GPUs on the node, and the simulations will be run on the GPU without any additional configuration.

## License

This repository is licensed under the MIT license. Please refer to the [LICENSE](LICENSE) file for more information.
