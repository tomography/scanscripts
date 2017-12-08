scanscripts
###########

Experiment scanning scripts at APS.

.. image:: https://travis-ci.org/tomography/scanscripts.svg?branch=master
   :target: https://travis-ci.org/tomography/scanscripts
   :alt: Build status	    

.. image:: https://readthedocs.org/projects/scanscripts/badge/?version=latest
   :target: http://scanscripts.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation status


This **scanscripts** library contains the scripts used at various APS
beamlines to collect data.

Documentation
=============

http://scanscripts.readthedocs.io/en/latest/


Project Structure
=================

``scanlib`` contains the classes common to all beamlines.

``aps_*`` folders contain beamline-specific libraries, and a ``run``
folder with runnable scripts for that beamline.

``docs`` and ``tests`` contain documentation and tests.


Installation
============

.. code:: bash

   $ git clone https://github.com/tomography/scanscripts.git
   $ pip install -e scanscripts
   $ pytest # To run tests


How to add your beamline scripts
================================

* Clone **scanscripts** to your machine::

  git clone https://github.com/tomography/scanscripts.git
    

* Add your beamline scan scripts to **scanscripts**::     
	
  cd scanscripts
  mkdir my_beamline
  cp path/my_beamline_script.py to my_beamline
  ...
  ...

* Publish your beamline scan scripts to **scanscripts**::

   git add my_beamline
   git commit -m "added my_beamline_script.py"
   git push origin master
