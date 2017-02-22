#!/APSshare/epd/rh5-x86/bin/python
'''
This is for X-piezo scan (stage coordinates) and Y-combined (stage coordinates) batch flyscan with different sample_Z postions.

The max scan width in X direction is 80 um.

'''
import epics
from epics import caput, caget
from epics import PV
import time
import numpy as np
import pdb

'''
please enter the scan prameters below:
scans [x-center(um) y-center.(um), z-position (um), x-width.(um), y-width.(um), x-stepsize.(um), Y-stepsize.(um), dwell.(ms)]
'''
caput('9idbTAU:SM:Ps:xyDiffMotion.VAL', 1)

scans = [[482.3,-2131.6,247.5,10,10,0.02,0.02,50],
         [482.3,-2131.6,247.5,10,10,0.02,0.02,50],
         [482.3,-2131.6,247.5,12,12,0.02,0.02,50]
        ]
        
# add some lines to check the beam alignment
                 
pvs = ['9idbTAU:SM:PX:RqsPos', '9idbTAU:SY:PY:RqsPos', '9idbTAU:SM:SZ:RqsPos', '9idbBNP:scan1.P1WD', '9idbBNP:scan2.P1WD', '9idbBNP:scan1.P1SI', '9idbBNP:scan2.P1SI', '9idbBNP:scanTran3.C PP']

sm_px_RqsPos=PV('9idbTAU:SM:PX:RqsPos')
sm_px_ActPos=PV('9idbTAU:SM:PX:ActPos') 
sm_py_RqsPos=PV('9idbTAU:SY:PY:RqsPos') 
sm_py_ActPos=PV('9idbTAU:SY:PY:ActPos')


print 'Batchscan starts'

for batch_num, scan in enumerate(scans):
        #pdb.set_trace()
	print 'changing XY scan mode to combined motion'
	caput('9idbTAU:SM:Ps:xMotionChoice.VAL', 0)  #0: Stepper+piezo, 1: stepper only, 2: piezo only
        time.sleep(2.)
	caput('9idbTAU:SY:Ps:yMotionChoice.VAL', 0)
	time.sleep(2.)

	#print 'scan #{0:d} starts'.format(batch_num)
	print 'entering scan parameters for scan #{0:d}'.format(batch_num+1)
	for i, pvs1 in enumerate(pvs):
		#print 'Setting %s' %pvs1 
		caput(pvs1, scans[batch_num][i])
		time.sleep(1.)

        # check whether the motors have moved to the requested position 
	print 'checking whether motors are in position'
    	ready=abs(sm_px_ActPos.get()-sm_px_RqsPos.get())<0.1 and abs(sm_py_ActPos.get()-sm_py_RqsPos.get())<0.1 
    	while not ready:
        	print '\t Motors are not ready'
        	sm_px_RqsPos.put(sm_px_RqsPos.get())
        	sm_py_RqsPos.put(sm_py_RqsPos.get())
        	time.sleep(3.)
        	ready=abs(sm_px_ActPos.get()-sm_px_RqsPos.get())<0.1 and abs(sm_py_ActPos.get()-sm_py_RqsPos.get())<0.1 
    	print '\t Motors are ready now!'

        print 'setting the current position as the center of the scan'
	caput('9idbBNP:aoRecord11.PROC', 1)
	time.sleep(3.)
	caput('9idbBNP:aoRecord12.PROC', 1)
	time.sleep(3.)
	
	print 'changing X scan mode to Piezo only'
	caput('9idbTAU:SM:Ps:xMotionChoice.VAL', 2)
        time.sleep(3.)

        print 'centering piezoX and piezoY'
	caput('9idbTAU:SM:Ps:xCenter.PROC', 1)
	time.sleep(3.)
	caput('9idbTAU:SY:Ps:yCenter.PROC', 1)
	time.sleep(3.)
	caput('9idbTAU:SM:Ps:xCenter.PROC', 1)
	time.sleep(3.)
	caput('9idbTAU:SY:Ps:yCenter.PROC', 1)
	time.sleep(3.)
	
	caput('9idbBNP:scan2.EXSC', 1)
	time.sleep(1.)
	done = False
	print 'Checking every 10 sec for scan to complete'
	
	while not done:
     		done = caget('9idbBNP:scan2.EXSC')==0
		print '\t Batch {0:d}/{1:d} scan is ongoging'.format(batch_num+1,len(scans))
     		time.sleep(10.)


print 'Completeted. Congratulations!'
caput('9idbTAU:SM:Ps:xMotionChoice.VAL', 0)
caput('9idbTAU:SM:Ps:xyDiffMotion.VAL', 0)
raw_input("Press Enter to exit")


