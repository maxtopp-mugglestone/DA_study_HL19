"""This script is used to configure the collider and track the particles. Functions in this script
are called sequentially, in the order in which they are defined. Modularity has been favored over
simple scripting for reproducibility, to allow rebuilding the collider from a different program
(e.g. dahsboard)."""
import contextlib

# ==================================================================================================
# --- Imports
# ==================================================================================================
# Import standard library modules
import json
import logging
import os
import time
from zipfile import ZipFile

# Import third-party modules
import numpy as np
import pandas as pd
import ruamel.yaml
import tree_maker

# Import user-defined modules
import xmask as xm
import xmask.lhc as xlhc
import xobjects as xo
import xtrack as xt
import lumilocal
from gen_config_orbit_correction import *
'''

# hack to use 4d twiss for bb
import xfields as xf

import xfields.config_tools.beambeam_config_tools.config_tools as ct
from configure_beam_beam_patch import configure_beam_beam_elements_4dpatch

xt.multiline_legacy.multiline_legacy.MultilineLegacy.configure_beam_beam_elements = (
    configure_beam_beam_elements_4dpatch
)'''


print("CUPY_CACHE_DIR =", os.environ.get("CUPY_CACHE_DIR"))
print("HOME =", os.environ.get("HOME"))

# Initialize yaml reader
ryaml = ruamel.yaml.YAML()
# %% Configuration path
# Set the path to your configuration file
config_path = "config.yaml"

# %% 
# ==================================================================================================
# --- Functions to read configuration files and generate configuration files for orbit correction
# ==================================================================================================
def read_configuration(config_path="config.yaml"):
    # Read configuration for simulations
    with open(config_path, "r") as fid:
        config_gen_2 = ryaml.load(fid)
        
    # Also read configuration from previous generation
    try:
        with open("../" + config_path, "r") as fid:
            config_gen_1 = ryaml.load(fid)
    except Exception:
        with open("../1_build_distr_and_collider/" + config_path, "r") as fid:
            config_gen_1 = ryaml.load(fid)

    return config_gen_1, config_gen_2

config_gen_1, config_gen_2 = read_configuration(config_path)

# Inspect the configurations
print("=== Config Gen 1 (Global) config) ===")
print(f"Keys: {list(config_gen_1.keys())}")
print("\n=== Config Gen 2 (Local config) ===")
print(f"Keys: {list(config_gen_2.keys())}")
print("### Configuration gen 2 ###", config_gen_2)
# %%
# ==================================================================================================
# --- Function for tree_maker tagging
# ==================================================================================================
def tree_maker_tagging(config, tag="started"):
    # Start tree_maker logging if log_file is present in config
    if tree_maker is not None and "log_file" in config:
        tree_maker.tag_json.tag_it(config["log_file"], tag)
    else:
        logging.warning("tree_maker loging not available")

# Tag start of the job
tree_maker_tagging(config_gen_2, tag="started")    

# %%
# ==================================================================================================
# --- Function to get context
# ==================================================================================================
def get_context(configuration):
    # Get device number
    if "device_number" not in configuration:
        device_number = None
    else:
        device_number = configuration["device_number"]

    if configuration["context"] == "cupy":
        return xo.ContextCupy(device=device_number)
    elif configuration["context"] == "opencl":
        return xo.ContextPyopencl()
    elif configuration["context"] == "cpu":
        return xo.ContextCpu(omp_num_threads= 4)
    else:
        logging.warning("context not recognized, using cpu")
        return xo.ContextCpu(omp_num_threads= 4)


context = get_context(config_gen_2)
print(f"Using context: {type(context).__name__}")


# %% Generate orbit correction configuration files
def generate_configuration_correction_files(output_folder="correction"):
    # Generate configuration files for orbit correction
    correction_setup = generate_orbit_correction_setup()
    os.makedirs(output_folder, exist_ok=True)
    for nn in ["b1", "b2"]:
        with open(f"{output_folder}/corr_co_{nn}.json", "w") as fid:
            json.dump(correction_setup[nn], fid, indent=4)

