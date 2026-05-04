"""This script is used to build the base collider with Xmask, configuring only the optics. Functions
in this script are called sequentially."""

# ==================================================================================================
# --- Imports
# ==================================================================================================

# Import standard library modules
import itertools
import logging
import os
import shutil
from zipfile import ZipFile

# Import third-party modules
import numpy as np

# Import user-defined modules
import pandas as pd
import tree_maker
import xtrack as xt
import xdeps as xd
import xmask as xm
import xmask.lhc as xlhc
import yaml
#from cpymad.madx import Madx


# ==================================================================================================
# --- Function for tree_maker tagging
# ==================================================================================================
def tree_maker_tagging(config, tag="started"):
    # Start tree_maker logging if log_file is present in config
    if tree_maker is not None and "log_file" in config:
        tree_maker.tag_json.tag_it(config["log_file"], tag)
    else:
        logging.warning("tree_maker logging not available")


# ==================================================================================================
# --- Function for check of lattices
# ==================================================================================================    
def check_xsuite_lattices(my_line):
    tw = my_line.twiss(method="6d", matrix_stability_tol=100)
    print(f"--- Now displaying Twiss result at all IPS for line {my_line}---")
    print(tw.rows["ip.*"])
    # print qx and qy
    print(f"--- Now displaying Qx and Qy for line {my_line}---")
    print(tw.qx, tw.qy)


# ==================================================================================================
# --- Function to load configuration file
# ==================================================================================================
def load_configuration(config_path="config.yaml"):
    # Load configuration
    with open(config_path, "r") as fid:
        configuration = yaml.safe_load(fid)

    # Get configuration for the particles distribution and the collider separately
    config_particles = configuration["config_particles"]
    config_collider = configuration["config_collider"]

    return configuration, config_particles, config_collider


# ==================================================================================================
# --- Function to build particle distribution and write it to file
# ==================================================================================================
def build_particle_distribution(config_particles):
    # Define radius distribution
    r_min = config_particles["r_min"]
    r_max = config_particles["r_max"]
    n_r = config_particles["n_r"]
    radial_list = np.linspace(r_min, r_max, n_r, endpoint=False)

    # Filter out particles with low and high amplitude to accelerate simulation
    # radial_list = radial_list[(radial_list >= 4.5) & (radial_list <= 7.5)]

    # Define angle distribution
    n_angles = config_particles["n_angles"]
    theta_list = np.linspace(0, 90, n_angles + 2)[1:-1]

    # Define particle distribution as a cartesian product of the above
    particle_list = [
        (particle_id, ii[1], ii[0])
        for particle_id, ii in enumerate(itertools.product(theta_list, radial_list))
    ]

    # Split distribution into several chunks for parallelization
    n_split = config_particles["n_split"]
    particle_list = list(np.array_split(particle_list, n_split))

    # Return distribution
    return particle_list


def write_particle_distribution(particle_list):
    # Write distribution to parquet files
    distributions_folder = "particles"
    os.makedirs(distributions_folder, exist_ok=True)
    for idx_chunk, my_list in enumerate(particle_list):
        pd.DataFrame(
            my_list,
            columns=["particle_id", "normalized amplitude in xy-plane", "angle in xy-plane [deg]"],
        ).to_parquet(f"{distributions_folder}/{idx_chunk:02}.parquet")


