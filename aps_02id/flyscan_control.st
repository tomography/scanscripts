program flyscan_control

option +s;

%%#include <stdlib.h>
%%#include <string.h>
%%#include <math.h>

/*%%#include <cadef.h>
%%#include <pv.h>*/

#define NONE 0
#define NETCDF 1

#define XMAP 0
#define IP330 1
#define STRUCK_MCA 2

#define DONE 0
#define BUSY 1

#define BEFORE_OUTER 1
#define BEFORE_INNER 2
#define AFTER_INNER 3
#define AFTER_OUTER 4
#define RESET_DONE 5
#define SCAN_IN_PROGRESS 6

#define FALSE 0
#define TRUE 1

#define MAX_DETECTORS 6
#define MAX_PLUGINS 6

/*******************************************************************/
/* These variables are assigned to PVs located in flyscan_setup.db */

int initializeAll;
assign initializeAll to "{P}Flyscans:Setup:Initialize.VAL";
monitor initializeAll;

string innerScanRec;
assign innerScanRec to "{P}Flyscans:Setup:InnerScanRec.VAL";

string outerScanRec;
assign outerScanRec to "{P}Flyscans:Setup:OuterScanRec.VAL";

string fastPositioner;
assign fastPositioner to "{P}Flyscans:Setup:FastPositioner.VAL";

float fastPositionerMinBaseVel;
assign fastPositionerMinBaseVel to "{P}Flyscans:Setup:MinBaseVel.VAL";
monitor fastPositionerMinBaseVel;

string scaler;
assign scaler to "{P}Flyscans:Setup:Scaler.VAL";

int useXmap;
assign useXmap to "{P}Flyscans:Setup:UseXMAP.VAL";

int useSis3820;
assign useSis3820 to "{P}Flyscans:Setup:Use3820.VAL";

int useIp330;
assign useIp330 to "{P}Flyscans:Setup:UseIP330.VAL";

int useNetCDF;
assign useNetCDF to "{P}Flyscans:Setup:UseNetCDF.VAL";

float dwellTime;
assign dwellTime to "{P}Flyscans:Setup:DwellTime.VAL";
monitor dwellTime;

int innerBeforeBusy;
assign innerBeforeBusy to "{P}Flyscans:Setup:InnerBeforeBusy.VAL";
monitor innerBeforeBusy;

int innerAfterBusy;
assign innerAfterBusy to "{P}Flyscans:Setup:InnerAfterBusy.VAL";
monitor innerAfterBusy;

int outerBeforeBusy;
assign outerBeforeBusy to "{P}Flyscans:Setup:OuterBeforeBusy.VAL";
monitor outerBeforeBusy;

int outerAfterBusy;
assign outerAfterBusy to "{P}Flyscans:Setup:OuterAfterBusy.VAL";
monitor outerAfterBusy;

int allPvsConnected;
assign allPvsConnected to "{P}Flyscans:Setup:PVsConnected.VAL";
monitor allPvsConnected;

int showDebugMessages;
assign showDebugMessages to "{P}Flyscans:Setup:DebugMessages.VAL";
monitor showDebugMessages;

string scanAbortPV;
assign scanAbortPV to "{P}Flyscans:Setup:AbortPV.VAL";

int scanPhase;
assign scanPhase to "{P}Flyscans:Setup:Phase.VAL";
monitor scanPhase;

int reset;
assign reset to "{P}Flyscans:Setup:Reset.VAL";
monitor reset;

float maxDwellTime;
assign maxDwellTime to "{P}Flyscans:Setup:MaxDwellTime.VAL";

float minDwellTime;
assign minDwellTime to "{P}Flyscans:Setup:MinDwellTime.VAL";

float flySpeed;
assign flySpeed to "{P}Flyscans:Setup:FlySpeed.VAL";

float maxVelocity;
assign maxVelocity to "{P}Flyscans:Setup:MaxVelocity.VAL";

string lineTimeString;
assign lineTimeString to "{P}Flyscans:Setup:LineTime.VAL";

string scanTimeString;
assign scanTimeString to "{P}Flyscans:Setup:ScanTime.VAL";

int useEncoder;
assign useEncoder to "{P}Flyscans:Setup:UseEncoder.VAL";

float resetVelocity;
assign resetVelocity to "{P}Flyscans:Setup:ResetVelocity.VAL";

float resetBacklashVel;
assign resetBacklashVel to "{P}Flyscans:Setup:ResetBacklashVel.VAL";

float resetBaseVel;
assign resetBaseVel to "{P}Flyscans:Setup:ResetBaseVel.VAL";

int dwellTimeError;
assign dwellTimeError to "{P}Flyscans:Setup:DwellTimeError.VAL";

int motorType;
assign motorType to "{P}Flyscans:Setup:MotorType.VAL";

string filePrefix;
assign filePrefix to "{P}Flyscans:Setup:FilePrefix.VAL";

string fileSuffix;
assign fileSuffix to "{P}Flyscans:Setup:FileSuffix.VAL";

/*******************************************************************/
/* These variables are used to read in the information needed to   */
/* make all of the necessary calculations.                         */

float innerScanCenterPoint;
assign innerScanCenterPoint to "";

float innerScanStartingPoint;
assign innerScanStartingPoint to "";

float innerScanStepSize;
assign innerScanStepSize to "";
monitor innerScanStepSize;

float innerScanWidth;
assign innerScanWidth to "";
monitor innerScanWidth;

int innerScanNumPoints;
assign innerScanNumPoints to "";

int outerScanNumPoints;
assign outerScanNumPoints to "";
monitor outerScanNumPoints;

