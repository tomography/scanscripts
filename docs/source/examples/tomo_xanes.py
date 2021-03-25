#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

import aps_32id
import scanlib

log_level = logging.DEBUG
logging.basicConfig(level=log_level)
log = logging.getLogger(__name__)

energies = scanlib.energy_range(
    # (start, stop, step)
    (6.529, 6.547, 0.003),
    (8.5, 8.7, 0.01),
)

energies = [8.3, 8.345, 8.43]

# (x, y, z, θ°)
# None = use current value
sample_pos = (0, 0, 0, -71)
out_pos = (0.0, 0, 8, -90)

# (pre-dark, post-dark)
num_dark = (5, 0)
num_white = (10, 10)

# Rotation range (start°, end°)
rotation_range = (-70, 70)
n_proj = 726

# Exposure time in seconds
exposure_sec = 0.5

#########################################################################

for energy in energies:
    # Move to the new energy point
    log.debug("Hello")
    aps_32id.move_energy(energy, constant_mag=True)
    # Perform the tomo fly scan
    log.debug("Beginning tomo_fly_scan at %f keV", energy)
    aps_32id.run_tomo_fly_scan(projections=n_proj, 
                               rotation_start=rotation_range[0],
                               rotation_end=rotation_range[1],
                               exposure=exposure_sec,
                               num_white=num_white, num_dark=num_dark,
                               sample_pos=sample_pos, out_pos=out_pos,
                               log_level=log_level)
