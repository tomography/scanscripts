scanscripts
###########

Experiment scanning scripts at APS

This **scanscripts** contains the scripts used at various APS beamlines to collect data.

Documentation
=============

http://scanscripts.readthedocs.io/en/latest/


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

* Publish your  to **scanscripts**  beamline scan scripts to **scanscripts**::

	git add my_beamline
	git commit -m "first commit"
	git push origin master