generate_configuration_correction_files()
print("Orbit correction configuration files generated in 'correction/' folder")

# %% Extract simulation and collider configurations
config_sim = config_gen_2["config_simulation"]
config_collider = config_gen_2["config_collider"]

print("=== Simulation Config ===")
for k, v in config_sim.items():
    print(f"  {k}: {v}")

# %%
# ==================================================================================================
# --- Load collider
# ==================================================================================================

# Rebuild collider
if config_sim["collider_file"].endswith(".zip"):
    # Uncompress file locally
    with ZipFile(config_sim["collider_file"], "r") as zip_ref:
        zip_ref.extractall()
    collider = xt.load(
        config_sim["collider_file"].split("/")[-1].replace(".zip", "")
    )
else:
    collider = xt.load(config_sim["collider_file"])
    

print(f"Collider loaded. Lines: {list(collider.lines.keys())}")

tt = collider['b1'].get_table()
for ele in tt.name:
    if 'acs' in ele:
        print(collider.b1.element_dict[ele])
collider['b1'].twiss()
# %%
# ==================================================================================================
# --- Function to install beam-beam skipped: beam-beam installed in gen1
# ==================================================================================================

config_bb = config_collider["beam_beam"]
print("Beam-beam interactions installed")
print(f"Number of particles per bunch: {config_bb['num_particles_per_bunch']:.2e}")
print(f"Sigma_z: {config_bb['sigma_z']} m")

# %% Build trackers
collider.build_trackers()
print("Trackers built")
# %%
# ==================================================================================================
# --- Function to match knobs and tuning
# ==================================================================================================

def set_knobs(lhc, config):
    # Set all knobs (crossing angles, dispersion correction, rf, crab cavities,
    # experimental magnets, etc.)
    for kk, vv in config['knob_settings'].items():
        lhc[kk] = vv
    # save knobs and tuning settings from config file
    return lhc

collider['b1'].twiss()

collider = set_knobs(collider, config_collider)
print("Knobs set. Current knob values:")
for kk, vv in config_collider["knob_settings"].items():
    print(f"  {kk}: {vv}")
collider['b1'].twiss()

# %% Inspect tune and chromaticity BEFORE matching
print("=== Tune and chromaticity BEFORE matching ===")
for line_name in ["b1", "b2"]:
    print(f'Looking at line {line_name}')
    for ii in collider[line_name].element_names:
        if ii.startswith('acsca'):
            print(ii)
            print(collider[line_name][ii])
            #collider[line_name][ii].lag = 180.000000001
    try: 
        tw = collider[line_name].twiss()
    #except xt.twiss.ClosedOrbitSearchError:
    except:
        tw = collider[line_name].twiss4d()
    print(f"\n{line_name}:")
    print(f"  Qx = {tw.qx:.6f}, Qy = {tw.qy:.6f}")
    print(f"  dQx = {tw.dqx:.2f}, dQy = {tw.dqy:.2f}")
    print(f"  c_minus = {tw.c_minus:.6f}")

collider['b1'].twiss()
# %%
# ==================================================================================================
# --- Output initial twiss parameters at IPs
# ==================================================================================================    
try:
    twb1 = collider['b1'].twiss(method="6d", matrix_stability_tol=100)
    twb2 = collider['b2'].twiss(method="6d", matrix_stability_tol=100)
except: #xt.twiss.ClosedOrbitSearchError:
    twb1 = collider['b1'].twiss(method="4d", matrix_stability_tol=100)
    twb2 = collider['b2'].twiss(method="4d", matrix_stability_tol=100)
print(f"--- Now displaying Twiss result at all IPS for beam 1 ---")
print(twb1.rows["ip.*"])
print(f"--- Now displaying Twiss result at all IPS for beam 2 ---")
print(twb2.rows["ip.*"])
iplist = ["ip1", "ip2", "ip5", "ip8"]
for ip in iplist:
    ipx = dict()
    ipx['betx1_initial'] = twb1.rows[ip]['betx'].item()
    ipx['bety1_initial'] = twb1.rows[ip]['bety'].item()
    ipx['betx2_initial'] = twb2.rows[ip]['betx'].item()
    ipx['bety2_initial'] = twb2.rows[ip]['bety'].item()
    config_collider['tuning'][ip] = ipx 