int outerScanExecute;
assign outerScanExecute to "";

float fastPositionerAccel;
assign fastPositionerAccel to "";
monitor fastPositionerAccel;

float fastPositionerMaxVel;
assign fastPositionerMaxVel to "";
monitor fastPositionerMaxVel;

float fastPositionerResolution;
assign fastPositionerResolution to "";
monitor fastPositionerResolution;

float fastPositionerValue;
assign fastPositionerValue to "";

float fastPositionerDial;
assign fastPositionerDial to "";

float fastPositionerBaseVel;
assign fastPositionerBaseVel to "";

float fastPositionerBacklashVel;
assign fastPositionerBacklashVel to "";

float fastPositionerVelocity;
assign fastPositionerVelocity to "";

int fastPositionerDone;
assign fastPositionerDone to "";
monitor fastPositionerDone;

/*******************************************************************/
/* These variables are used for motor controller parameters that   */
/* are not stepper motor controllers.                              */

float triggerDelay;
assign triggerDelay to "";

float triggerWidth;
assign triggerWidth to "";

int triggerPolarity;
assign triggerPolarity to "";

int triggerMode;
assign triggerMode to "";

float triggerStart;
assign triggerStart to "";

float triggerEnd;
assign triggerEnd to "";

int numTriggers;
assign numTriggers to "";

int sendParameters;
assign sendParameters to "";

/*******************************************************************/
/* These variables are monitoring the scan records.                */

int scanAbort;
assign scanAbort to "";
monitor scanAbort;

int innerScanBusyField;
assign innerScanBusyField to "";
monitor innerScanBusyField;

int outerScanBusyField;
assign outerScanBusyField to "";
monitor outerScanBusyField;

/*******************************************************************/
/* These variables are for the XMAP signal processor.              */

int xmapNumPixels;
assign xmapNumPixels to "{XMAP}PixelsPerRun";

int xmapPrescale;
assign xmapPrescale to "{XMAP}SyncCount";

int xmapMode;
assign xmapMode to "{XMAP}CollectMode";

int xmapUpdateStatusRate;
assign xmapUpdateStatusRate to "{XMAP}StatusAll.SCAN";

int xmapUpdateDataRate;
assign xmapUpdateDataRate to "{XMAP}ReadAll.SCAN";

int xmapEraseStart;
assign xmapEraseStart to "{XMAP}EraseStart";

int xmapNextPixel;
assign xmapNextPixel to "{XMAP}NextPixel";

int xmapStopAll;
assign xmapStopAll to "{XMAP}StopAll";

float xmapRealTime;
assign xmapRealTime to "{XMAP}PresetReal";

int xmapPixelsPerBuffer;
assign xmapPixelsPerBuffer to "{XMAP}PixelsPerBuffer_RBV";

/*******************************************************************/
/* These variables are for the SIS3820 multi-channel scalar.       */

int sisNumPixels;
assign sisNumPixels to "{SIS}NuseAll";

int sisPrescale;
assign sisPrescale to "{SIS}Prescale";

int sisRealTime;
assign sisRealTime to "{SIS}PresetReal";

/*******************************************************************/
/* These variables are for the IP330 adc.                          */

int ip330NumPixels;
assign ip330NumPixels to "";

int ip330Prescale;
assign ip330Prescale to "";

int ip330RealTime;
assign ip330RealTime to "";

/*******************************************************************/
/* These variables are for the NetCDF file plugin.                 */

string netCDFString1;
assign netCDFString1 to "{P]Flyscans:NetCDF_1:String1.VAL";

string netCDFString2;
assign netCDFString2 to "{P]Flyscans:NetCDF_1:String2.VAL";

string netCDFString3;
assign netCDFString3 to "{P]Flyscans:NetCDF_1:String3.VAL";

string netCDFString4;
assign netCDFString4 to "{P]Flyscans:NetCDF_1:String4.VAL";

string netCDFString5;
assign netCDFString5 to "{P]Flyscans:NetCDF_1:String5.VAL";

string netCDFFilePrefix;
assign netCDFFilePrefix to "{P]Flyscans:NetCDF_1:FilePrefix.VAL";

string netCDFFileSuffix;
assign netCDFFileSuffix to "{P]Flyscans:NetCDF_1:FileSuffix.VAL";

char netCDFFileName[256];
assign netCDFFileName to "{FILE}FileName";

int netCDFFileNumber;
assign netCDFFileNumber to "{FILE}FileNumber";

int netCDFCapture;
assign netCDFCapture to "{FILE}NumCapture";

int nextScan;
assign nextScan to "{P}saveData_scanNumber";

/*******************************************************************/
/* These variables are anonymous PVs                               */

int numAborts;
assign numAborts;
monitor numAborts;

float stepsPerPixel;
assign stepsPerPixel;

int pvFieldsFilled;
assign pvFieldsFilled;

/*******************************************************************/
/* These variables are not tied to any PVs                         */

string pvName;

evflag fastPositionerDoneFlag;

evflag scanAbortedFlag;
evflag dwellTimeSetFlag;
evflag fastPositionerAccelSetFlag;
evflag fastPositionerMaxVelSetFlag;
evflag fastPositionerMinBaseVelSetFlag;
evflag fastPositionerResolutionSetFlag;
evflag innerScanStepSizeSetFlag;
evflag innerScanWidthSetFlag;
evflag outerScanNumPointsSetFlag;
evflag initOnBootFlag;

evflag setXmapToFlyScanFlag;
evflag setXmapToStepScanFlag;
evflag processSIS3820Flag;
evflag processIP330Flag;
evflag processNetCDFFlag;

