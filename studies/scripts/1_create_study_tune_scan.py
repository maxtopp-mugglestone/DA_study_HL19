# ==================================================================================================
# --- Imports
# ==================================================================================================
import copy
import itertools
import os
import time

import numpy as np
import yaml
from generate_run_file import (
    generate_run_sh,
    generate_run_sh_htc,
)
from tree_maker import initialize

# ==================================================================================================
# --- Initial particle distribution parameters (generation 1)
#
# Below, the user defines the parameters for the initial particles distribution.
# Path for the particle distribution configuration:
# master_study/master_jobs/1_build_distr_and_collider/config.yaml [field config_particles]
# =================================name=================================================================

# Define dictionary for the initial particle distribution
d_config_particles = {}

# Radius of the initial particle distribution
d_config_particles["r_min"] = 4
d_config_particles["r_max"] = 8
d_config_particles["n_r"] = 2 * 16 * (d_config_particles["r_max"] - d_config_particles["r_min"])

# Number of angles for the initial particle distribution
d_config_particles["n_angles"] = 5

# Number of split for parallelization
d_config_particles["n_split"] = 5

# ==================================================================================================
d_config_collider = yaml.safe_load(open("config_collider.yaml"))
# ==================================================================================================
# ==================================================================================================
# --- Tracking parameters (generation 2)
#
# Below, the user defines the parameters for the tracking.
# ==================================================================================================
d_config_simulation = {}

# Number of turns to track
d_config_simulation["n_turns"] = 1000000

# Initial off-momentum
d_config_simulation["delta_max"] = 27.0e-5

# Beam to track (b1 or b2)
d_config_simulation["beam"] = "b1"

# Tolerances tune and coupling
d_config_simulation["tol_qx"] = 1e-4 # 1e-4
d_config_simulation["tol_qy"] = 1e-4 # 1e-4
d_config_simulation["tol_dqx"] = 0.05
d_config_simulation["tol_dqy"] = 0.05
d_config_simulation["tol_cminus"] = 1e-3 #1e-4
d_config_simulation["tol_qknobs_step"] = 1e-6 # 1e-4
# ==================================================================================================
# --- Dump collider and collider configuration
#
# Below, the user chooses if the gen 2 collider must be dumped, along with the corresponding
# configuration.
# ==================================================================================================
dump_collider = False
dump_config_in_collider = False
# ==================================================================================================
# --- Machine parameters being scanned (generation 2)
#
# Below, the user defines the grid for the machine parameters that must be scanned to find the
# optimal DA (e.g. tune, chroma, etc).
# ==================================================================================================
# Scan tune with step of 0.001 (need to round to correct for numpy numerical instabilities)
array_qx = np.round(np.arange(62.305, 62.330, 0.001), decimals=4)
array_qy = np.round(np.arange(60.305, 60.330, 0.001), decimals=4)

# In case one is doing a tune-tune scan, to decrease the size of the scan, we can ignore the
# working points too close to resonance. Otherwise just delete this variable in the loop at the end
# of the script
keep = "upper_triangle"  # 'lower_triangle', 'all'
# ==================================================================================================
# --- Make tree for the simulations (generation 1)
#
# The tree is built as a hierarchy of dictionnaries. We add a first generation (named as the
# study being done) to the root. This first generation is used set the initial particle
# distribution, and build a collider with only the optics set.
# ==================================================================================================

# Build empty tree: first generation (later added to the root), and second generation
children = {"base_collider": {"config_particles": {}, "config_collider": {}, "children": {}}}

# Add particles distribution parameters to the first generation
children["base_collider"]["config_particles"] = d_config_particles

# Add base machine parameters to the first generation
children["base_collider"]["config_collider"] = d_config_collider


# ==================================================================================================
# --- Complete tree for the simulations (generation 2)
#
# We now set a second generation for the tree. This second generation contains the tracking
# parameters, as well as a default set of parameters for the colliders (defined above), that we
# mutate according to the parameters we want to scan.
# ! Caution when mutating the dictionary in this function, you have to pass a deepcopy to children,
# ! otherwise the dictionary will be mutated for all the children.
# ==================================================================================================
track_array = np.arange(d_config_particles["n_split"])
for idx_job, (track, qx, qy) in enumerate(itertools.product(track_array, array_qx, array_qy)):
    # If requested, ignore conditions below the upper diagonal as they can't be reached in the LHC
    if keep == "upper_triangle":
        if qy < (qx - 2 + 0.0039):  # 0.039 instead of 0.04 to avoid rounding errors
            continue
    elif keep == "lower_triangle":
        if qy >= (qx - 2 - 0.0039):
            continue
    else:
        pass

    # Mutate the appropriate collider parameters
    for beam in ["b1", "b2"]:
        d_config_collider["tuning"]["qx"][beam] = float(qx)
        d_config_collider["tuning"]["qy"][beam] = float(qy)

    # Complete the dictionnary for the tracking
    d_config_simulation["particle_file"] = f"../particles/{track:02}.parquet"
    d_config_simulation["collider_file"] = "../collider.json.zip"

    # Add a child to the second generation, with all the parameters for the collider and tracking
    children["base_collider"]["children"][f"xtrack_{idx_job:04}"] = {
        "config_simulation": copy.deepcopy(d_config_simulation),
        "config_collider": copy.deepcopy(d_config_collider),
        "log_file": "tree_maker.log",
        "dump_collider": dump_collider,
        "dump_config_in_collider": dump_config_in_collider,
    }

# ==================================================================================================
# --- Simulation configuration
# ==================================================================================================
# Load the tree_maker simulation configuration
config = yaml.safe_load(open("config_sim.yaml"))

# # Set the root children to the ones defined above
config["root"]["children"] = children

# Set miniconda environment path in the config
config["root"]["setup_env_script"] = os.getcwd() + "/../../source_python.sh"


# Recursively define the context for the simulations
def set_context(children, idx_gen, config):
    for child in children.values():
        child["context"] = config["root"]["generations"][idx_gen]["context"]
        if "children" in child.keys():
            set_context(child["children"], idx_gen + 1, config)


set_context(children, 1, config)
# ==================================================================================================
# --- Build tree and write it to the filesystem
# ==================================================================================================
# Define study name
study_name = "ts_eol_hl19_round_v4"

# Creade folder that will contain the tree
if not os.path.exists(f"../scans/{study_name}"):
    os.makedirs(f"../scans/{study_name}")
else:
    answer = input(
        "The folder already exists. You might delete an existing study. "
        "Do you want to overwrite it? [y/n]"
    )
    if answer != "y":
        print("Aborting...")
        exit()

# Move to the folder that will contain the tree
os.chdir(f"../scans/{study_name}")

# Clean the id_job file
id_job_file_path = "id_job.yaml"
if os.path.isfile(id_job_file_path):
    os.remove(id_job_file_path)

# Create tree object
start_time = time.time()
root = initialize(config)
print("Done with the tree creation.")
print(f"--- {time.time() - start_time} seconds ---")

# Check if htcondor is the configuration
if "htc" in config["root"]["generations"][2]["run_on"]:
    generate_run = generate_run_sh_htc
else:
    generate_run = generate_run_sh

# From python objects we move the nodes to the filesystem.
start_time = time.time()
root.make_folders(generate_run)
print("The tree folders are ready.")
print(f"--- {time.time() - start_time} seconds ---")