# print qx and qy
print(f"--- Now displaying Qx and Qy for beam 2---")
print(twb1.qx, twb1.qy)
print(f"--- Now displaying Qx and Qy for beam 2---")
print(twb2.qx, twb2.qy)

# %%
# ==================================================================================================
# --- Match closed orbit, tune, chroma
# ==================================================================================================

print("Matching tune and chromaticity...")

def match_tune_and_chroma(lhc, config, match_linear_coupling_to_zero = True):
    # Reference model for orbit correction
    env_ref = xt.load(f'../collider_co_ref.json')

    # Tunings
    conf_tuning = config['tuning']
    optimizers = {}
    for line_name in ['b1', 'b2']:
        print()
        print('Working on line ', line_name)

        knob_names = conf_tuning['knob_names'][line_name]

        targets = {
            'qx': conf_tuning['qx'][line_name],
            'qy': conf_tuning['qy'][line_name],
            'dqx': conf_tuning['dqx'][line_name],
            'dqy': conf_tuning['dqy'][line_name],
        }

        optimizers[line_name] = xm.machine_tuning(line=lhc[line_name],
            enable_closed_orbit_correction=True,
            enable_linear_coupling_correction=match_linear_coupling_to_zero,
            enable_tune_correction=True,
            enable_chromaticity_correction=True,
            knob_names=knob_names,
            targets=targets,
            step_q_knob=conf_tuning['steps']['q_knob'],
            step_dq_knob=conf_tuning['steps']['dq_knob'],
            step_c_minus_knob=conf_tuning['steps']['c_minus_knob'],
            tol_tune=conf_tuning['tolerances']['tune'],
            tol_chromaticity=conf_tuning['tolerances']['chromaticity'],
            tol_c_minus=conf_tuning['tolerances']['c_minus'],
            line_co_ref=env_ref[line_name],
            co_corr_config=conf_tuning['closed_orbit_correction'][line_name])

    return lhc

collider['b1'].twiss()

collider = match_tune_and_chroma(collider, config_collider)
print("Tune and chromaticity matched")


print("=== Tune and chromaticity AFTER matching ===")
for line_name in ["b1", "b2"]:
    try: 
        tw = collider[line_name].twiss()
    except :#xt.twiss.ClosedOrbitSearchError:
        tw = collider[line_name].twiss4d()
    target_qx = config_collider['tuning']["qx"][line_name]
    target_qy = config_collider['tuning']["qy"][line_name]
    target_dqx = config_collider['tuning']["dqx"][line_name]
    target_dqy = config_collider['tuning']["dqy"][line_name]
    print(f"\n{line_name}:")
    print(f"  Qx = {tw.qx:.6f} (target: {target_qx})")
    print(f"  Qy = {tw.qy:.6f} (target: {target_qy})")
    print(f"  dQx = {tw.dqx:.2f} (target: {target_dqx})")
    print(f"  dQy = {tw.dqy:.2f} (target: {target_dqy})")
    print(f"  c_minus = {tw.c_minus:.6f}")

collider['b1'].twiss()
# %%
# ==================================================================================================
# --- Crab cavity status
# ==================================================================================================
crab = False
if "on_crab1" in config_collider["knob_settings"]:
    crab_val = float(config_collider["knob_settings"]["on_crab1"])
    if abs(crab_val) > 0:
        crab = True
print(f"Crab cavities active: {crab}")