evflag xmapDoneFlag;
evflag sis3820DoneFlag;
evflag ip330DoneFlag;
evflag netCDFDoneFlag;

sync scanAbort to scanAbortedFlag;
sync dwellTime to dwellTimeSetFlag;
sync fastPositionerAccel to fastPositionerAccelSetFlag;
sync fastPositionerMaxVel to fastPositionerMaxVelSetFlag;
sync fastPositionerMinBaseVel to fastPositionerMinBaseVelSetFlag;
sync fastPositionerResolution to fastPositionerResolutionSetFlag;
sync innerScanStepSize to innerScanStepSizeSetFlag;
sync innerScanWidth to innerScanWidthSetFlag;
sync outerScanNumPoints to outerScanNumPointsSetFlag;

char *iocPrefix;
char *ip330Prefix;

/*******************************************************************/

ss netCDF_control {

	state setNetCDFParameters {
	
		when (efTestAndClear(processNetCDFFlag)) {
		
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setNetCDFParameters: Setting NetCDF parameters.\n");
			
			pvGet(nextScan);
			nextScan = nextScan - 1;
			
			pvGet(netCDFString1);
			pvGet(netCDFString2);
			pvGet(netCDFString3);
			pvGet(netCDFString4);
			pvGet(netCDFString5);
			
			pvGet(filePrefix);
			pvGet(fileSuffix);
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setNetCDFParameters: File prefix and suffix:%s, %s.\n", filePrefix, fileSuffix);
			
			if (strlen(netCDFString2))
				strcat(netCDFString1, netCDFString2);
		
			if (strlen(netCDFString3))
				strcat(netCDFString1, netCDFString3);
		
			if (strlen(netCDFString4))
				strcat(netCDFString1, netCDFString4);
		
			if (strlen(netCDFString5))
				strcat(netCDFString1, netCDFString5);
				
			sprintf(netCDFFileName, "%s_%.4d_%s%s", filePrefix, nextScan, fileSuffix, netCDFString1);
		
			netCDFFileNumber = 0;
				
			pvGet(innerScanNumPoints);
			pvGet(xmapPixelsPerBuffer);
			
			netCDFCapture = (ceil((float) innerScanNumPoints / (float) xmapPixelsPerBuffer));
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setNetCDFParameters: Setting number of buffers to capture to %d.\n", netCDFCapture);
				
			pvPut(netCDFFileNumber);	
			pvPut(netCDFCapture);
			pvPut(netCDFFileName);
			
			efSet(netCDFDoneFlag);
		
		} state setNetCDFParameters
	}
}

ss ip330_control {

	state setIp330Parameters {
	
		when (efTestAndClear(processIP330Flag)) {
		
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setIp330Parameters: Setting IP330 parameters.\n");
		
			pvGet(innerScanNumPoints);
			pvGet(stepsPerPixel);
			
			ip330RealTime = 0.0;
			ip330NumPixels = innerScanNumPoints - 2;
			ip330Prescale = stepsPerPixel;
			
			pvPut(ip330RealTime);
			pvPut(ip330NumPixels);
			pvPut(ip330Prescale);
			
			efSet(ip330DoneFlag);
		
		} state setIp330Parameters
		
	}
}

ss sis3820_control {

	state setSisParameters {
	
		when (efTestAndClear(processSIS3820Flag)) {
		
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setSisParameters: Setting SIS3820 parameters.\n");
		
			pvGet(innerScanNumPoints);
			pvGet(stepsPerPixel);
			
			sisRealTime = 0.0;
			sisNumPixels = innerScanNumPoints - 2;
			sisPrescale = stepsPerPixel;
			
			pvPut(sisRealTime);
			pvPut(sisNumPixels);
			pvPut(sisPrescale);
			
			efSet(sis3820DoneFlag);
		
		} state setSisParameters
		
	}
}

ss xmap_control {

	state setXmapMode {
	
		when (efTestAndClear(setXmapToFlyScanFlag)) {
		
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setXmapMode: Setting XMAP to MCA mapping mode.\n");
		
			xmapMode = 1; /* Set to mapping mode */
			pvPut(xmapMode, SYNC);
			
		} state setXmapFlyParameters
		
		when (efTestAndClear(setXmapToStepScanFlag)) {
		
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setXmapMode: Setting XMAP to MCA spectra mode.\n");
		
			xmapMode = 0; /* Set to spectra mode */
			pvPut(xmapMode, SYNC);
			
		}state setXmapStepParameters
	}

	state setXmapFlyParameters {
	
		when (delay(2.0)) {
			
			pvGet(innerScanNumPoints);
			pvGet(stepsPerPixel);
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setXmapMode: Setting XMAP pixels and scan rates.\n");
			
			xmapRealTime = 0.0;
			xmapNumPixels = innerScanNumPoints - 2;
			xmapPrescale = 1;
			xmapUpdateStatusRate = 0; /* Set to passive scan rate */
			xmapUpdateDataRate = 0;
			xmapEraseStart = 1;
			
			pvPut(xmapRealTime);
			pvPut(xmapNumPixels);
			pvPut(xmapPrescale);
			pvPut(xmapUpdateStatusRate);
			pvPut(xmapUpdateDataRate);
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setXmapMode: Acquiring one pixel.\n");
				
			pvPut(xmapEraseStart);
			
			xmapNextPixel = 1;
			pvPut(xmapNextPixel, SYNC);
			
			xmapStopAll = 1;
			pvPut(xmapStopAll);
			
			pvGet(useNetCDF);
			if (useNetCDF)
				efSet(processNetCDFFlag);
			else
				efSet(netCDFDoneFlag);
			
			efSet(xmapDoneFlag);			
		
		} state setXmapMode
	}
	
	state setXmapStepParameters {
	
		when (delay(1.0)) {
		
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state setXmapMode: Setting XMAP scan rates to 0.2 seconds.\n");
		
			xmapUpdateStatusRate = 8; /* Set to .2 second scan rate */
			xmapUpdateDataRate = 8;
			
			pvPut(xmapUpdateStatusRate);
			pvPut(xmapUpdateDataRate);
			
			efSet(xmapDoneFlag);
			
		} state setXmapMode
	}
}

