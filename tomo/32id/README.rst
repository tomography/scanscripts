Sector 32-ID-C Microscope
=========================

These scripts control the X-Ray Microscope at APS 32-ID-C. They also
make use of the TXM() class for controlling the microscope. This class
exposes process variables as attributes and has some methods for
common control tasks.
<<<<<<< HEAD
=======

Deferred PV's
-------------

It is sometimes desirable to move multiple process variables (PV's)
simultaneously, especially if they take a long time. By default,
updating the value of a PV is a blocking operation, which means that
setting several PVs becomes a serial operation. Using the
``TXM.wait_pvs()`` context manager allows for this to become a
concurrent operation

.. code:: python

    txm = TXM()

    # These move one at a time
    txm.Motor_SampleY = 5
    txm.Motor_SampleZ = 3

    # These move simultaneously
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

+--------------+-------------+------------------+----------------------+
| TxmPV(wait=) | No context  | Blocking context | Non-blocking context |
+==============+=============+==================+======================+
| wait=True    | Blocks now  | Blocks later     | No blocking          |
+--------------+-------------+------------------+----------------------+
| wait=False   | No blocking | No blocking      | No blocking          |
+--------------+-------------+------------------+----------------------+
>>>>>>> wolfman-devel