# %%
# ==================================================================================================
# --- Function to compute the number of collisions in the IPs (used for luminosity computation)
# ==================================================================================================
def compute_collision_from_scheme(config_bb):
    # Get the filling scheme path (in json or csv format)
    filling_scheme_path = config_bb["mask_with_filling_pattern"]["pattern_fname"]

    # Load the filling scheme
    if not filling_scheme_path.endswith(".json"):
        raise ValueError(
            f"Unknown filling scheme file format: {filling_scheme_path}. It you provided a csv"
            " file, it should have been automatically convert when running the script"
            " 001_make_folders.py. Something went wrong."
        )

    with open(filling_scheme_path, "r") as fid:
        filling_scheme = json.load(fid)

    # Extract booleans beam arrays
    array_b1 = np.array(filling_scheme["beam1"])
    array_b2 = np.array(filling_scheme["beam2"])

    # Assert that the arrays have the required length, and do the convolution
    assert len(array_b1) == len(array_b2) == 3564
    n_collisions_ip1_and_5 = array_b1 @ array_b2
    n_collisions_ip2 = np.roll(array_b1, 891) @ array_b2
    n_collisions_ip8 = np.roll(array_b1, 2670) @ array_b2

    return int(n_collisions_ip1_and_5), int(n_collisions_ip2), int(n_collisions_ip8)


n_collisions_ip1_and_5, n_collisions_ip2, n_collisions_ip8 = compute_collision_from_scheme(config_bb)
print(f"Number of collisions:")
print(f"  IP1 & IP5: {n_collisions_ip1_and_5}")
config_collider['lumi_leveling']['ip1_5']['num_colliding_bunches'] = n_collisions_ip1_and_5
print(f"  IP2: {n_collisions_ip2}")
config_collider['lumi_leveling']['ip2']['num_colliding_bunches'] = n_collisions_ip2
print(f"  IP8: {n_collisions_ip8}")
config_collider['lumi_leveling']['ip8']['num_colliding_bunches'] = n_collisions_ip8
# %%
# ==================================================================================================
# --- Function to do the Levelling
# ==================================================================================================
def level_collider(lhc, config): 
    config_lumi_leveling = config['lumi_leveling']
    config_bb = config['beam_beam']


    # Initial intensity
    initial_I = config_bb["num_particles_per_bunch"]

    # First level luminosity in IP 1/5 changing the intensity
    if (
        "ip1_5" in config_lumi_leveling
        and not config_lumi_leveling["ip1_5"]["skip_leveling"]
    ):
        print("Leveling luminosity in IP 1/5 varying the intensity")
        # Update the number of bunches in the configuration file

        # Do the levelling
        #try:
        bunch_intensity = lumilocal.luminosity_leveling_ip1_5(
            collider,
            config_collider,
            config_bb,
            crab=crab,
        )
        #except ValueError:
        #    print("There was a problem during the luminosity leveling in IP1/5... Ignoring it.")
        #    bunch_intensity = config_bb["num_particles_per_bunch"]

        config_bb["num_particles_per_bunch"] = float(bunch_intensity)
    else:
        print("IP1, 5 leveling skipped")

    xmask_leveling_ips = ['ip2', 'ip8'] #which IPs have levelling inside mask
    config_ip2_8 ={k: config_lumi_leveling[k] for k in xmask_leveling_ips}
    opts = lumilocal.luminosity_leveling( #IP2 and 8 only!
        lhc, config_lumi_leveling=config_ip2_8,
        config_beambeam=config_bb)
    
    # Re-match tunes, and chromaticities
    conf_tuning = config['tuning']

    for line_name in ['b1', 'b2']:
        knob_names = conf_tuning['knob_names'][line_name]
        targets = {
            'qx': conf_tuning['qx'][line_name],
            'qy': conf_tuning['qy'][line_name],
            'dqx': conf_tuning['dqx'][line_name],
            'dqy': conf_tuning['dqy'][line_name],
        }
        xm.machine_tuning(line=lhc[line_name],
            enable_tune_correction=True, enable_chromaticity_correction=True,
            knob_names=knob_names, targets=targets)
            # Update configuration
    config_bb["num_particles_per_bunch_before_optimization"] = float(initial_I)
    config_collider["lumi_leveling"]["ip2"]["final_on_sep2h"] = float(
        collider.vars["on_sep2h"]._value
    )
    config_collider["lumi_leveling"]["ip2"]["final_on_sep2v"] = float(
        collider.vars["on_sep2v"]._value
    )
    config_collider["lumi_leveling"]["ip8"]["final_on_sep8h"] = float(
        collider.vars["on_sep8h"]._value
    )
    config_collider["lumi_leveling"]["ip8"]["final_on_sep8v"] = float(
        collider.vars["on_sep8v"]._value
    )

    return collider, config

