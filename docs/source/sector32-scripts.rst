====================
Sector 32-ID Scripts
====================

Move Energy
===========

The :mod:`~aps_32id.run.move_energy` script provides a way to change
the energy of the beamline. If the parameter ``constant_mag`` is
truthy, the detector will move to maintain a constant level of
magnification. The equivalent function
:func:`~aps_32id.run.move_energy.move_energy` can be used
programatically.

Energy Scan
===========

The :mod:`~aps_32id.run.energy_scan` script collects 2D frames over a
range of energies, as well as the corresponding flat-field and
dark-field images. The equivalent function
:py:func:`~aps_32id.run.energy_scan.run_energy_scan` lets this script be
called programatically. The variable dictionary contains parameters
for ``Energy_Start``, ``Energy_End`` and ``Energy_Step``. If more
control is needed (eg, non-evenly spaced energies), then the function
should be used with the ``energies`` argument. The helper function
:py:func:`~scanlib.tools.energy_range` allows easy construction of a unique
list of energies.

.. code:: python

    from aps_32id import run_energy_scan
    from scanlib import energy_range
    import numpy as np

    # Create a list of energies from energy ranges
    energies = energy_range(
        # (start, end, step)
        (8250, 8290, 10),
	(8290, 8300, 2),
	(8300, 8380, 1),
	(8380, 8500, 10),
    )

    # Describe position for sample and flat-field frames
    # (x, y, z, θ°)
    out_pos = (0.2, None, None, 0)
    sample_pos = (0, None, None, 0)

    # Execute the scan
    run_energy_scan(energies=energies, out_pos=out_pos, sample_pos=sample_pos)


Tomography Step Scan
====================

The :mod:`~aps_32id.run.tomo_step_scan` script collects a tomogram as
well as flat-field and dark-field images. The variable dictionary
entries ``SampleStart_Rot``, ``SampleEnd_Rot``, ``Projections``
control which angles get run. If more control is needed, the
:py:func:`~aps_32id.run.tomo_step_scan.run_tomo_step_scan` function
with the ``angles`` parameter can be used. It is not a requirement
that the angles be equally spaced.

.. code:: python

    import numpy as np

    from aps_32id import run_tomo_step_scan

    # Create the list of angles to scan
    angles = np.linspace(0, 180, 361)

    # Describe positions for sample and white-field position
    # (x, y, z, θ°)
    out_pos = (0.2, None, None, 0)
    sample_pos = (0, None, None, 0)

    # Execute the scan
    run_tomo_step_scan(angles=angles, sample_pos=sample_pos, out_pos=out_pos)

Tomography Fly Scan
===================

.. warning::

   This function has not yet replaced the "old style" script at the
   beamline.

The :mod:`~aps_32id.run.tomo_fly_scan` script is similar to
:mod:`~aps_32id.run.tomo_step_scan` except it does not come to a
complete stop when collecting projection.

Mosaic Tomography Fly Scan
==========================

.. warning::

   This function has not yet replaced the "old style" script at the
   beamline.

The :mod:`~aps_32id.run.mosaic_tomo_fly_scan` script and
:func:`~aps_32id.run.mosaic_tomo_fly_scan.mosaic_tomo_fly_scan` are
similar to :mod:`~aps_32id.run.tomo_step_scan` except multiple fields
of view are collected.

Roll-Your-Own Scripts
=====================

Those with a sense of adventure can write their own scripts for
Sector 32. It's highly recommended to become familiar with the
:doc:`sector32-txm` and :doc:`examples` pages.
