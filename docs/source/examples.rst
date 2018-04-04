========
Examples
========

Sector 32-ID-C
==============

An template TXM script is show below. It doesn't actually collect any
data, but it does set up the TXM, open the shutters, close them again,
and tear down the TXM. The ``variableDict`` describes the parameters
that are presented to the user in the GUI when running this script. In
the example below, Several actions take place within a
:py:meth:`~aps_32id.txm.NanoTXM.run_scan` context manager. This
ensures that the current configuration is restored after the scan.

.. literalinclude:: examples/my_aps32_script.py
