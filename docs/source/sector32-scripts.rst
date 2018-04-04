====================
Sector 32-ID Scripts
====================

General Features
================

All the scan scripts below can be executed in one of three ways.

1. Through the ``tomography.sh`` graphical user interface (GUI)
2. From the command line interface (CLI)
3. Directly from a python interpreter   

The mechanisms behind the GUI and command-line interfaces are
identical. Every argument in the GUI parameter panel is also present
as a long argument on the command-line:

.. code:: bash

   $ energy-scan --Energy_End 8.5 --Energy_Start 8.3 --ExposureTime 1.5 --SampleXOut 0.1

The programatic python versions start with ``run_``. They often have
slightly differet parameters to the GUI/CLI implementation, allowing
for more precise control.

.. code:: python

   >>> import aps_32id
   >>> import numpy as np
   >>> aps_32id.run_energy(energies=np.linspace(8.3, 8.5, num=101))

Logging
-------

These scripts (except for ``move_energy``) uses the standard library
:py:mod:`logging` module to save logs with file names matching the
HDF5 data files. The default level is ``logging.INFO``, but this can
be changed by using the ``Log_Level`` variable:

.. code:: bash

   $ energy-scan --Log_Level 10

or the ``log_level`` parameter:

.. code:: python

   >>> import numpy as np
   >>> import logging
   >>> import aps_32id
   >>> aps_32id.run_energy_scan(energies=np.linspace(8.3, 8.5, 100), log_level=logging.DEBUG)

The log levels are the same as those defined in the logging
module. They get set to the root logger, so logging.UNSET results in
all messages being sent through. The special value -1 causes no
changes to the logging configuration.

.. table:: Logging levels for the ``Log_Level`` variable
   :widths: auto

   =================  =====
   Level              Value
   =================  =====
   (no change)        -1
   logging.UNSET      0
   logging.DEBUG      10
   logging.INFO       20
   logging.WARNING    30
   logging.ERROR      40
   logging.CRITICAL   50
   =================  =====

Move Energy
===========

+---------------+--------------------------------+
| GUI:          | ``run/move_energy.py``         |
+---------------+--------------------------------+
| Command-line: | ``$ move-energy``              |
+---------------+--------------------------------+
| Python:       | ``>>> aps_32id.move_energy()`` |
+---------------+--------------------------------+

The :mod:`~aps_32id.run.move_energy` script provides a way to change
the energy of the beamline. If the parameter ``constant_mag`` is
truthy, the detector will move to maintain a constant level of
magnification. The equivalent function
:func:`~aps_32id.run.move_energy.move_energy` can be used
programatically.

Energy Scan
===========

+---------------+------------------------------------+
| GUI:          | ``run/energy_scan.py``             |
+---------------+------------------------------------+
| Command-line: | ``$ energy-scan``                  |
+---------------+------------------------------------+
| Python:       | ``>>> aps_32id.run_energy_scan()`` |
+---------------+------------------------------------+

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

+---------------+---------------------------------------+
| GUI:          | ``run/tomo_step_scan.py``             |
+---------------+---------------------------------------+
| Command-line: | ``$ tomo-step-scan``                  |
+---------------+---------------------------------------+
| Python:       | ``>>> aps_32id.run_tomo_step_scan()`` |
+---------------+---------------------------------------+

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

+---------------+--------------------------------------+
| GUI:          | ``run/tomo_fly_scan.py``             |
+---------------+--------------------------------------+
| Command-line: | ``$ tomo-fly-scan``                  |
+---------------+--------------------------------------+
| Python:       | ``>>> aps_32id.run_tomo_fly_scan()`` |
+---------------+--------------------------------------+

The :mod:`~aps_32id.run.tomo_fly_scan` script is similar to
:mod:`~aps_32id.run.tomo_step_scan` except it does not come to a
complete stop when collecting projection. The timing must be uniform,
so only equally spaced angles are allowed, even in the python function
form.

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
