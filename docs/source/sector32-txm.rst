================
Sector 32-ID TXM
================

.. note::

   This code is under active development and may change at any
   time. If you encounter issues, or documentation bugs, please
   `submit an issue`_.

This page describes the features of the
:py:class:`aps_32id.txm.NanoTXM` class, and a few supporting
classes. The :py:class:`~aps_32id.txm.NanoTXM` class is the primary
interface for controlling the Transmission X-ray Microscope (TXM) at
beamline 32-ID-C. There is also a complimentary
:py:class:`aps_32id.txm.MicroTXM`.

A **core design goal** is to keep as much of the complexity in the
:class:`~aps_32id.txm.NanoTXM` class, which leaves the scripts to
handle high-level details. It also allows for better unit and
integration testing. When creating new scripts, it is recommended to
**put all interactions to process variables (PVs) in methods of the**
:py:class:`~aps_32id.txm.NanoTXM` **class**. This may seem silly for
single PV situations, but will make the script more readable. A
hypothetical example:

.. code:: python

   # Not readable at all: what does that address even mean??
   PV('32idcTXM:SG_RdCntr:reset.PROC').put(1, wait=True)
	  
   # Better, but still not great: what does 1 mean?
   txm.Reset_Theta = 1

   # Best, even though this method definition would only have one line
   txm.reset_theta()

.. _sector-32-config:

Sector 32-ID Configuration
--------------------------

The following configuration options can be set in the
``beamline_config.conf`` file under the ``[32-ID-C]`` heading:

has_permit (yes|no)
  If ``has_permit`` is "no", then the script will not attempt to
  change the X-ray source, monochromator, shutters, etc. This allows
  testing of scripts while the B-hutch is operating without risking
  interferance.
stage (NanoTXM|MicroCT)
  Controls which stage/optics/shutters to use for manipulating the
  sample. ``MicroCT`` uses the front stage and ``NanoTXM`` uses the
  rear stage.
zone_plate_drift_x (float)
  Adjusts the zoneplate x position by this amount for every unit
  change of zoneplate z. When properly set, this will keep the sample
  centered when changing energy.
zone_plate_drift_y (float)
  Adjusts the zoneplate y position by this amount for every unit
  change of zoneplate z. When properly set, this will keep the sample
  centered when changing energy.

.. literalinclude:: examples/beamline_config.conf


Stopping Scans Gracefully
-------------------------

When a scan script ends, we want the **instrument to return to a
usable configuration** even if an exception occurred. Using the
:py:meth:`~aps_32id.txm.NanoTXM.run_scan()` context manager, this
becomes easy. At the start of the context, this manager saves certain
configuration details about instrument; when exiting the context for
any reason the configuration is restored, the CCD is set to
"continuous mode", and any extra logging is stopped:

.. code:: python

   import logging
   import aps_32id

   txm = aps_32id.NanoTXM()
   
   with txm.run_scan():
       # Setup the microscope as desired
       txm.setup_hdf_writer()
       txm.start_logging(logging.INFO)
       txm.setup_detector()
       # Now do experiment stuff
       

Process Variables
-----------------

Process variables (PVs), though the :mod:`pyepics` package are the way
python controls the actuators and sensors of the instrument. There are
**two ways to interact with process variables**:

1. The :py:meth:`~aps_32id.txm.NanoTXM.pv_put` method on a
   :py:class:`~aps_32id.txm.NanoTXM` object.
2. A :py:class:`~scanlib.txm_pv.TxmPV` descriptor on the
   :py:class:`~aps_32id.txm.NanoTXM` class (or subclass).

The second option handles more of the underlying complexity, but
understanding it requires a good grasp of the first option. The
:py:meth:`NanoTXM.pv_put() <aps_32id.txm.NanoTXM.pv_put>` method is a
wrapper around :py:meth:`pyepics.PV.put`, and accepts similar
arguments:

.. code:: python

   # These two sets of statements have the same effect

   # Using the epics PV class
   epics.PV('my_great_pv').put(1, wait=True)

   # Using the TXM method
   my_txm = TXM()
   my_txm.pv_put('my_great_pv', 1, wait=True)

Behind the scenes, there is some extra magic so :ref:`the txm can
coordinate PVs that work together <wait_pvs>`.

Manually supplying the PV name and options each time is cumbersome, so
the :py:class:`~scanlib.txm_pv.TxmPV` descriptor can be used to
**define PVs at import time**. Set instances of the
:py:class:`~scanlib.txm_pv.TxmPV` class as attributes on a
:class:`~aps_32id.txm.NanoTXM` subclass, then assign and retrieve
values directly from the attribute:

.. code:: python

    from aps_32id import NanoTXM
    from scanlib import TxmPV

    class ExampleTXM(NanoTXM):
        # Define a PV during import time
        my_awesome_pv = TxmPV('cryptic:pv:string', dtype=float, wait=True)
        # More PV definitions go here

    # Now we can use the PV attribute of the txm class
    my_txm = ExampleTXM()
    # Retrieve the current value
    # Equivalent to ``float(epics.PV('cryptic:pv:string').get())``
    curr_value = my_txm.my_awesome_pv
    # Set the value
    # Equivalent of epics.PV('cryptic:pv:string').put(2.718, wait=True)
    my_txm.my_awesome_pv = 2.718

