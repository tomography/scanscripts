=======
Install
=======

This section covers the basics of how to download and install 
`ScanScripts <https://github.com/tomography/scanscripts>`_.We recommend you 
to install the `Anaconda Python <http://continuum.io/downloads>`_
distribution.

.. contents:: Contents:
   :local:


Installing from source
======================
  
Clone the 
`ScanScripts <https://github.com/tomography/scanscripts>`_  
from `GitHub <https://github.com>`_ repository::

    git clone https://github.com/tomography/scanscripts.git project

then::

    cd project
    python setup.py install
    
Beamline Configuration
======================

The scanscripts library looks for a file in the top director (eg
``~/TXM/scanscripts``) called ``beamline_config.conf``. This file
should contain configuration details for how the beamline is
setup. This allows easy configuration changes without having to modify
library code. See the documentation for each beamline for more details
on which options are supported:

- :ref:`sector-32-config`