ss initialize_variables {

	int initLoop;

	state on_boot {

		when () {
		
			if (showDebugMessages > 0)
			{
				printf("\nFlyscan message: state on_boot: Starting flyscan program.\n");
			}
			
			allPvsConnected = FALSE;
			pvPut(allPvsConnected);
			
			numAborts = 0;
			pvPut(numAborts);
										
			efSet(initOnBootFlag);
			
		} state init

	}

	state init {
	
		entry {
		
			if (showDebugMessages > 1)
			{
				printf("\nFlyscan message: state init: Entering init state.\n");
			}
		
		}

		when (initializeAll || efTestAndClear(initOnBootFlag)) {
		
			if (showDebugMessages > 1)
			{
				printf("\nFlyscan message: state init: Beginning initialization.\n");
			}

			initializeAll = 0;
			
			pvFieldsFilled = 0;
			pvPut(pvFieldsFilled);
			
			/* Get all of the information that the user entered */
			/* in the setup screen.								*/

			pvGet(innerScanRec);
			pvGet(outerScanRec);
			pvGet(scaler);
			pvGet(dwellTime);
			pvGet(fastPositioner);
			pvGet(scanAbortPV);
			pvGet(useEncoder);
			pvGet(resetVelocity);
			pvGet(motorType);
			
			if ((strlen(innerScanRec) > 0) && (strlen(outerScanRec) > 0) && 
			    (strlen(fastPositioner) > 0) && (strlen(scanAbortPV) > 0) && (resetVelocity != 0))	
			{

				/* Use the above information to connect variables to */
	         	/* scan record and positioner PVs.                   */

				if (showDebugMessages > 1)
					printf("\nFlyscan message: state init: Initializing scan record and positioner variables.\n");
				
				/* If using the Hydra controller from PI, connect to the PVs needed to set up the 
				   detector triggers. */	
				if (motorType > 0)
				{
				   sprintf(pvName, "%sHydra1:Delay.VAL", iocPrefix);
					pvAssign(triggerDelay, pvName);
					
					sprintf(pvName, "%sHydra1:Width.VAL", iocPrefix);
					pvAssign(triggerWidth, pvName);
					
					sprintf(pvName, "%sHydra1:Polarity.VAL", iocPrefix);
					pvAssign(triggerPolarity, pvName);
					
					sprintf(pvName, "%sHydra1:Mode.VAL", iocPrefix);
					pvAssign(triggerMode, pvName);
					
					sprintf(pvName, "%sHydra1:StartPosition.VAL", iocPrefix);
					pvAssign(triggerStart, pvName);
					
					sprintf(pvName, "%sHydra1:EndPosition.VAL", iocPrefix);
					pvAssign(triggerEnd, pvName);
					
					sprintf(pvName, "%sHydra1:NumTriggers.VAL", iocPrefix);
					pvAssign(numTriggers, pvName);	
					
					sprintf(pvName, "%sHydra1:StartStopCalc.PROC", iocPrefix);
					pvAssign(sendParameters, pvName);					
				}
				
				/* Connect to the scan record PVs. */
				sprintf(pvName, "%s.P1CP", innerScanRec);
				pvAssign(innerScanCenterPoint, pvName);

				sprintf(pvName, "%s.P1SP", innerScanRec);
				pvAssign(innerScanStartingPoint, pvName);

				pvStopMonitor(innerScanStepSize);
				sprintf(pvName, "%s.P1SI", innerScanRec);
				pvAssign(innerScanStepSize, pvName);
				pvMonitor(innerScanStepSize);

				pvStopMonitor(innerScanWidth);
				sprintf(pvName, "%s.P1WD", innerScanRec);
				pvAssign(innerScanWidth, pvName);
				pvMonitor(innerScanWidth);

				sprintf(pvName, "%s.NPTS", innerScanRec);
				pvAssign(innerScanNumPoints, pvName);

				sprintf(pvName, "%s.EXSC", outerScanRec);
				pvAssign(outerScanExecute, pvName);

				pvStopMonitor(outerScanNumPoints);
				sprintf(pvName, "%s.NPTS", outerScanRec);
				pvAssign(outerScanNumPoints, pvName);
				pvMonitor(outerScanNumPoints);
				
				pvStopMonitor(scanAbort);
				sprintf(pvName, "%s", scanAbortPV);
				pvAssign(scanAbort, pvName);
				pvMonitor(scanAbort);
			
				pvStopMonitor(innerScanBusyField);
				sprintf(pvName, "%s.BUSY", innerScanRec);
				pvAssign(innerScanBusyField, pvName);
				pvMonitor(innerScanBusyField);
			
				pvStopMonitor(outerScanBusyField);
				sprintf(pvName, "%s.BUSY", outerScanRec);
				pvAssign(outerScanBusyField, pvName);
				pvMonitor(outerScanBusyField);
				
				/* Connect to the fly motor PVs. */
				pvStopMonitor(fastPositionerAccel);
				sprintf(pvName, "%s.ACCL", fastPositioner);
				pvAssign(fastPositionerAccel, pvName);
				pvMonitor(fastPositionerAccel);

				pvStopMonitor(fastPositionerMaxVel);
				sprintf(pvName, "%s.VMAX", fastPositioner);
				pvAssign(fastPositionerMaxVel, pvName);
				pvMonitor(fastPositionerMaxVel);
				
				pvStopMonitor(fastPositionerResolution);
				
				if (useEncoder)
					sprintf(pvName, "%s.ERES", fastPositioner);
				else
					sprintf(pvName, "%s.MRES", fastPositioner);
				
				pvAssign(fastPositionerResolution, pvName);
				pvMonitor(fastPositionerResolution);

				sprintf(pvName, "%s.VAL", fastPositioner);
				pvAssign(fastPositionerValue, pvName);
				
				sprintf(pvName, "%s.DVAL", fastPositioner);
				pvAssign(fastPositionerDial, pvName);

				sprintf(pvName, "%s.VBAS", fastPositioner);
				pvAssign(fastPositionerBaseVel, pvName);

				sprintf(pvName, "%s.BVEL", fastPositioner);
				pvAssign(fastPositionerBacklashVel, pvName);

				sprintf(pvName, "%s.VELO", fastPositioner);
				pvAssign(fastPositionerVelocity, pvName);
				
				pvStopMonitor(fastPositionerDone);
				sprintf(pvName, "%s.DMOV", fastPositioner);
				pvAssign(fastPositionerDone, pvName);
				pvMonitor(fastPositionerDone);
				
				pvGet(useIp330);
				if (useIp330)
				{
					ip330Prefix = macValueGet("IP330");
					
					sprintf(pvName, "%sNuseAll", ip330Prefix);
					pvAssign(ip330NumPixels, pvName);
					
					sprintf(pvName, "%sPrescale", ip330Prefix);
					pvAssign(ip330Prescale, pvName);
					
					sprintf(pvName, "%sPresetReal", ip330Prefix);
					pvAssign(ip330RealTime, pvName);
				}
				
				pvFieldsFilled = 1;
				pvPut(pvFieldsFilled);
			
			}

		} state pvs_connecting
	}
	
	state pvs_connecting {
	
		entry {
		
			if (showDebugMessages > 1)
			{
				printf("\nFlyscan message: state pvs_connecting: Entering pvs_connecting state.\n");
			}
		}
	
		when (pvConnectCount() == pvAssignCount()) {
		
			if (showDebugMessages > 1)
			{
				printf("\nFlyscan message: state pvs_connecting: pvConnectCount==pvAssignCount.\n");
			}
			
			/* Set initial values for some variables. */
			scanPhase = 0;
			pvPut(scanPhase);
			
			if (pvFieldsFilled)
			{
				if (showDebugMessages > 1)
				{
					printf("\nFlyscan message: state pvs_connecting: Setting allPvsConnected=TRUE.\n");
				}
				
				allPvsConnected = TRUE;
				pvPut(allPvsConnected);
			
				efSet (dwellTimeSetFlag);
			}
						
		} state init
		
		when (delay(5)) {
		
			if (showDebugMessages > 1)
			{
				printf("\nFlyscan message: state pvs_connecting: All PVs did not connect.\n");
			}
		
		} state init
	}
}