# ==================================================================================================
# --- Function to build collider in xsuite
# ==================================================================================================
def build_collider_xsuite(config_collider, sanity_checks=True):

    # Load lattice
    lhc = xt.load(config_collider['lattice_file'])

    # Clear default twiss settings
    lhc.b1.twiss_default.clear()
    lhc.b2.twiss_default.clear()

    # Load optics
    lhc.vars.load(config_collider['optics_file'])

    # For legacy files:
    if 'particle_ref_b1' not in lhc.particles:
        if 'p0c' not in lhc.vars:
            lhc['p0c'] = 6.8e12
        lhc.new_particle(f'particle_ref_b1', p0c='p0c')
        lhc.new_particle(f'particle_ref_b2', p0c='p0c')
        lhc.b1.particle_ref = 'particle_ref_b1'
        lhc.b2.particle_ref = 'particle_ref_b2'

    assert 'particle_ref_b1' in lhc.particles
    assert 'particle_ref_b2' in lhc.particles
    assert lhc.b1.particle_ref.name == 'particle_ref_b1'
    assert lhc.b2.particle_ref.name == 'particle_ref_b2'

    # Define reference energy and rigidity variables
    lhc['energy0_b1'] = lhc.ref['particle_ref_b1'].energy0[0]
    lhc['energy0_b2'] = lhc.ref['particle_ref_b2'].energy0[0]
    lhc['brho0_b1'] = lhc.ref['particle_ref_b1'].rigidity0[0]
    lhc['brho0_b2'] = lhc.ref['particle_ref_b2'].rigidity0[0]

    # Define new knobs from yaml
    lhc.vars.default_to_zero = True # for knobs defined implicitly within expressions
    for knob_name, knob_expr in config_collider['new_knobs'].items():
        lhc[knob_name] = knob_expr
    lhc.vars.default_to_zero = False

    # Attach orbit correction knobs to all dipole correctors
    lhc['on_corr_co'] = 1
    for kk in list(lhc.vars.keys()):
        if kk.startswith('acb'):
            lhc['corr_co_'+kk] = 0
            lhc.ref[kk] += (lhc.ref['corr_co_'+kk] * lhc.ref['on_corr_co'])

    # Cycle both beams
    lhc.b1.cycle('ip3')
    lhc.b2.cycle('ip3')

    # Install beam-beam lenses (inactive and not configured)
    config_bb = config_collider['beam_beam']
    if config_bb['install_beam_beam']:
        lhc.install_beambeam_interactions(
            clockwise_line='b1',
            anticlockwise_line='b2',
            ip_names=['ip1', 'ip2', 'ip5', 'ip8'],
            delay_at_ips_slots=[0, 891, 0, 2670],
            num_long_range_encounters_per_side=
                config_bb['num_long_range_encounters_per_side'],
            num_slices_head_on=config_bb['num_slices_head_on'],
            harmonic_number=35640,
            bunch_spacing_buckets=config_bb['bunch_spacing_buckets'],
            sigmaz=config_bb['sigma_z'])

    # Prepare reference model for orbit correction
    lhc_co_ref = xlhc.build_closed_orbit_reference(lhc)
    #lhc_co_ref.to_json(f'lhc_co_ref_{config_collider["label"]}.json')

    #lhc.to_json(f'lhc_{config_collider["label"]}_00_prepared.json')

    # Check that both lines twiss without errors
    twb1 = lhc.b1.twiss4d()
    twb2 = lhc.b2.twiss4d()
    if sanity_checks:
        check_xsuite_lattices(lhc.b1)
        check_xsuite_lattices(lhc.b2)
    return lhc

def build_closed_orbit_reference(lhc):

    lhc_ref = lhc.copy() # deep copy
    lhc_ref._var_management = None
    lhc_ref._init_var_management() # kills all knobs on the elements and the particles

    xm.transfer_vars_to_env(lhc, lhc_ref)

    tt_ref = lhc_ref.elements.get_table()
    tt_correctors = tt_ref.rows.match(name='mcb.*')
    tt_experimental_magnets = tt_ref.rows.match(name=r'mb[xlaw].*\.1[rl][28]/.*')
    element_names_transfer_strengths = list(set(tt_correctors.name) | set(tt_experimental_magnets.name))

    old_default_to_zero = lhc_ref.vars.default_to_zero
    lhc_ref.vars.default_to_zero = True

    formatter = xd.refs.CompactFormatter(scope=None)
    for nn in element_names_transfer_strengths:
        if hasattr(lhc_ref[nn], 'knl'):
            expr_knl = lhc.ref[nn].knl[0]._expr
            if expr_knl is not None:
                lhc_ref[nn].knl[0] = expr_knl._formatted(formatter)
        if hasattr(lhc_ref[nn], 'ksl'):
            expr_ksl = lhc.ref[nn].ksl[0]._expr
            if expr_ksl is not None:
                lhc_ref[nn].ksl[0] = expr_ksl._formatted(formatter)
    lhc_ref.vars.default_to_zero = old_default_to_zero

    return lhc_ref

def clean():
    # Remove all the temporary files created in the process of building collider
    shutil.rmtree("temp")
    os.unlink("errors")
    os.unlink("acc-models-lhc")


# ==================================================================================================
# --- Main function for building distribution and collider
# ==================================================================================================
def build_distr_and_collider(config_file="config.yaml"):
    # Get configuration
    configuration, config_particles, config_collider = load_configuration(config_file)

    # Get sanity checks flag
    sanity_checks = configuration["sanity_checks"]

    # Tag start of the job
    tree_maker_tagging(configuration, tag="started")

    # Build particle distribution
    particle_list = build_particle_distribution(config_particles)

    # Write particle distribution to file
    write_particle_distribution(particle_list)

    # Build collider from mad model
    collider = build_collider_xsuite(config_collider, sanity_checks)

    # Clean temporary files
    collider_co_ref = build_closed_orbit_reference(collider)

    # Save collider to json
    collider.to_json("collider.json")
    collider.to_json("collider_co_ref.json")

    # Compress the collider file to zip to ease the load on afs
    with ZipFile("collider.json.zip", "w") as zipf:
        zipf.write("collider.json")
        zipf.write("collider_co_ref.json")
        
    os.rename('config.yaml', 'config_gen1.yaml')
    # Tag end of the job
    tree_maker_tagging(configuration, tag="completed")


# ==================================================================================================
# --- Script for execution
# ==================================================================================================

if __name__ == "__main__":
    build_distr_and_collider()