The advantage here is that boilerplate, such as type-casting and
blocking, can be defined once then forgotten. This approach also lets
you define PVs that should not be changed when the B-hutch is being
operated, by passing ``permit_required=True`` to the TxmPV
constructor. :ref:`More on this below <permits>`.

.. _wait_pvs:

Waiting on Process Variables
----------------------------

Sometimes it is necessary to set one PV then wait on a different PV to
confirm the new value. The :py:meth:`tomo.32id.txm.TXM.wait_pv` method
will poll a specified PV until it reaches its target value. It accepts
the *attribute name* of a PV, not the actual PV name itself. It may be
necessary to use the ``wait=False`` argument on the first PV to avoid
blocking forever:

.. code:: python

   class MyTXM(TXM):
       motor_pv = TxmPV('txm:motorA', wait=False
       sensor_pv = TxmPV('txm:sensorA')


   txm = MyTXM()
   # First set the actuator to the desired value
   new_position = 3.
   txm.motor_pv = new_position
   # This will block until the sensor reaches the target value
   tmx.wait_pv('sensor_pv', new_position)


Waiting on Multiple Process Variables
-------------------------------------

.. warning::

   This feature should be considered experimental. It has been know to
   break during some operations, most notably setting the undulator
   gap.

By default, calling the :py:meth:`~tomo.32id.txm.TXM.pv_put` method
will block execution until the ``put`` call has completed. This means
that setting several PVs becomes a serial operation. This is the
safest approach but is unnecessary in many situations. For example,
setting the x, y and z stage positions can be done simultaneously. You
can always use ``wait=False`` and handle the blocking yourself,
however this is not always straight-forward and may involve messy
callbacks. Using the :py:meth:`~tomo.32id.txm.TXM.wait_pvs` context
manager takes care of this. Any PVs that are set inside the context
will move immediately; if ``block=True`` (default) the manager will
wait for them to finish before leaving the context.

.. code:: python

    txm = TXM()

    # These move one at a time
    txm.Motor_SampleY = 5
    txm.Motor_SampleZ = 3

    # This waits while both motors move simultaneously
    with txm.wait_pvs():
        txm.Motor_SampleY = 8
	txm.Motor_SampleZ = 9

    # These move in the background without blocking
    with txm.wait_pvs(block=False):
        txm.Motor_SampleY = 3
	txm.Motor_SampleZ = 12

This table describes whether if and when a process variable blocks the
execution of python code and waits for the PV to achieve its target
value:

+---------------------------------+-----------------------+------------------------+
| Context manager                 | ``pv_put(wait=True)`` | ``pv_put(wait=False)`` |
+=================================+=======================+========================+
| No context                      | Blocks now            | No blocking            |
+---------------------------------+-----------------------+------------------------+
| ``TXM().wait_pvs``              | Blocks later          | No blocking            |
+---------------------------------+-----------------------+------------------------+
| ``TXM().wait_pvs(block=False)`` | No blocking           | No blocking            |
+---------------------------------+-----------------------+------------------------+

.. _permits:

Locking Shutter Permits
-----------------------

Sometimes it's desireable to test portions of the codebase during
downtime while the B-hutch is operating. In order to do this, however,
it's important to ensure that the shutters, undulator and
monochromator are not changed. Using the
:py:class:`~tomo.32id.txm_pv.TxmPV` descriptors makes this easy: any
PV's that should not be changed can be given the
``permit_required=True`` argument to their constructor:

.. code:: python

   class MyTXM(TXM):
       SHUTTER_OPEN = 1
       my_shutter = TxmPV('32idc:shutter', permit_required=True)
       
       def open_shutter(self):
           """Opens the shutter so we can science!"""
           self.my_shutter = self.SHUTTER_OPEN
   

   # This will not do anything
   my_txm = MyTXM()
   my_txm.open_shutter()

   # This will control the PV as expected
   my_txm = MyTXM(has_permit=True)
   my_txm.open_shutter()

.. note::

   There is no check that the C-hutch actually *has* permission to
   open the shutter, etc. It's controlled only by the ``has_permit``
   argument given to the :py:class:`~aps_32id.txm.TXM`
   constructor. Please be considerate.

Fast Shutter
------------

The instrument is equipped with a "fast shutter" than protects the
specimen from excessive X-ray exposure. Calling
:py:meth:`~aps_32id.txm.TXM.enable_fast_shutter` turns this feature
on. If using the :py:meth:`~aps_32id.txm.TXM.run_scan` context manager
(recommended), the fast shutter is automatically disabled, otherwise
the :py:meth:`~aps_32id.txm.TXM.disable_fast_shutter` method should be
called to return to normal behavior. The fast shutter respects
:py:meth:`~aps_32id.txm.TXM.exposure_time` attribute.

.. _submit an issue: https://github.com/tomography/scanscripts/issues