ss calculate_time_and_speed {

	float stepsPerPixelMax;
	float stepsPerPixelMin;
	float lineTime;
	float scanTime;
	float hours;
	float minutes;
	float seconds;

	state calc_time_speed {
	
		when ((efTestAndClear(dwellTimeSetFlag) || efTestAndClear(outerScanNumPointsSetFlag) || efTestAndClear(fastPositionerAccelSetFlag)
			 || efTestAndClear(fastPositionerResolutionSetFlag) || efTestAndClear(innerScanStepSizeSetFlag) || efTestAndClear(fastPositionerMinBaseVelSetFlag)
			 || efTestAndClear(fastPositionerMaxVelSetFlag) || efTestAndClear(innerScanWidthSetFlag)) && allPvsConnected) {
		
			/* Calculate the number of steps per pixel.  Before rounding, add a small amount so
			 * that 3.9999 does not become 3 instead of 4. */
			stepsPerPixel = floor(fabs(innerScanStepSize / fastPositionerResolution) + 0.0001);
			pvPut(stepsPerPixel);
			
			if (showDebugMessages > 4)
			{
				printf("\nFlyscan message: state calc_time_speed: Positioner resolution is %f.\n", fastPositionerResolution);
				printf("\nFlyscan message: state calc_time_speed: Positioner minimum speed is %f.\n", fastPositionerMinBaseVel);
				printf("\nFlyscan message: state calc_time_speed: Positioner maximum speed is %f.\n", fastPositionerMaxVel);
				printf("\nFlyscan message: state calc_time_speed: Fast scan width is %f.\n", innerScanWidth);
				printf("\nFlyscan message: state calc_time_speed: Slow scan number of points is %d.\n", outerScanNumPoints);
			}
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state calc_time_speed: Calculated %f steps per pixel.\n", stepsPerPixel);
			
			
			maxDwellTime = (stepsPerPixel * (fastPositionerResolution / fastPositionerMinBaseVel)) * 1000;
			pvPut(maxDwellTime);
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state calc_time_speed: Calculated maximum dwell time of %f.\n", maxDwellTime);
			
			minDwellTime = (stepsPerPixel * (fastPositionerResolution / fastPositionerMaxVel)) * 1000;
			pvPut(minDwellTime);
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state calc_time_speed: Calculated minimum dwell time of %f.\n", minDwellTime);
				
			if ((dwellTime > maxDwellTime) || (dwellTime < minDwellTime))
				dwellTimeError = 1;
			else
				dwellTimeError = 0;
				
			pvPut(dwellTimeError);
			
			flySpeed = (stepsPerPixel * (fastPositionerResolution / dwellTime)) * 1000;
			pvPut(flySpeed);
			
			maxVelocity = fastPositionerMaxVel;
			pvPut(maxVelocity);
			
			lineTime = (fabs(innerScanWidth) / flySpeed) + ((fabs(innerScanWidth) / 2) / fastPositionerMaxVel) + (2 * fastPositionerAccel) + 1.3;
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state calc_time_speed: Calculated line time of %f.\n", lineTime);

			/* The total scan time is the time for a line times the number of lines that will be done.
			 * There is also a small constant of 2 seconds to account for the before and after scan
			 * processing, as well as a fraction of a second for each motion of the outer scan motor.
			 */
			scanTime = ((lineTime + (fabs(innerScanWidth) / fastPositionerMaxVel)) * outerScanNumPoints) + (2 + (outerScanNumPoints * 0.3));
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state calc_time_speed: Calculated scan time of %f.\n", scanTime);
				
			hours = 0;
			minutes = 0;
			seconds = 0;
			
			/* Calculate the number hours, minutes, and seconds it will take to complete the scan line. */
			if (lineTime > 3600.0)
			{
				hours = floor(lineTime / 3600.0);
				lineTime = (lineTime - (hours * 3600.0));
			}

			if (lineTime > 60.0)
			{
				minutes = floor(lineTime / 60.0);
				lineTime = (lineTime - (minutes * 60.0));
			}

			seconds = lineTime;

			sprintf(lineTimeString, "%.0fhrs %.0fmin %.1fsec", hours, minutes, seconds);
			pvPut(lineTimeString);
			
			hours = 0;
			minutes = 0;
			seconds = 0;
						
			/* Calculate the number hours, minutes, and seconds it will take to complete the entire scan. */
			if (scanTime > 3600.0)
			{
				hours = floor(scanTime / 3600.0);
				scanTime = (scanTime - (hours * 3600.0));
			}
			
			if (scanTime > 60.0)
			{
				minutes = floor(scanTime / 60.0);
				scanTime = (scanTime - (minutes * 60.0));
			}
			
			seconds = scanTime;

			sprintf(scanTimeString, "%.0fhrs %.0fmin %.1fsec", hours, minutes, seconds);
			pvPut(scanTimeString);
			
		} state calc_time_speed
	}
}