if "lumi_leveling" in config_collider and not config_collider["skip_leveling"]:
    collider, config_collider = level_collider(collider, config_collider)

else:
    print(
        "No leveling is done as no configuration has been provided, or skip_leveling"
        " is set to True."
    )

# %%
# ==================================================================================================
# --- Function to add linear coupling 
# ==================================================================================================
def add_linear_coupling(collider, config_collider):
    # Get the version of the optics
    version_hllhc = config_collider["ver_hllhc_optics"]

    conf_tuning = config_collider['tuning']

    # Add linear coupling as the target in the tuning of the base collider was 0
    # (not possible to set it the target to 0.001 for now)
    if version_hllhc in [1.6, 1.5]: #this implementation is for legacy support
        collider.vars["c_minus_re_b1"] += conf_tuning["delta_cmr"]
        collider.vars["c_minus_re_b2"] += conf_tuning["delta_cmr"]
    elif version_hllhc in [1.9]:
        collider.vars["cmrs.b1_op"] += conf_tuning["delta_cmr"]
        collider.vars["cmrs.b2_op"] += conf_tuning["delta_cmr"]
    else:
        raise ValueError(f"Unknown version of the optics/run: {version_hllhc}.")

    return collider


#config_mad = config_gen_1["config_mad"]
collider = add_linear_coupling(collider, config_collider)
print(f"Linear coupling added: delta_cmr = {config_collider['tuning']['delta_cmr']}")

# %%
# ==================================================================================================
# --- Rematch tune and chromaticity without coupling correction
# ==================================================================================================
print("Rematching tune and chromaticity (keeping linear coupling)...")
collider = match_tune_and_chroma(collider, config_collider, match_linear_coupling_to_zero=False)
print("Rematch completed")

# %%
# ==================================================================================================
# --- Function to assert that tune, chromaticity and linear coupling are correct before beam-beam
#     configuration
# ==================================================================================================

def assert_tune_chroma_coupling(collider, config_collider):
    results = {}
    conf_tuning = config_collider['tuning']
    for line_name in ["b1", "b2"]:
        try: 
            tw = collider[line_name].twiss()
        except :#xt.twiss.ClosedOrbitSearchError:
            tw = collider[line_name].twiss4d()
        results[line_name] = {
            "qx": tw.qx,
            "qy": tw.qy,
            "dqx": tw.dqx,
            "dqy": tw.dqy,
            "c_minus": tw.c_minus,
        }
        assert np.isclose(tw.qx, conf_tuning["qx"][line_name], atol=1e-4), (
            f"tune_x is not correct for {line_name}. Expected"
            f" {conf_tuning['qx'][line_name]}, got {tw.qx}"
        )
        assert np.isclose(tw.qy, conf_tuning["qy"][line_name], atol=1e-4), (
            f"tune_y is not correct for {line_name}. Expected"
            f" {conf_tuning['qy'][line_name]}, got {tw.qy}"
        )
        assert np.isclose(
            tw.dqx,
            conf_tuning["dqx"][line_name],
            rtol=1e-2,
        ), (
            f"chromaticity_x is not correct for {line_name}. Expected"
            f" {conf_tuning['dqx'][line_name]}, got {tw.dqx}"
        )
        assert np.isclose(
            tw.dqy,
            conf_tuning["dqy"][line_name],
            rtol=1e-2,
        ), (
            f"chromaticity_y is not correct for {line_name}. Expected"
            f" {conf_tuning['dqy'][line_name]}, got {tw.dqy}"
        )

        assert np.isclose(
            tw.c_minus,
            conf_tuning["delta_cmr"],
            atol=5e-3,
        ), (
            f"linear coupling is not correct for {line_name}. Expected"
            f" {conf_tuning['delta_cmr']}, got {tw.c_minus}"
        )
        return results