ss monitor_scan_abort {

	state count_aborted {
	
		when (efTestAndClear(scanAbortedFlag)) {
		
			numAborts = numAborts + 1;
			
			if (numAborts == 4)
				numAborts = 0;
				
			pvPut(numAborts);
			
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state count_aborted: Abort scan processed %d times.\n", numAborts);
			
		} state count_aborted
		
		when ((numAborts > 0) && (outerScanBusyField == 0)) {
		
			numAborts = 0;
			
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state count_aborted: Abort count reset to zero.\n");
			
		} state count_aborted
	}
}

/* This state set looks to see if a scan was aborted without the after scan
 * PV being processed.  If that was the case, then make sure that those
 * actions occur. */
ss scan_cleanup {

	state scan_aborted {

		when ((allPvsConnected == TRUE) && (outerBeforeBusy == 1) && (outerScanBusyField == 0) && ((numAborts > 1) || (reset == 1))) {
		
			reset = 0;
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state scan_aborted: Initiating cleanup procedure while in BEFORE_OUTER_SCAN state.\n");
		
		} state wait_for_outer_before_busy
		
		
		when ((allPvsConnected == TRUE) && (innerBeforeBusy == 1) && (innerScanBusyField == 0) && ((numAborts > 1) || (reset == 1))) {
		
			reset = 0;
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state scan_aborted: Initiating cleanup procedure while in BEFORE_INNER_SCAN state.\n");
		
		} state wait_for_inner_before_busy
		
		when ((allPvsConnected == TRUE) && (scanPhase == SCAN_IN_PROGRESS) && (innerScanBusyField == 0) && ((numAborts > 1) || (reset == 1))) {
		
			reset = 0;
			innerAfterBusy = 1;
			pvPut(innerAfterBusy);
			
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state scan_aborted: Initiating cleanup procedure while in SCAN_IN_PROGRESS state.\n");
			
		} state wait_for_inner_after_busy
		
		when ((allPvsConnected == TRUE) && (innerAfterBusy == 1) && (innerScanBusyField == 0) && ((numAborts > 1) || (reset == 1))) {
		
			reset = 0;
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state scan_aborted: Initiating cleanup procedure while in AFTER_INNER_SCAN state.\n");
		
		} state wait_for_inner_after_busy
		
	}
	
	state wait_for_outer_before_busy {
	
		when (outerBeforeBusy == 0) {
		
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state wait_for_outer_before_busy: BEFORE_OUTER_SCAN complete, initiating AFTER_OUTER_SCAN.\n");
		
			outerAfterBusy = 1;
			pvPut(outerAfterBusy);
			
		} state wait_for_outer_after_busy
		
		when (delay(5.0)) {
		
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state wait_for_outer_before_busy: WARNING!! BEFORE_OUTER_SCAN did not complete, initiating AFTER_OUTER_SCAN.\n");
				
			outerBeforeBusy = 0;
			pvPut(outerBeforeBusy);
		
			outerAfterBusy = 1;
			pvPut(outerAfterBusy);
			
		} state wait_for_outer_after_busy
	}
	
	state wait_for_inner_before_busy {
	
		when (innerBeforeBusy == 0) {
		
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state wait_for_inner_before_busy: BEFORE_INNER_SCAN complete, initiating AFTER_INNER_SCAN.\n");
		
			innerAfterBusy = 1;
			pvPut(innerAfterBusy);
			
		} state wait_for_inner_after_busy
		
		when (delay(5.0)) {
		
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state wait_for_inner_before_busy: WARNING!! BEFORE_INNER_SCAN did not complete, initiating AFTER_INNER_SCAN.\n");
				
			innerBeforeBusy = 0;
			pvPut(innerBeforeBusy);
		
			innerAfterBusy = 1;
			pvPut(innerAfterBusy);
			
		} state wait_for_inner_after_busy
	}
	
	state wait_for_inner_after_busy {
	
		when (innerAfterBusy == 0) {
		
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state wait_for_inner_after_busy: AFTER_INNER_SCAN complete, initiating AFTER_OUTER_SCAN.\n");
				
			outerAfterBusy = 1;
			pvPut(outerAfterBusy);
			
		} state wait_for_outer_after_busy
		
		when (delay(5.0)) {
		
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state wait_for_inner_after_busy: WARNING!! AFTER_INNER_SCAN did not complete, initiating AFTER_OUTER_SCAN.\n");
				
			innerAfterBusy = 0;
			pvPut(innerAfterBusy);
		
			outerAfterBusy = 1;
			pvPut(outerAfterBusy);
			
		} state wait_for_outer_after_busy
	}
	
	state wait_for_outer_after_busy {
	
		when (outerAfterBusy == 0) {
		
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state wait_for_outer_after_busy: AFTER_OUTER_SCAN complete.\n");
		
		} state scan_aborted
		
		when (delay(5.0)) {
		
			if (showDebugMessages > 0)
				printf("\nFlyscan message: state wait_for_inner_after_busy: WARNING!! AFTER_OUTER_SCAN did not complete.\n");
		
			outerAfterBusy = 0;
			pvPut(outerAfterBusy);
			
		} state scan_aborted
	}
}