print("=== Final verification ===")
results = assert_tune_chroma_coupling(collider, config_collider)
for line_name, vals in results.items():
    print(f"\n{line_name}:")
    print(f"  Qx = {vals['qx']:.6f} (target: {config_collider['tuning']['qx'][line_name]})")
    print(f"  Qy = {vals['qy']:.6f} (target: {config_collider['tuning']['qy'][line_name]})")
    print(f"  dQx = {vals['dqx']:.2f} (target: {config_collider['tuning']['dqx'][line_name]})")
    print(f"  dQy = {vals['dqy']:.2f} (target: {config_collider['tuning']['dqy'][line_name]})")
    print(f"  c_minus = {vals['c_minus']:.6f} (target: {config_collider['tuning']['delta_cmr']})")
print("\nAll assertions passed!")


# %% (Optional) Save collider before beam-beam
# Uncomment to save the collider before beam-beam configuration
if config_gen_2['dump_collider']:
    collider.to_json("collider_before_bb.json")
    print("Collider before beam-beam saved")

# %%
# ==================================================================================================
# --- Function to configure beam beam and set the bunch numbers
# ==================================================================================================
def configure_beam_beam(lhc, config_collider):  
    config_bb = config_collider['beam_beam']
    # Configure beam-beam lenses
    print('Configuring beam-beam lenses...')
    lhc.xfields.configure_beambeam_interactions(
        num_particles=config_bb['num_particles_per_bunch'],
        nemitt_x=config_bb['nemitt_x'],
        nemitt_y=config_bb['nemitt_y'])

    if 'mask_with_filling_pattern' in config_bb:
        fname = config_bb['mask_with_filling_pattern']['pattern_fname']
        i_bunch_cw = config_bb['mask_with_filling_pattern']['i_bunch_b1']
        i_bunch_acw = config_bb['mask_with_filling_pattern']['i_bunch_b2']
        with open(fname, 'r') as fid:
            filling = json.load(fid)

        lhc.apply_filling_pattern(
            filling_pattern_cw=filling['beam1'],
            filling_pattern_acw=filling['beam2'],
            i_bunch_cw=i_bunch_cw, i_bunch_acw=i_bunch_acw)

    return lhc, config_bb



if config_bb["install_beam_beam"]:
    print("Configuring beam-beam...")
    collider, config_bb = configure_beam_beam(collider, config_collider)
    print("Beam-beam configured")
    print(f"Filling scheme: {config_bb['mask_with_filling_pattern']['pattern_fname']}")
    print(f"Bunch B1: {config_bb['mask_with_filling_pattern']['i_bunch_b1']}")
    print(f"Bunch B2: {config_bb['mask_with_filling_pattern']['i_bunch_b2']}")
else:
    print("Skipping beam-beam configuration (install_beam_beam=False)")

# %%
# ==================================================================================================
# --- Output final twiss parameters at IPs
# ==================================================================================================    
try:
    twb1 = collider['b1'].twiss(method="6d", matrix_stability_tol=100)
    twb2 = collider['b2'].twiss(method="6d", matrix_stability_tol=100)
except: # xt.twiss.ClosedOrbitSearchError:
    twb1 = collider['b1'].twiss(method="4d", matrix_stability_tol=100)
    twb2 = collider['b2'].twiss(method="4d", matrix_stability_tol=100)
print(f"--- Now displaying Twiss result at all IPS for beam 1 ---")
print(twb1.rows["ip.*"])
print(f"--- Now displaying Twiss result at all IPS for beam 2 ---")
print(twb2.rows["ip.*"])
iplist = ["ip1", "ip2", "ip5", "ip8"]
for ip in iplist:
    ipx = dict()
    ipx['betx1_final'] = twb1.rows[ip]['betx'].item()
    ipx['bety1_final'] = twb1.rows[ip]['bety'].item()
    ipx['betx2_final'] = twb2.rows[ip]['betx'].item()
    ipx['bety2_final'] = twb2.rows[ip]['bety'].item()
    config_collider['tuning'][ip].update(ipx)
# print qx and qy
print(f"--- Now displaying Qx and Qy for beam 1---")
print(twb1.qx, twb1.qy)
print(f"--- Now displaying Qx and Qy for beam 2---")
print(twb2.qx, twb2.qy)


# %%
# ==================================================================================================
# --- Function to compute luminosity once the collider is configured
# ==================================================================================================
def record_final_luminosity(collider, config_bb, l_n_collisions, crab):
    """Compute and record the final luminosity at all IPs."""
    l_ip = ["ip1", "ip2", "ip5", "ip8"]

    def twiss_and_compute_lumi(collider, config_bb, l_n_collisions, crab):
        try:
            twiss_b1 = collider['b1'].twiss(method="6d", matrix_stability_tol=100)
            twiss_b2 = collider['b2'].twiss(method="6d", matrix_stability_tol=100)
        except: #xt.twiss.ClosedOrbitSearchError:
            twiss_b1 = collider['b1'].twiss(method="4d", matrix_stability_tol=100)
            twiss_b2 = collider['b2'].twiss(method="4d", matrix_stability_tol=100)
        l_lumi = []
        l_PU = []
        for n_col, ip in zip(l_n_collisions, l_ip):
            try:
                L = lumilocal.luminosity_from_twiss(
                    n_colliding_bunches=n_col,
                    num_particles_per_bunch=config_bb["num_particles_per_bunch"],
                    ip_name=ip,
                    nemitt_x=config_bb["nemitt_x"],
                    nemitt_y=config_bb["nemitt_y"],
                    sigma_z=config_bb["sigma_z"],
                    twiss_b1=twiss_b1,
                    twiss_b2=twiss_b2,
                    crab=crab,
                )
                PU = lumilocal.compute_PU(L, n_col, twiss_b1["t_rev0"])
            except Exception:
                print(f"Problem computing luminosity in {ip}... Ignoring it.")
                L = 0
                PU = 0
            l_lumi.append(L)
            l_PU.append(PU)
        return l_lumi, l_PU

    # Without beam-beam
    collider.vars["beambeam_scale"] = 0
    l_lumi_no_bb, l_PU_no_bb = twiss_and_compute_lumi(collider, config_bb, l_n_collisions, crab)

    for ip, L, PU in zip(l_ip, l_lumi_no_bb, l_PU_no_bb):
        config_bb[f"luminosity_{ip}_without_beam_beam"] = float(L)
        config_bb[f"Pile-up_{ip}_without_beam_beam"] = float(PU)

    # With beam-beam
    collider.vars["beambeam_scale"] = 1
    l_lumi_bb, l_PU_bb = twiss_and_compute_lumi(collider, config_bb, l_n_collisions, crab)

    for ip, L, PU in zip(l_ip, l_lumi_bb, l_PU_bb):
        config_bb[f"luminosity_{ip}_with_beam_beam"] = float(L)
        config_bb[f"Pile-up_{ip}_with_beam_beam"] = float(PU)

    return config_bb, l_ip, l_lumi_no_bb, l_lumi_bb, l_PU_no_bb, l_PU_bb

l_n_collisions = [n_collisions_ip1_and_5, n_collisions_ip2, n_collisions_ip1_and_5, n_collisions_ip8]
config_bb, l_ip, l_lumi_no_bb, l_lumi_bb, l_PU_no_bb, l_PU_bb = record_final_luminosity(
    collider, config_bb, l_n_collisions, crab
)

print("=== Luminosity Results ===")
print(f"{'IP':<6} {'L (no BB)':<15} {'L (with BB)':<15} {'PU (no BB)':<12} {'PU (with BB)':<12}")
for ip, L_no, L_bb, PU_no, PU_bb in zip(l_ip, l_lumi_no_bb, l_lumi_bb, l_PU_no_bb, l_PU_bb):
    print(f"{ip:<6} {L_no:<15.3e} {L_bb:<15.3e} {PU_no:<12.2f} {PU_bb:<12.2f}")