ss before_inner_scan {

	int innerBeforeLoop;
	float baseSpeed;

	state move_fast_positioner {
	
		when (innerBeforeBusy && allPvsConnected && fastPositionerDone) {
		
			/* Set the value of the phase so that the database processes correctly.*/
			scanPhase = BEFORE_INNER;
			pvPut(scanPhase, SYNC);
			
			/* Send the fast positioner to the starting point of the scan. */
			pvGet(innerScanStartingPoint);			
			fastPositionerValue = innerScanStartingPoint;
			pvPut(fastPositionerValue, ASYNC);
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state move_fast_positioner: Sending fast positioner to %f.\n", innerScanStartingPoint);
			
		} state set_values
	}
	
	state set_values {
	
		when (pvPutComplete(fastPositionerValue) && delay(0.2)) {
				
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state set_values: Setting fast positioner velocities to fly values.\n");
				
			pvGet(motorType);
			 
			 if (motorType > 0)
			 {
			     /* Get some scan values. */
			     pvGet(innerScanStartingPoint);
			     pvGet(innerScanStepSize);
			     pvGet(innerScanWidth);
			     pvGet(innerScanNumPoints);
				  pvGet(fastPositionerDial);
				 
				  /* Calculate trigger parameters. */ 
			     triggerDelay = 0;
				  triggerWidth = 100;
				  triggerPolarity = 0;
				  triggerMode = 1;
				  triggerStart = fastPositionerDial + innerScanStepSize;
				  triggerEnd = fastPositionerDial + innerScanWidth;
				  numTriggers = innerScanNumPoints- 1;

				  sendParameters = 1;
				 
				  pvPut(triggerDelay);
				  pvPut(triggerWidth);
				  pvPut(triggerPolarity);
				  pvPut(triggerMode);
				  pvPut(triggerStart);
				  pvPut(triggerEnd);
				  pvPut(numTriggers);

				  pvPut(sendParameters);
			 }

			pvGet(stepsPerPixel);
			pvGet(flySpeed);
			baseSpeed = flySpeed;	
			/* Take the smaller of the calculated value and the current
			 * fast positioner base speed. */			
			if (baseSpeed > fastPositionerBaseVel)
				baseSpeed = fastPositionerBaseVel;

			/* Take the larger of the calculated base speed and
			 * the user entered minimum base speed. */
			pvGet(fastPositionerMinBaseVel);
			if (baseSpeed < fastPositionerMinBaseVel)
				baseSpeed = fastPositionerMinBaseVel;
				
			if (showDebugMessages > 1)
			{
				printf("\nFlyscan message: state set_values: Using value of %f steps per pixel.\n", stepsPerPixel);
				printf("\nFlyscan message: state set_values: Using value of %f for base speed.\n", baseSpeed);
				printf("\nFlyscan message: state set_values: Using value of %f for fly speed.\n", flySpeed);
			}

			/* Set the fast positioner minimum base speed and
			 * the fly speed. */
			fastPositionerBaseVel = baseSpeed;
			pvPut(fastPositionerBaseVel);
			fastPositionerVelocity = flySpeed;
			pvPut(fastPositionerVelocity);
			fastPositionerBacklashVel = flySpeed;
			pvPut(fastPositionerBacklashVel);
			
			efSet(xmapDoneFlag);
			efSet(sis3820DoneFlag);
			efSet(ip330DoneFlag);
			efSet(netCDFDoneFlag);

		} state inner_before_complete
	}
	
	state inner_before_complete {
	
		when (efTestAndClear(xmapDoneFlag) &&  efTestAndClear(ip330DoneFlag) && efTestAndClear(sis3820DoneFlag) && efTestAndClear(netCDFDoneFlag)) {
		
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state inner_before_complete: Setting phase to SCAN_IN_PROGRESS.\n");

			scanPhase = SCAN_IN_PROGRESS;
			pvPut(scanPhase, SYNC);
			
			innerBeforeBusy = 0;
			pvPut(innerBeforeBusy);
			
		} state move_fast_positioner
	} 
}

ss after_inner_scan {

	int innerAfterLoop;

	state inner_after_scan {

		when (innerAfterBusy && allPvsConnected) {

			scanPhase = AFTER_INNER;
			pvPut(scanPhase, SYNC);
				
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state inner_after_scan: Resetting motor parameters to previous values.\n");
			
			/* Restore motor parameters to prescan values. */
			pvGet(resetVelocity);
			pvGet(resetBacklashVel);
			pvGet(resetBaseVel);
			
			fastPositionerVelocity = resetVelocity;
			fastPositionerBacklashVel = resetBacklashVel;
			fastPositionerBaseVel = resetBaseVel;
			
			pvPut(fastPositionerVelocity);
			pvPut(fastPositionerBacklashVel);
			pvPut(fastPositionerBaseVel);
			
			efSet(xmapDoneFlag);
			efSet(sis3820DoneFlag);
			efSet(ip330DoneFlag);
			efSet(netCDFDoneFlag);

		} state inner_after_complete
	}

	state inner_after_complete {
	
		when (efTestAndClear(xmapDoneFlag) &&  efTestAndClear(ip330DoneFlag) && efTestAndClear(sis3820DoneFlag) && efTestAndClear(netCDFDoneFlag)) {
			
			if (showDebugMessages > 4)
				printf("\nFlyscan message: state inner_after_complete: Setting phase to RESET_DONE.\n");
			
			scanPhase = RESET_DONE;
			pvPut(scanPhase, SYNC);
			
			innerAfterBusy = 0;
			pvPut(innerAfterBusy);
			
		} state inner_after_scan
	}
}

ss before_outer_scan {

	int outerBeforeLoop;

	state outer_before_scan {

		when (outerBeforeBusy && allPvsConnected) {
		
			scanPhase = BEFORE_OUTER;
			pvPut(scanPhase, SYNC);
		
			pvGet(useXmap);
			pvGet(useSis3820);
			pvGet(useIp330);
			pvGet(useNetCDF);
			
			if (useXmap)
				efSet(setXmapToFlyScanFlag);
			else
				efSet(xmapDoneFlag);
				
			if (useSis3820)
				efSet(processSIS3820Flag);
			else
				efSet(sis3820DoneFlag);
				
			if (useIp330)
				efSet(processIP330Flag);
			else
				efSet(ip330DoneFlag);
		
			if (showDebugMessages > 4)
					printf("\nFlyscan message: state outer_before_scan: Before outer scan processing started.\n");
					
		  	/* Use the current value of the fast positioner as the center
			 * point of the inner scan.*/
			pvGet(fastPositionerValue);
			innerScanCenterPoint = fastPositionerValue;
			pvPut(innerScanCenterPoint);
			
		} state outer_before_complete
	}
	
	state outer_before_complete {
	
		when (efTest(xmapDoneFlag) &&  efTest(ip330DoneFlag) && efTest(sis3820DoneFlag) && efTest(netCDFDoneFlag)) {
		
			efClear(xmapDoneFlag);
			efClear(ip330DoneFlag);
			efClear(sis3820DoneFlag);
			efClear(netCDFDoneFlag);
		
			if (showDebugMessages > 4)
					printf("\nFlyscan message: state outer_before_complete: Setting phase to RESET_DONE.\n");
			
			scanPhase = RESET_DONE;
			pvPut(scanPhase, SYNC);
			
			outerBeforeBusy = 0;
			pvPut(outerBeforeBusy);

		} state outer_before_scan
	}
}

ss after_outer_scan {

	int outerAfterLoop;
	
	state outer_after_scan {
	
		when (outerAfterBusy && allPvsConnected) {
		
			scanPhase = AFTER_OUTER;
			pvPut(scanPhase, SYNC);
		
			pvGet(useXmap);
			
			if (useXmap)
				efSet(setXmapToStepScanFlag);
			else
				efSet(xmapDoneFlag);
				
			efSet(sis3820DoneFlag);
			efSet(ip330DoneFlag);
			efSet(netCDFDoneFlag);
		
			pvGet(innerScanCenterPoint);			
			fastPositionerValue = innerScanCenterPoint;
			pvPut(fastPositionerValue, SYNC);
		
		} state outer_after_complete
	}

	state outer_after_complete {

		when (efTestAndClear(xmapDoneFlag) &&  efTestAndClear(ip330DoneFlag) && efTestAndClear(sis3820DoneFlag) && efTestAndClear(netCDFDoneFlag)) {
			
			if (showDebugMessages > 4)
					printf("\nFlyscan message: state outer_after_complete: Setting phase to RESET_DONE.\n");
			
			scanPhase = RESET_DONE;
			pvPut(scanPhase, SYNC);
			
			outerAfterBusy = 0;
			pvPut(outerAfterBusy);
			
		} state outer_after_scan
	}
}

/*******************************************************************/