# %% Save updated configuration
with open(config_path, "w") as fid:
    ryaml.dump(config_gen_2, fid)
print(f"Configuration saved to {config_path}")

# %%
# ==================================================================================================
# --- Function to prepare particles distribution for tracking
# ==================================================================================================
def prepare_particle_distribution(collider, context, config_sim, config_bb):
    beam = config_sim["beam"]

    particle_df = pd.read_parquet(config_sim["particle_file"])

    r_vect = particle_df["normalized amplitude in xy-plane"].values
    theta_vect = particle_df["angle in xy-plane [deg]"].values * np.pi / 180  # type: ignore # [rad]

    A1_in_sigma = r_vect * np.cos(theta_vect)
    A2_in_sigma = r_vect * np.sin(theta_vect)

    particles = collider[beam].build_particles(
        x_norm=A1_in_sigma,
        y_norm=A2_in_sigma,
        delta=config_sim["delta_max"],
        nemitt_x = config_bb["nemitt_x"],
        nemitt_y = config_bb["nemitt_y"],
        _context=context,
    )

    particle_id = particle_df.particle_id.values
    return particles, particle_id, r_vect, theta_vect


particles, particle_id, l_amplitude, l_angle = prepare_particle_distribution(
    collider, context, config_sim, config_bb
)

print(f"Particles prepared: {len(particle_id)} particles")
print(f"Amplitude range: {l_amplitude.min():.2f} - {l_amplitude.max():.2f} sigma")
print(f"Angle range: {l_angle.min()*180/np.pi:.1f} - {l_angle.max()*180/np.pi:.1f} deg")

# %% (Optional) Reset tracker for GPU
# Uncomment if you need to switch to GPU context
if config_gen_2["context"] in ["cupy", "opencl"]:
     collider.discard_trackers()
     collider.build_trackers(_context=context)
     print("Trackers rebuilt for GPU context")

# %%
# ==================================================================================================
# --- Function to do the tracking
# ==================================================================================================
def track(collider, particles, config_sim, save_input_particles=False):
    # Get beam being tracked
    beam = config_sim["beam"]

    # Optimize line for tracking
    collider[beam].optimize_for_tracking() #something isn't implemented inside this. CHECK

    # Save initial coordinates if requested
    if save_input_particles:
        pd.DataFrame(particles.to_dict()).to_parquet("input_particles.parquet")

    # Track
    num_turns = config_sim["n_turns"]
    a = time.time()
    print('Tracking')
    collider[beam].track(particles, turn_by_turn_monitor=False, num_turns=num_turns)
    b = time.time()

    print(f"Elapsed time: {b-a} s")
    print(f"Elapsed time per particle per turn: {(b-a)/particles._capacity/num_turns*1e6} us")

    return particles

particles = track(collider, particles, config_sim, save_input_particles=True)

# %% Process and save tracking results
def process_and_save_results(particles, particle_id, l_amplitude, l_angle,
                             config_gen_1, config_gen_2):
    """Process tracking results and save to parquet file."""
    particles_dict = particles.to_dict()
    particles_df = pd.DataFrame(particles_dict)

    # Sort by parent_particle_id
    particles_df = particles_df.sort_values("parent_particle_id")

    # Assign the original particle IDs
    particles_df["particle_id"] = particle_id

    # Add amplitude and angle
    particles_df["normalized amplitude in xy-plane"] = l_amplitude
    particles_df["angle in xy-plane [deg]"] = l_angle * 180 / np.pi

    # Add metadata

    particles_df.attrs["configuration_gen_1"] = config_gen_1
    particles_df.attrs["configuration_gen_2"] = config_gen_2
    particles_df.attrs["date"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # Save
    
    particles_df.to_parquet("output_particles.parquet")
    print("Results saved to 'output_particles.parquet'")
    
    return particles_df

particles_df = process_and_save_results(
    particles, particle_id, l_amplitude, l_angle,
    config_gen_1, config_gen_2
 )
print('Tracking results processed and saved.')

