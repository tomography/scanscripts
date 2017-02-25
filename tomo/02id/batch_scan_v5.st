program batch_scan_v5

option +s;
/* This program allows the user to set up several scans and then run them in succession
	without having to manually restart. 
   
   Author:	Christian Roehrig
   Created:	01/08/2007
   Version:	3.0

   Experimental Physics and Industrial Control System (EPICS)

   Copyright 1995, the University of Chicago Board of Governors.

   This software was produced under U.S. Government contract
   W-31-109-ENG-38 at Argonne National Laboratory.

   
   Modification Log
   
   18 July, 2008 - The program was changed to have a maximum of 30 scans.
   
   08 January, 2009 - The user no longer has to press initialize if either the
   			scan records used or the motors used in a scan record
   			changed.  In addition, two additional types of abort
   			have been added.  The original finishes the scan and
   			aborts the rest of the batch.  The second now aborts
   			the scan and finishes the batch.  The third aborts
   			everything.

   10 March, 2009 - Cleaned up some possible memory usage problems.  Added comments for
                    clearer code.
                    
   11 July, 2011 - Heavily modified to be able to run more than one instance, added support for flyscans, added transform records,
                   added a third loop.
                   
   04 June, 2012 - Changed the code to separate the motors used in the scan from the motors that position
                   the sample for the next scan.
                   
   01 August, 2012 - Made significant changes to accomodate the Bionanoprobe.

   06 July, 2013 - Changes made to work with sequencer version 2.1.5 or greater, removed BNP changes.
   
   02 September, 2015 - Made changes to compile with version 2.2 of the sequencer.
*/

/* Usage: seq &batchscan, "P=8bmb:,B=B1" */

%%#include <stdlib.h>
%%#include <stdio.h>
%%#include <math.h>

%%#include <epicsTime.h>
%%#include <epicsTypes.h>
%%#include <cadef.h>
%%#include <string.h>
%%#include <pv.h>

#define NORMAL 1
#define PAUSE 2
#define SKIP 0

#define SCAN_ONE 0
#define SCAN_TWO 1
#define SCAN_THREE 2
#define SCAN_FOUR 3
#define SCAN_H 4

#define SET_STEP_SCAN 1
#define SET_FLY_SCAN 2
#define STEP 0
#define FLY 1

#define NEVER 0
#define BEFORE 1
#define AFTER 2

#define MAXBATCHSIZE 30
#define MAXPOSITIONERS 3

#define WORKING 2

/*************************************************************************/
/* Variables associated with the scan records used
 * These are just initial values and are probably changed
 * immediatley by the initialization routine. */
	
string scan1RecPos;								/* This is the positioner used by the loop 1 of the scan. */
assign scan1RecPos to "{P}scan1.P1PV";

int scan1RecNumPts;
assign scan1RecNumPts to "{P}scan1.NPTS"; /* The number of points in the inner scan. */

float scan1RecWidth;
assign scan1RecWidth to "{P}scan1.P1WD"; /* The width of the inner scan. */

int scan1Execute;
assign scan1Execute to "{P}scan1.EXSC"; /* This equals one when the inner scan is executing. */

int scan1CurrentPoint;
assign scan1CurrentPoint to "{P}scan1.CPT"; /* The current point of the inner scan. */

int scan1CenterPoint;
assign scan1CenterPoint to "{P}scan1.P1CP"; /* The center of the inner scan. */

int scan1Busy;
assign scan1Busy to "{P}scan1.BUSY"; /* This equals one when the inner scan is not idle. */

string scan2RecPos;								/* This is the positioner used by the loop 2 of the scan. */
assign scan2RecPos to "{P}scan2.P1PV";

int scan2RecNumPts;
assign scan2RecNumPts to "{P}scan2.NPTS"; /* This is the number of points of the outer scan. */

float scan2RecWidth;
assign scan2RecWidth to "{P}scan2.P1WD"; /* The width of the outer scan. */

int scan2Execute;
assign scan2Execute to "{P}scan2.EXSC"; /* This equals one when the outer scan is executing. */

int scan2CurrentPoint;
assign scan2CurrentPoint to "{P}scan2.CPT"; /* The current point of the outer scan. */

int scan2CenterPoint;
assign scan2CenterPoint to "{P}scan2.P1CP"; /* The center of the outer scan. */

int scan2Busy;
assign scan2Busy to "{P}scan2.BUSY"; /* This equals one when the inner scan is not idle. */

int scanRecAbort;
assign scanRecAbort to "{P}AbortScans.PROC"; /* Setting this to one will abort the scan. */

/*************************************************************************/
/* Variables associated with batch scan setup                            */

/*** Step Scans ***/

int stepScan1RecPV;										/* This is used to choose which scan record will be the loop 1. */
assign stepScan1RecPV to "{P}{B}:Scan1Rec_PV.VAL";

int stepScan2RecPV;										/* This is used to choose which scan record will be the loop 2. */
assign stepScan2RecPV to "{P}{B}:Scan2Rec_PV.VAL";

string stepScan1PosPV;									/* Used to move the sample in the X direction between scans. */
assign stepScan1PosPV to "{P}{B}:Positioner1.VAL";

string stepScan1PosRdbkPV;								/* A PV for the readback position of positioner1. */
assign stepScan1PosRdbkPV to "{P}{B}:Positioner1Rdbk.VAL";

string stepScan2PosPV;									/* Used to move the sample in the Y direction between scans. */
assign stepScan2PosPV to "{P}{B}:Positioner2.VAL";

string stepScan2PosRdbkPV;								/* A PV for the readback position of positioner2. */
assign stepScan2PosRdbkPV to "{P}{B}:Positioner2Rdbk.VAL";

string stepScan3PosPV;									/* This is used to set the positioner for loop 3, if any. */
assign stepScan3PosPV to "{P}{B}:Positioner3.VAL";

string stepScan3PosRdbkPV;								/* A PV for the readback position of positioner3. */
assign stepScan3PosRdbkPV to "{P}{B}:Positioner3Rdbk.VAL";

string stepDwellTimePV;									/* This sets the PV with which a user may enter a dwell time. */
assign stepDwellTimePV to "{P}{B}:DwellTime_PV.VAL";

float stepMaxDeltaPos1;
assign stepMaxDeltaPos1 to "{P}{B}:MaxDeltaPos1.VAL";

float stepMaxDeltaPos2;
assign stepMaxDeltaPos2 to "{P}{B}:MaxDeltaPos2.VAL";

float stepMaxDeltaPos3;
assign stepMaxDeltaPos3 to "{P}{B}:MaxDeltaPos3.VAL";

float stepOverhead;										/* A value used to help calculate the total scan time. */
assign stepOverhead to "{P}{B}:Overhead.VAL";			/* It represents things like motor movement and detector overhead. */

int stepPos1IsMotorRecord;
assign stepPos1IsMotorRecord to "{P}{B}:StepPos1MotorRecord.VAL";

int stepPos2IsMotorRecord;
assign stepPos2IsMotorRecord to "{P}{B}:StepPos2MotorRecord.VAL";

int stepPos3IsMotorRecord;
assign stepPos3IsMotorRecord to "{P}{B}:StepPos3MotorRecord.VAL";

/*** Fly Scans ***/

int flyScan1RecPV;										/* This is used to choose which scan record will be the loop 1. */
assign flyScan1RecPV to "{P}{B}:FlyScan1Rec_PV.VAL";

int flyScan2RecPV;										/* This is used to choose which scan record will be the loop 2. */
assign flyScan2RecPV to "{P}{B}:FlyScan2Rec_PV.VAL";

string flyScan1PosPV;									/* Used to move the sample in the X direction between scans. */
assign flyScan1PosPV to "{P}{B}:FlyPositioner1.VAL";

string flyScan1PosRdbkPV;								/* A PV for the readback position of positioner1. */
assign flyScan1PosRdbkPV to "{P}{B}:FlyPositioner1Rdbk.VAL";

string flyScan2PosPV;									/* Used to move the sample in the Y direction between scans. */
assign flyScan2PosPV to "{P}{B}:FlyPositioner2.VAL";

string flyScan2PosRdbkPV;								/* A PV for the readback position of positioner2. */
assign flyScan2PosRdbkPV to "{P}{B}:FlyPositioner2Rdbk.VAL";

string flyScan3PosPV;									/* This is used to set the positioner for loop 3, if any. */
assign flyScan3PosPV to "{P}{B}:FlyPositioner3.VAL";

string flyScan3PosRdbkPV;								/* A PV for the readback position of positioner3. */
assign flyScan3PosRdbkPV to "{P}{B}:FlyPositioner3Rdbk.VAL";

string flyDwellTimePV;									/* This sets the PV with which a user may enter a dwell time. */
assign flyDwellTimePV to "{P}{B}:FlyDwellTime_PV.VAL";

float flyOverhead;										/* A value used to help calculate the total scan time. */
assign flyOverhead to "{P}{B}:FlyOverhead.VAL";		/* It represents things like motor movement and detector overhead. */

float flyMaxDeltaPos1;
assign flyMaxDeltaPos1 to "{P}{B}:FlyMaxDeltaPos1.VAL";

float flyMaxDeltaPos2;
assign flyMaxDeltaPos2 to "{P}{B}:FlyMaxDeltaPos2.VAL";

float flyMaxDeltaPos3;
assign flyMaxDeltaPos3 to "{P}{B}:FlyMaxDeltaPos3.VAL";

int flyPos1IsMotorRecord;
assign flyPos1IsMotorRecord to "{P}{B}:FlyPos1MotorRecord.VAL";

int flyPos2IsMotorRecord;
assign flyPos2IsMotorRecord to "{P}{B}:FlyPos2MotorRecord.VAL";

int flyPos3IsMotorRecord;
assign flyPos3IsMotorRecord to "{P}{B}:FlyPos3MotorRecord.VAL";

/*** All Scans ***/

string commentPV;									/* This set the PV with which a user may enter a comment. */
assign commentPV to "{P}{B}:ScanComment_PV.VAL";

string sampleNamePV;								/* This set the PV with which a user may enter a sample name. */
assign sampleNamePV to "{P}{B}:SampleName_PV.VAL";

string flyPrefix;
assign flyPrefix to "{P}{B}:FlyScanPrefix.VAL"; 	/* This is the prefix used for the fly scan records, e.g. 2tst:F. */

string stepPrefix;
assign stepPrefix to "{P}{B}:StepScanPrefix.VAL"; 	/* This is the prefix used for the step scan records, e.g. 2tst:. */

string logFileMount;
assign logFileMount to "{P}{B}:LogFileMountPoint.VAL";

/*************************************************************************/
/* These variables are initially set to placeholder values.
 * They will be re-assigned after the user has entered
 * permanent values in the setup window. */
 
float scan1PosVal;								/* This is the position value for the inner loop positioner. */
assign scan1PosVal to "{P}{B}:DummyPos1Val.VAL";

float scan1PosRdbk;								/* This is the position value readback for the inner loop positioner. */
assign scan1PosRdbk to "{P}{B}:DummyPos1Val.VAL";

float scan2PosVal;								/* This is the position value for the outer loop positioner. */
assign scan2PosVal to "{P}{B}:DummyPos2Val.VAL";

float scan2PosRdbk;								/* This is the position value readback for the outer loop positioner. */
assign scan2PosRdbk to "{P}{B}:DummyPos2Val.VAL";

float scan3PosVal;								/* This is the position value for the third positioner. */
assign scan3PosVal to "{P}{B}:DummyPos3Val.VAL";

float scan3PosRdbk;								/* This is the position value readback for the third positioner. */
assign scan3PosRdbk to "{P}{B}:DummyPos3Val.VAL";

float pos1HighLimit;
assign pos1HighLimit;

float pos2HighLimit;
assign pos2HighLimit;

float pos3HighLimit;
assign pos3HighLimit;

float pos1LowLimit;
assign pos1LowLimit;

float pos2LowLimit;
assign pos2LowLimit;

float pos3LowLimit;
assign pos3LowLimit;

/*************************************************************************/
/* These arrays hold values for each scan that is set up by the user.
 * Each element is assigned to the correct PV in the init_batch state.*/

int scan1NumPts[MAXBATCHSIZE];				/* The number of points to use in the scan's loop 1*/
assign scan1NumPts to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

float scan1Center[MAXBATCHSIZE];				/* The starting position for the loop 1 positioner */
assign scan1Center to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

float scan1Width[MAXBATCHSIZE];					/* The total distance that the loop 1 positioner */
												/* will travel on each iteration */
assign scan1Width to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

int scan2NumPts[MAXBATCHSIZE];				/* The number of points to use in the scan's loop 2*/
assign scan2NumPts to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

float scan2Center[MAXBATCHSIZE];				/* The starting position for the loop 2 positioner */
assign scan2Center to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

float scan2Width[MAXBATCHSIZE];					/* The total distance that the loop 2 positioner */
												/* will travel on each iteration */
assign scan2Width to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

int scan3NumPts[MAXBATCHSIZE];				/* The number of points to use in the scan's loop 3*/
assign scan3NumPts to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

float scan3Center[MAXBATCHSIZE];				/* The starting position for the loop 3 positioner */
assign scan3Center to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

float scan3Width[MAXBATCHSIZE];					/* The total distance that the loop 3 positioner will travel on each iteration */
assign scan3Width to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

float scanDwellTime[MAXBATCHSIZE];				/* A dwell time for the detectors */
assign scanDwellTime to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

string scanComment[MAXBATCHSIZE];				/* A descriptive comment for the scan */
assign scanComment to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

string fileName[MAXBATCHSIZE];					/* File that the scan was saved to */
assign fileName to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

string endFileName[MAXBATCHSIZE];				/* File that the scan was saved to */
assign endFileName to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

string scanStarted[MAXBATCHSIZE];				/* The time that the scan started. */		
assign scanStarted to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

string scanEnded[MAXBATCHSIZE];					/* The time that the scan ended. */	
assign scanEnded to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

int scanMode[MAXBATCHSIZE];						/* A value that tells the program if it should execute the scan, */
												/* pause at the scan line, or skip it. */
assign scanMode to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};
monitor scanMode; 

int execTransform[MAXBATCHSIZE];				/* When should the transform record process? Before scan, after scan, never. */
assign execTransform to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

int procTransform[MAXBATCHSIZE];				/* The PROC field of each transform record. */
assign procTransform to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};

/*************************************************************************/
int initialize;
assign initialize to "{P}{B}:InitBatch.VAL";
monitor initialize;

int loadFromScan;									/* A command to load scan parameters from a scan record */
assign loadFromScan to "{P}{B}:LoadFromScan.VAL";	/* to the batch scan */
monitor loadFromScan;

int loadToScan;										/* A command to load scan parameters from the batch scan */
assign loadToScan to "{P}{B}:LoadToScan.VAL";		/* to the scan record */
monitor loadToScan;

int zeroScan;
assign zeroScan to "{P}{B}:ZeroScan.VAL";			/* A command to reset all scan paramters to zero. */
monitor zeroScan;

int scanNumber;										/* The scan line that is currently selected by the user. */
assign scanNumber to "{P}{B}:ScanNumber.VAL";

int executingLine;									/* The line currently running in the batch. */
assign executingLine to "{P}{B}:ExecutingLine.VAL";

int calculateTime;
assign calculateTime to "{P}{B}:CalcBatchTime.VAL";	/* Initiates a calculation of the length of time to complete all */
monitor calculateTime;								/* scan lines with a mode or NORMAL. */

int calculatePoints;								/* Recalculate the number of scan points.  If calculatePoints = 1, */
assign calculatePoints to "{P}{B}:RecalcPoints.VAL";/* recalcualte for the selected scan line.  If calcualtePoints = 2, */
monitor calculatePoints;							/* recalculate for each scan line. */

float xStepSize;
assign xStepSize to "{P}{B}:XStepSize.VAL";			/* The step size to use for calculating number of points of positioner 1. */

float yStepSize;
assign yStepSize to "{P}{B}:YStepSize.VAL";			/* The step size to use for calculating number of points of positioner 2. */

string lastEstimate;
assign lastEstimate to "{P}{B}:LastEstimate.VAL";	/* The last time that a time calculation was done. */
monitor lastEstimate;

string estimateScanDone;							/* An estimate of when the current batch will be finished. */
assign estimateScanDone to "{P}{B}:EstimateScanDone.VAL";

string timeToComplete;								/* The length remaining for the current batch. */
assign timeToComplete to "{P}{B}:TimeToComplete.VAL";

string scanStatus;									/* A status message for the current action of the program. */
assign scanStatus to "{P}{B}:ScanStatus.VAL";

string lastAlive;									/* The time that each individual scan started. */
assign lastAlive to "{P}{B}:LastAlive.VAL";

int beginScan;
assign beginScan to "{P}{B}:BeginScan.VAL";			/* Initiates the execution of the current batch. */
monitor beginScan;

int continueScan;									/* Causes a paused batch to continue. */
assign continueScan to "{P}{B}:ContinueScan.VAL";
monitor continueScan;

int zeroAllScans;									/* Set all values in the batch to zero. */
assign zeroAllScans to "{P}{B}:ZeroAllScans.VAL";
monitor zeroAllScans;

int clearComments;									/* Clears all of the comment fields. */
assign clearComments to "{P}{B}:ClearComments.VAL";
monitor clearComments;

int pauseScan;										/* Causes the batch to puase at the next scan. */
assign pauseScan to "{P}{B}:PauseScan.VAL";
monitor pauseScan;

int abortBatch;										/* This is used to abort the batch after the current scan has finished. */
assign abortBatch to "{P}{B}:AbortBatch.VAL";
monitor abortBatch;

int abortScan;										/* This is used to abort the current scan and continue with the next scan. */
assign abortScan to "{P}{B}:AbortScan.VAL";
monitor abortScan;

string saveMessage;									/* The value of the saveData message. */
assign saveMessage to "{P}saveData_message.VAL";

string errorMessage;								/* A place to hold error messages for display to the users. */
assign errorMessage to "{P}{B}:ErrorMessage.VAL";

string batchSample;
assign batchSample to "{P}{B}:BatchSample.VAL";		/* A description of the current sample. */

string batchSampleInLink;							/* The PV the user uses to enter the sample name. */
assign batchSampleInLink to "{P}{B}:BatchSample.INP";

int numScans;										/* The number of scans that will be executed. */
assign numScans to "{P}{B}:BatchSize.VAL";

int extraScans;										/* Are any scans with scanNumber > 10 set to NORMAL mode? */
assign extraScans to "{P}{B}:ExtraScans.VAL";

int lastScan;										/* The last line of the batch that will be executed. */
assign lastScan to "{P}{B}:LastScan.VAL";
monitor lastScan;

int abortAll;										/* This is used to abort the current scan and the rest of the batch. */
assign abortAll to "{P}{B}:AbortAll.VAL";
monitor abortAll;

int setScanType;									/* Sets the scan type, fly or step. */
assign setScanType to "{P}{B}:SetScanType.VAL";
monitor setScanType;

int scanType;										/* Display the scant type, fly or step. */
assign scanType to "{P}{B}:ScanTypeStatus.VAL";
monitor scanType;

int resetPos3;										/* Sets the number of points for positioner 3 in all scans to one. */
assign resetPos3 to "{P}{B}:ResetPos3.VAL";
monitor resetPos3;

int zeroPos3;										/* Sets the number of points for positioner 3 in all scans to zero. */
assign zeroPos3 to "{P}{B}:ZeroPos3.VAL";
monitor zeroPos3;

string scan1RecordUsed;								/* The scan record associated with positioner 1. */
assign scan1RecordUsed to "{P}{B}:Scan1RecordUsed.VAL";

string scan2RecordUsed;								/* The scan record associated with positioner 2. */
assign scan2RecordUsed to "{P}{B}:Scan2RecordUsed.VAL";

string saveDataPath;
assign saveDataPath to "{P}saveData_subDir.VAL";

string saveDataFileName;
assign saveDataFileName to "{P}saveData_fileName.VAL";

int testPath;										/* Tests the ability to record data for positioner 3. */
assign testPath to "{P}{B}:TestFilePath.VAL";
monitor testPath;

int testPathStatus;									/* Reports success or failure after testing. */
assign testPathStatus to "{P}{B}:TestPathStatus.VAL";

int batchRunning;									/* Reports TRUE or FALSE. */
assign batchRunning to "{P}{B}:BatchRunning.VAL";
monitor batchRunning;

int showDebugMessages;
assign showDebugMessages to "{P}{B}:ShowDebugMsgs.VAL";
monitor showDebugMessages;

int disable;
assign disable to "{P}{B}:Disable.VAL";
monitor disable;

int allPvsConnected;
assign allPvsConnected to "{P}{B}:AllPVsConnected.VAL";
monitor allPvsConnected;

int resetBatch;
assign resetBatch to "{P}{B}:ResetBatch.VAL";
monitor resetBatch;

int checkLimits;
assign checkLimits to "{P}{B}:CheckLimits.VAL";
monitor checkLimits;

/*************************************************************************/
/* Anonymous PVs                                                         */

int numPtsComplete[MAXBATCHSIZE];			/* This is used to recalculate the time left for the batch scan after
									   					each time through an iteration of scan X. */
assign numPtsComplete to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};
monitor numPtsComplete;

int remainingScan3Points;		/* The number of point remaining for the 3rd positioner in the scan. */
assign remainingScan3Points;
monitor remainingScan3Points;

int scanComplete[MAXBATCHSIZE];				/* A variable that keeps track of which scans are complete */
assign scanComplete to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};
monitor scanComplete;

int transformComplete[MAXBATCHSIZE];		/* This keeps track of transform records that have been executed */
assign transformComplete to {"","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""};
monitor transformComplete;

string iocPrefix;
assign iocPrefix;

string batchNumber;
assign batchNumber;

int scan1RecPV;
assign scan1RecPV;

int scan2RecPV;
assign scan2RecPV;

string scan1PosPV;
assign scan1PosPV;

string scan1PosRdbkPV;
assign scan1PosRdbkPV;

string scan2PosPV;
assign scan2PosPV;

string scan2PosRdbkPV;
assign scan2PosRdbkPV;

string scan3PosPV;
assign scan3PosPV;

string scan3PosRdbkPV;
assign scan3PosRdbkPV;

float maxDeltaPos1;
assign maxDeltaPos1;

float maxDeltaPos2;
assign maxDeltaPos2;

float maxDeltaPos3;
assign maxDeltaPos3;

float dwellTime;									/* This is the dwell time PV. It is assigned its value in the init_batch state. */
assign dwellTime to "";

string comment;										/* This is the comment PV. It is assigned its value in the init_batch state. */
assign comment to "";

string sampleName;									/* This is the sample name PV. It is assigned its value in the init_batch state. */
assign sampleName to "";

float overhead;										
assign overhead to "";

int pos1IsMotor;
assign pos1IsMotor;

int pos2IsMotor;
assign pos2IsMotor;

int pos3IsMotor;
assign pos3IsMotor;

int xyDifferentScans;
assign xyDifferentScans;

/*************************************************************************/

evflag updateTime;
evflag modeChange;
evflag initFlag;
evflag positionerErrorFlag;
evflag scanErrorFlag;
evflag scanLineFinished;
evflag resetBatchFlag;

sync resetBatch resetBatchFlag;
sync scanMode modeChange;

int initLoop;						/* There is one variable for each state set to use in iterative loops. */
int controlLoop;					/* This was done to avoid conflicts. */
int modifyLoop;
int timeLoop;
int scanLoop;
int modeLoop;
int scanPaused;
int scanValid;
int scan3TimeFactor;				/* The number of points that positioner 3 is contributing to the scan time */
int readyToStart;					/* Indicates that all stages should be ready to start the scan. */
int positionChecked;				/* Motor positions have been checked to see if they actually moved. */
int errorCount;					/* The number of times an error has occured. */

float batchTime;

double hours;
double minutes;
double seconds;
double quotient;
double pointsRemainder;
double pos3Increment;
double pos3Start;
double pos3End;

string pvName;
string scan1Name;					/* The scan record used for loop 1. */
string scan2Name;					/* The scan record used for loop 2. */
string scanPrefix;					/* The pv prefix to use with the scan record.  It can be step or fly scan records. */


char timeString[32];
char *ioc;
char *batch;

%{

typedef struct fileOutputInfo
{
	char fileNameStr[40];
	char path[255];
	char sample[40];
	char startTime[40];
	char endTime[40];
	int scanLine;
	int newFile;
	float positioner3Val;
} fileInfo;

fileInfo scanInfo;	/* This holds the file information and position for each scan done at a particular value of positioner 3. */

static epicsTimeStamp timeStamp;

void write_scan_info (fileInfo *);
int test_file_path(char *, char *);

}%


/**************************************************/

ss init_batch {

	/* This state initializes most of the variables and assigns them to the PVs that are needed. */
	state init {
			
		entry {
			
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state init: Beginning program initialization.\n");	
				
		}

	    when() {

			int initLoop;

			allPvsConnected = FALSE;
			pvPut(allPvsConnected);

			numScans = 0;
			extraScans = FALSE;
			lastScan = 0;
			readyToStart = FALSE;
			positionChecked = FALSE;
			errorCount = 0;
						
			/* Get the ioc prefix and batch number that will be used to assign variables to PVs. */
			ioc = macValueGet("P");
			sprintf(iocPrefix, ioc);
			pvPut(iocPrefix);
			
			batch = macValueGet("B");
			sprintf(batchNumber, batch);
			pvPut(batchNumber);
			
			/*******************************************************************/
			
			pvGet(scanType);
			
			if (scanType == STEP)
			{
				pvGet(stepScan1RecPV);
				pvGet(stepScan2RecPV);
				
				scan1RecPV = stepScan1RecPV;
				pvPut(scan1RecPV);
				scan2RecPV = stepScan2RecPV;
				pvPut(scan2RecPV);
				
				pvGet(stepPos1IsMotorRecord);
				pos1IsMotor = stepPos1IsMotorRecord;
				pvPut(pos1IsMotor);
				
				pvGet(stepPos2IsMotorRecord);
				pos2IsMotor = stepPos2IsMotorRecord;
				pvPut(pos2IsMotor);
				
				pvGet(stepPos3IsMotorRecord);
				pos3IsMotor = stepPos3IsMotorRecord;
				pvPut(pos3IsMotor);
				
				sprintf(pvName, "%s%s:Positioner1.VAL", iocPrefix, batchNumber);
				pvAssign(scan1PosPV, pvName);
				sprintf(pvName, "%s%s:Positioner2.VAL", iocPrefix, batchNumber);
				pvAssign(scan2PosPV, pvName);
				sprintf(pvName, "%s%s:Positioner3.VAL", iocPrefix, batchNumber);
				pvAssign(scan3PosPV, pvName);
				
				sprintf(pvName, "%s%s:Positioner1Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan1PosRdbkPV, pvName);
				sprintf(pvName, "%s%s:Positioner2Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan2PosRdbkPV, pvName);
				sprintf(pvName, "%s%s:Positioner3Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan3PosRdbkPV, pvName);
				
				pvGet(stepDwellTimePV);
				pvAssign(dwellTime, stepDwellTimePV);
				
				pvGet(stepOverhead);
				overhead = stepOverhead;
				pvPut(overhead);
				
				pvGet(stepPrefix);
				sprintf(scanPrefix, "%s", stepPrefix);
			}
			
			if (scanType == FLY)
			{
				pvGet(flyScan1RecPV);
				pvGet(flyScan2RecPV);
							
				scan1RecPV = flyScan1RecPV;
				pvPut(scan1RecPV);
				scan2RecPV = flyScan2RecPV;
				pvPut(scan2RecPV);
				
				pvGet(flyPos1IsMotorRecord);
				pos1IsMotor = flyPos1IsMotorRecord;
				pvPut(pos1IsMotor);
				
				pvGet(flyPos2IsMotorRecord);
				pos2IsMotor = flyPos2IsMotorRecord;
				pvPut(pos2IsMotor);
				
				pvGet(flyPos3IsMotorRecord);
				pos3IsMotor = flyPos3IsMotorRecord;
				pvPut(pos3IsMotor);
				
				sprintf(pvName, "%s%s:FlyPositioner1.VAL", iocPrefix, batchNumber);
				pvAssign(scan1PosPV, pvName);
				sprintf(pvName, "%s%s:FlyPositioner2.VAL", iocPrefix, batchNumber);
				pvAssign(scan2PosPV, pvName);
				sprintf(pvName, "%s%s:FlyPositioner3.VAL", iocPrefix, batchNumber);
				pvAssign(scan3PosPV, pvName);
				
				sprintf(pvName, "%s%s:FlyPositioner1Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan1PosRdbkPV, pvName);
				sprintf(pvName, "%s%s:FlyPositioner2Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan2PosRdbkPV, pvName);
				sprintf(pvName, "%s%s:FlyPositioner3Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan3PosRdbkPV, pvName);
				
				pvGet(flyDwellTimePV);
				pvAssign(dwellTime, flyDwellTimePV);
				
				pvGet(flyOverhead);
				overhead = flyOverhead;
				pvPut(overhead);
				
				pvGet(flyPrefix);
				sprintf(scanPrefix, "%s", flyPrefix);
			}
			
			/**************************************************************/
			/* Assign all of the batch scan variables to the correct PVs. */
		   	   for (initLoop = 0; initLoop < MAXBATCHSIZE; initLoop++)
			{
				sprintf(pvName, "%s%s:Scan_%d:Dwell.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scanDwellTime[initLoop], pvName);
			
				sprintf(pvName, "%s%s:Scan1_%d:NumPts.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan1NumPts[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan2_%d:NumPts.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan2NumPts[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan3_%d:NumPts.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan3NumPts[initLoop], pvName);

				sprintf(pvName, "%s%s:Scan1_%d:Center.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan1Center[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan2_%d:Center.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan2Center[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan3_%d:Center.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan3Center[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan1_%d:Width.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan1Width[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan2_%d:Width.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan2Width[initLoop], pvName);
					
				sprintf(pvName, "%s%s:Scan3_%d:Width.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scan3Width[initLoop], pvName);
								
				sprintf(pvName, "%s%s:Scan_%d:Comment.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scanComment[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan_%d:FileName.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(fileName[initLoop], pvName);
					
				sprintf(pvName, "%s%s:Scan_%d:FileName2.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(endFileName[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan_%d:Started.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scanStarted[initLoop], pvName);
				
				sprintf(pvName, "%s%s:Scan_%d:Ended.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scanEnded[initLoop], pvName);
				
				pvStopMonitor(scanMode[initLoop]);
				sprintf(pvName, "%s%s:Scan_%d:Mode.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(scanMode[initLoop], pvName);
				pvMonitor(scanMode[initLoop]);
					
				sprintf(pvName, "%s%s:Scan_%d:ExecOrder.VAL", iocPrefix, batchNumber, initLoop);
				pvAssign(execTransform[initLoop], pvName);
					
				sprintf(pvName, "%s%s:Scan_%d:Transform.PROC", iocPrefix, batchNumber, initLoop);
				pvAssign(procTransform[initLoop], pvName);
				
				numPtsComplete[initLoop] = 0;
				pvPut(numPtsComplete[initLoop]);
				scanComplete[initLoop] = FALSE;
				pvPut(scanComplete[initLoop]);
				transformComplete[initLoop] = FALSE;
				pvPut(transformComplete[initLoop]);
				
			}

			
			/*******************************************************************/		
			/* Get the user defined PVs for sample name, comments, dwell time, and others from the setup screen. */
			pvGet(sampleNamePV);
			pvAssign(sampleName, sampleNamePV);
			
			pvGet(commentPV);
			pvAssign(comment, commentPV);
			
			pvGet(scan1RecPV);
			pvGet(scan2RecPV);
			pvGet(scan1PosPV);
			pvGet(scan2PosPV);
			pvGet(scan3PosPV);
			pvGet(scan1PosRdbkPV);
			pvGet(scan2PosRdbkPV);
			pvGet(scan3PosRdbkPV);
			
			pvGet(logFileMount);
			/*******************************************************************/
						
			executingLine = -1;
			pvPut(executingLine);
			
			sprintf(scanStatus, "Idle");
			pvPut(scanStatus);
			
			/* Make sure that the scan records chosen are not the same. If they are, display an error message. */
			/* If they are different, then go ahead and assign all of the variables that are related to those */
			/* scan records. */
			if (scan1RecPV == scan2RecPV)
			{
				sprintf(errorMessage, "Scan X and Scan Y use the same record.");
				pvPut(errorMessage);
				
				xyDifferentScans = FALSE;
				pvPut(xyDifferentScans);
				
				if (showDebugMessages > 2)
					printf("\nBatchscan message: state reInit: Scan X is %d and Scan Y is %d.\n", scan1RecPV, scan2RecPV);
			}
			else
			{
				xyDifferentScans = TRUE;
				pvPut(xyDifferentScans);
			
				/* Determine which scan records are used based on what the user choose on the setup screen. */
				/* Valid values are scan1, scan2, scan3, scan4, and scanH. */
				if (scan1RecPV == SCAN_ONE)
					sprintf(scan1Name, "scan1");
				if (scan1RecPV == SCAN_TWO)
					sprintf(scan1Name, "scan2");	
				if (scan1RecPV == SCAN_THREE)
					sprintf(scan1Name, "scan3");
				if (scan1RecPV == SCAN_FOUR)
					sprintf(scan1Name, "scan4");
				if (scan1RecPV == SCAN_H)
					sprintf(scan1Name, "scanH");
					
				if (scan2RecPV == SCAN_ONE)
					sprintf(scan2Name, "scan1");
				if (scan2RecPV == SCAN_TWO)
					sprintf(scan2Name, "scan2");
				if (scan2RecPV == SCAN_THREE)
					sprintf(scan2Name, "scan3");
				if (scan2RecPV == SCAN_FOUR)
					sprintf(scan2Name, "scan4");
				if (scan2RecPV == SCAN_H)
					sprintf(scan2Name, "scanH");
								
				sprintf(scan1RecordUsed, "%s%s", stepPrefix, scan1Name);
				pvPut(scan1RecordUsed);
				
				sprintf(scan2RecordUsed, "%s%s", stepPrefix, scan2Name);
				pvPut(scan2RecordUsed);
				
				/********************************************************/	
				/* Assign the scan record variables to the correct PVs. */					
				sprintf(pvName, "%s%s.P1PV", scanPrefix, scan1Name);
				pvAssign(scan1RecPos, pvName);
					
				sprintf(pvName, "%s%s.NPTS", scanPrefix, scan1Name);
				pvAssign(scan1RecNumPts, pvName);
					
				sprintf(pvName, "%s%s.P1WD", scanPrefix, scan1Name);
				pvAssign(scan1RecWidth, pvName);
				
				sprintf(pvName, "%s%s.P1CP", scanPrefix, scan1Name);
				pvAssign(scan1CenterPoint, pvName);
					
				sprintf(pvName, "%s%s.EXSC", scanPrefix, scan1Name);
				pvAssign(scan1Execute, pvName);
				pvMonitor(scan1Execute);
				
				sprintf(pvName, "%s%s.BUSY", scanPrefix, scan1Name);
				pvAssign(scan1Busy, pvName);
				pvMonitor(scan1Busy);
				
				sprintf(pvName, "%s%s.P1PV", scanPrefix, scan2Name);
				pvAssign(scan2RecPos, pvName);
				
				sprintf(pvName, "%s%s.NPTS", scanPrefix, scan2Name);
				pvAssign(scan2RecNumPts, pvName);
					
				sprintf(pvName, "%s%s.P1WD", scanPrefix, scan2Name);
				pvAssign(scan2RecWidth, pvName);
				
				sprintf(pvName, "%s%s.P1CP", scanPrefix, scan2Name);
				pvAssign(scan2CenterPoint, pvName);
				
				sprintf(pvName, "%s%s.EXSC", scanPrefix, scan2Name);
				pvAssign(scan2Execute, pvName);
				pvMonitor(scan2Execute);
					
				sprintf(pvName, "%s%s.CPT", scanPrefix, scan2Name);
				pvAssign(scan2CurrentPoint, pvName);
				pvMonitor(scan2CurrentPoint);
				pvSync(scan2CurrentPoint, scanLineFinished);

				sprintf(pvName, "%s%s.BUSY", scanPrefix, scan2Name);
				pvAssign(scan2Busy, pvName);
				pvMonitor(scan2Busy);
				
				sprintf(pvName, "%sAbortScans.PROC", scanPrefix);
				pvAssign(scanRecAbort, pvName);
				pvMonitor(scanRecAbort);
				/********************************************************/
		
				pvPut(numScans);
				pvPut(extraScans);
				pvPut(lastScan);
				
				/*****************************************************************************************/
				/* Assign the motor positioner variables to the correct motor records. */
				/* This information is obtained from the scan records. */
			
				/* Positioner 1*/
				if(strlen(scan1PosPV) > 0)
					pvAssign(scan1PosVal, scan1PosPV);
				if(strlen(scan1PosRdbkPV) > 0)
					pvAssign(scan1PosRdbk, scan1PosRdbkPV);
				
				if (showDebugMessages > 0)
				{
					printf("\nBatchscan message: state init: Positioner 1 is %s.\n", scan1PosPV);
					printf("\nBatchscan message: state init: Positioner 1 readback is %s.\n", scan1PosRdbkPV);
				}
				
				/* If the positioner is a motor record, then assign  variables to the high and low soft limits. */
				if (pos1IsMotor)
				{
					sprintf(pvName, "%s", strtok(scan1PosPV, "."));
					strcat(pvName, ".LLM");
					if (showDebugMessages > 0)
						printf("\nBatchscan message: state init: Positioner 1 low limit PV is %s.\n", pvName);
					pvAssign(pos1LowLimit, pvName);
					
					sprintf(pvName, "%s", strtok(scan1PosPV, "."));
					strcat(pvName, ".HLM");
					if (showDebugMessages > 0)
						printf("\nBatchscan message: state init: Positioner 1 high limit PV is %s.\n", pvName);
					pvAssign(pos1HighLimit, pvName);
				}
				else
				{
					pvAssign(pos1LowLimit,"");
					pvAssign(pos1HighLimit,"");
				}
					
				/* Positioner 2*/
				if(strlen(scan2PosPV) > 0)
					pvAssign(scan2PosVal, scan2PosPV);
				if(strlen(scan2PosRdbkPV) > 0)
					pvAssign(scan2PosRdbk, scan2PosRdbkPV);

				if (showDebugMessages > 0)
				{
					printf("\nBatchscan message: state init: Positioner 2 is %s.\n", scan2PosPV);
					printf("\nBatchscan message: state init: Positioner 2 readback is %s.\n", scan2PosRdbkPV);
				}
				
				/* If the positioner is a motor record, then assign  variables to the high and low soft limits. */
				if (pos2IsMotor)
				{
					sprintf(pvName, "%s", strtok(scan2PosPV, "."));
					strcat(pvName, ".LLM");
					pvAssign(pos2LowLimit, pvName);
					
					sprintf(pvName, "%s", strtok(scan2PosPV, "."));
					strcat(pvName, ".HLM");
					pvAssign(pos2HighLimit, pvName);
				}
				else
				{
					pvAssign(pos2LowLimit,"");
					pvAssign(pos2HighLimit,"");
				}

				/* Positioner 3*/
				/* This positioner does not necessarily need to be assigned a real value. */
				if(strlen(scan3PosPV) > 0)
					pvAssign(scan3PosVal, scan3PosPV);
				if(strlen(scan3PosRdbkPV) > 0)
					pvAssign(scan3PosRdbk, scan3PosRdbkPV);
				
				if (showDebugMessages > 0)
				{
					printf("\nBatchscan message: state init: Positioner 3 is %s.\n", scan3PosPV);
					printf("\nBatchscan message: state init: Positioner 3 readback is %s.\n", scan3PosRdbkPV);
				}
				
				/* If the positioner is a motor record, then assign  variables to the high and low soft limits. */
				if (pos3IsMotor)
				{
					sprintf(pvName, "%s", strtok(scan3PosPV, "."));
					strcat(pvName, ".LLM");
					pvAssign(pos3LowLimit, pvName);
					
					sprintf(pvName, "%s", strtok(scan3PosPV, "."));
					strcat(pvName, ".HLM");
					pvAssign(pos3HighLimit, pvName);
				}
				else
				{
					pvAssign(pos3LowLimit,"");
					pvAssign(pos3HighLimit,"");
				}
				
				/*****************************************************************************************/				
				
				/* Write the name of the sample to the local PV for display on the batch scan screen. */
				pvGet(sampleName);
				strcpy(batchSample, sampleName);
				pvPut(batchSample);
				
				/* Set the input link of the sample name PV so that it updates on the batch scan screen
				   when the user changes it elsewhere. */
				strcpy(batchSampleInLink, sampleNamePV);
				strcat(batchSampleInLink, " CPP NMS");
				pvPut(batchSampleInLink);
				
				sprintf(errorMessage, "Connecting PVs.");
				pvPut(errorMessage);
			}
			
		} state pvsConnecting
	}
	
	/* Check to make sure that all variables assigned to a PV have been able to connect. */
	state pvsConnecting {
	
		entry {
			sprintf(errorMessage, "Waiting for variables to connect.");
			pvPut(errorMessage);
		}
		
		when (!xyDifferentScans) {
		
			sprintf(errorMessage, "Scan X and Scan Y use the same record.");
			pvPut(errorMessage);
			
		} state reInit
		
		/* The variables are connected to the EPICS PVs.  Go ahead and finish initialization. */
		when ((pvConnectCount() == pvAssignCount()) && xyDifferentScans) {
		
			allPvsConnected = TRUE;
			pvPut(allPvsConnected);
			sprintf(errorMessage, "All batch scan variables connected.");
			pvPut(errorMessage);
								
			/* Trigger the state set that will count the number of scans to be run and the number
			   of the last scan. */
			efSet(modeChange);
			
		} state reInit
		
		/* The variables cannot connect to the EPICS PVs.  Do not finish initialization and show
			an error message. */
		when (delay(15)) {
		
			allPvsConnected = FALSE;
			pvPut(allPvsConnected);
			sprintf(errorMessage, "Error - unconnected variables.");
			pvPut(errorMessage);
			
			if (showDebugMessages > 0)
			{
					printf("\nBatchscan message: state pvsConnecting: There are %d pvs assigned.\n", pvAssignCount());
					printf("\nBatchscan message: state pvsConnecting: There are %d pvs connected.\n", pvConnectCount());
			}
					
		} state reInit
	
	}
		
	/* This state initializes most of the variables and assigns them to the PVs that are needed. */
	state reInit {
	
	   when((efTestAndClear(initFlag) || initialize) && !batchRunning) {

			int initLoop;
			
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state reInit: Beginning program reinitialization.\n");	
			
			allPvsConnected = FALSE;
			pvPut(allPvsConnected);
			numScans = 0;
			extraScans = FALSE;
			lastScan = 0;
			readyToStart = FALSE;
			positionChecked = FALSE;
			errorCount = 0;

			/* Get the ioc prefix and batch number that will be used to assign variables to PVs. */
			pvGet(iocPrefix);
			pvGet(batchNumber);
						
			/* Get the user defined PVs for sample name, comments, and dwell time. */
			pvGet(sampleNamePV);
			pvAssign(sampleName, sampleNamePV);
			
			pvGet(commentPV);
			pvAssign(comment, commentPV);
			
			/*******************************************************************/
			
			pvGet(scanType);
			
			if (scanType == STEP)
			{
				pvGet(stepScan1RecPV);
				pvGet(stepScan2RecPV);
				
				scan1RecPV = stepScan1RecPV;
				pvPut(scan1RecPV);
				scan2RecPV = stepScan2RecPV;
				pvPut(scan2RecPV);
				
				pvGet(stepPos1IsMotorRecord);
				pos1IsMotor = stepPos1IsMotorRecord;
				pvPut(pos1IsMotor);
				
				pvGet(stepPos2IsMotorRecord);
				pos2IsMotor = stepPos2IsMotorRecord;
				pvPut(pos2IsMotor);
				
				pvGet(stepPos3IsMotorRecord);
				pos3IsMotor = stepPos3IsMotorRecord;
				pvPut(pos3IsMotor);
				
				sprintf(pvName, "%s%s:Positioner1.VAL", iocPrefix, batchNumber);
				pvAssign(scan1PosPV, pvName);
				sprintf(pvName, "%s%s:Positioner2.VAL", iocPrefix, batchNumber);
				pvAssign(scan2PosPV, pvName);
				sprintf(pvName, "%s%s:Positioner3.VAL", iocPrefix, batchNumber);
				pvAssign(scan3PosPV, pvName);
				
				sprintf(pvName, "%s%s:Positioner1Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan1PosRdbkPV, pvName);
				sprintf(pvName, "%s%s:Positioner2Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan2PosRdbkPV, pvName);
				sprintf(pvName, "%s%s:Positioner3Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan3PosRdbkPV, pvName);
				
				pvGet(stepDwellTimePV);
				pvAssign(dwellTime, stepDwellTimePV);
				
				pvGet(stepOverhead);
				overhead = stepOverhead;
				pvPut(overhead);
				
				pvGet(stepPrefix);
				sprintf(scanPrefix, "%s", stepPrefix);
			}
			
			if (scanType == FLY)
			{
				pvGet(flyScan1RecPV);
				pvGet(flyScan2RecPV);
				
				scan1RecPV = flyScan1RecPV;
				pvPut(scan1RecPV);
				scan2RecPV = flyScan2RecPV;
				pvPut(scan2RecPV);
				
				pvGet(flyPos1IsMotorRecord);
				pos1IsMotor = flyPos1IsMotorRecord;
				pvPut(pos1IsMotor);
				
				pvGet(flyPos2IsMotorRecord);
				pos2IsMotor = flyPos2IsMotorRecord;
				pvPut(pos2IsMotor);
				
				pvGet(flyPos3IsMotorRecord);
				pos3IsMotor = flyPos3IsMotorRecord;
				pvPut(pos3IsMotor);
				
				sprintf(pvName, "%s%s:FlyPositioner1.VAL", iocPrefix, batchNumber);
				pvAssign(scan1PosPV, pvName);
				sprintf(pvName, "%s%s:FlyPositioner2.VAL", iocPrefix, batchNumber);
				pvAssign(scan2PosPV, pvName);
				sprintf(pvName, "%s%s:FlyPositioner3.VAL", iocPrefix, batchNumber);
				pvAssign(scan3PosPV, pvName);
				
				sprintf(pvName, "%s%s:FlyPositioner1Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan1PosRdbkPV, pvName);
				sprintf(pvName, "%s%s:FlyPositioner2Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan2PosRdbkPV, pvName);
				sprintf(pvName, "%s%s:FlyPositioner3Rdbk.VAL", iocPrefix, batchNumber);
				pvAssign(scan3PosRdbkPV, pvName);
				
				pvGet(flyDwellTimePV);
				pvAssign(dwellTime, flyDwellTimePV);
				
				pvGet(flyOverhead);
				overhead = flyOverhead;
				pvPut(overhead);
				
				pvGet(flyPrefix);
				sprintf(scanPrefix, "%s", flyPrefix);
			
			}
			
			pvGet(scan1RecPV);
			pvGet(scan2RecPV);
			pvGet(scan1PosPV);
			pvGet(scan2PosPV);
			pvGet(scan3PosPV);
			pvGet(scan1PosRdbkPV);
			pvGet(scan2PosRdbkPV);
			pvGet(scan3PosRdbkPV);
			
			pvGet(logFileMount);
			
			executingLine = -1;
			pvPut(executingLine);
			
			sprintf(scanStatus, "Idle");
			pvPut(scanStatus);
			
			/* Make sure that the scan records chosen are not the same. If they are, display an error message. */
			/* If they are different, then go ahead and assign all of the variables that are related to those */
			/* scan records. */
			if (scan1RecPV == scan2RecPV)
			{
				sprintf(errorMessage, "Scan X and Scan Y use the same record.");
				pvPut(errorMessage);
				
				if (showDebugMessages > 2)
					printf("\nBatchscan message: state reInit: Scan X is %d and Scan Y is %d.\n", scan1RecPV, scan2RecPV);	
			}
			else
			{
			/* Determine which scan records are used based on what the user choose on the setup screen. */
				/* Valid values are scan1, scan2, scan3, scan4, and scanH. */
				if (scan1RecPV == SCAN_ONE)
					sprintf(scan1Name, "scan1");
				if (scan1RecPV == SCAN_TWO)
					sprintf(scan1Name, "scan2");	
				if (scan1RecPV == SCAN_THREE)
					sprintf(scan1Name, "scan3");
				if (scan1RecPV == SCAN_FOUR)
					sprintf(scan1Name, "scan4");
				if (scan1RecPV == SCAN_H)
					sprintf(scan1Name, "scanH");
					
				if (scan2RecPV == SCAN_ONE)
					sprintf(scan2Name, "scan1");
				if (scan2RecPV == SCAN_TWO)
					sprintf(scan2Name, "scan2");
				if (scan2RecPV == SCAN_THREE)
					sprintf(scan2Name, "scan3");
				if (scan2RecPV == SCAN_FOUR)
					sprintf(scan2Name, "scan4");
				if (scan2RecPV == SCAN_H)
					sprintf(scan2Name, "scanH");
					
				sprintf(scan1RecordUsed, "%s%s", scanPrefix, scan1Name);
				pvPut(scan1RecordUsed);
				
				sprintf(scan2RecordUsed, "%s%s", scanPrefix, scan2Name);
				pvPut(scan2RecordUsed);
				
				/********************************************************/								
				/* Assign the scan record variables to the correct PVs. */					
				sprintf(pvName, "%s%s.P1PV", scanPrefix, scan1Name);
				pvAssign(scan1RecPos, pvName);
					
				sprintf(pvName, "%s%s.NPTS", scanPrefix, scan1Name);
				pvAssign(scan1RecNumPts, pvName);
					
				sprintf(pvName, "%s%s.P1WD", scanPrefix, scan1Name);
				pvAssign(scan1RecWidth, pvName);
				
				sprintf(pvName, "%s%s.P1CP", stepPrefix, scan1Name);
				pvAssign(scan1CenterPoint, pvName);
				
				pvStopMonitor(scan1Execute);	
				sprintf(pvName, "%s%s.EXSC", scanPrefix, scan1Name);
				pvAssign(scan1Execute, pvName);
				pvMonitor(scan1Execute);
				
				sprintf(pvName, "%s%s.CPT", scanPrefix, scan1Name);
				pvAssign(scan1CurrentPoint, pvName);

				pvStopMonitor(scan1Busy);
				sprintf(pvName, "%s%s.BUSY", scanPrefix, scan1Name);
				pvAssign(scan1Busy, pvName);
				pvMonitor(scan1Busy);
				
				sprintf(pvName, "%s%s.P1PV", scanPrefix, scan2Name);
				pvAssign(scan2RecPos, pvName);
				
				sprintf(pvName, "%s%s.NPTS", scanPrefix, scan2Name);
				pvAssign(scan2RecNumPts, pvName);
					
				sprintf(pvName, "%s%s.P1WD", scanPrefix, scan2Name);
				pvAssign(scan2RecWidth, pvName);
				
				sprintf(pvName, "%s%s.P1CP", stepPrefix, scan2Name);
				pvAssign(scan2CenterPoint, pvName);
					
				pvStopMonitor(scan2Execute);
				sprintf(pvName, "%s%s.EXSC", scanPrefix, scan2Name);
				pvAssign(scan2Execute, pvName);
				pvMonitor(scan2Execute);
				
				pvStopMonitor(scan2CurrentPoint);	
				sprintf(pvName, "%s%s.CPT", scanPrefix, scan2Name);
				pvAssign(scan2CurrentPoint, pvName);
				pvMonitor(scan2CurrentPoint);
				pvSync(scan2CurrentPoint, scanLineFinished);
				
				pvStopMonitor(scan2Busy);
				sprintf(pvName, "%s%s.BUSY", scanPrefix, scan2Name);
				pvAssign(scan2Busy, pvName);
				pvMonitor(scan2Busy);
				
				pvStopMonitor(scanRecAbort);
				sprintf(pvName, "%sAbortScans.PROC", scanPrefix);
				pvAssign(scanRecAbort, pvName);
				pvMonitor(scanRecAbort);
				/********************************************************/

				/* Reset some array values. */
				for (initLoop = 0; initLoop < MAXBATCHSIZE; initLoop++)
				{
					
					numPtsComplete[initLoop] = 0;
					pvPut(numPtsComplete[initLoop]);
					scanComplete[initLoop] = FALSE;
					pvPut(scanComplete[initLoop]);
					transformComplete[initLoop] = FALSE;
					pvPut(transformComplete[initLoop]);				
				}
				
				pvPut(numScans);
				pvPut(extraScans);
				pvPut(lastScan);
				
				/*****************************************************************************************/
				/* Assign the motor positioner variables to the correct motor records. */
				/* This information is obtained from the scan records. */
			
				/* Positioner 1*/
				if(strlen(scan1PosPV) > 0)
					pvAssign(scan1PosVal, scan1PosPV);
				if(strlen(scan1PosRdbkPV) > 0)
					pvAssign(scan1PosRdbk, scan1PosRdbkPV);
					
				if (showDebugMessages > 0)
				{
					printf("\nBatchscan message: state reInit: Positioner 1 is %s.\n", scan1PosPV);
					printf("\nBatchscan message: state reInit: Positioner 1 readback is %s.\n", scan1PosRdbkPV);
				}
				
				/* If the positioner is a motor record, then assign  variables to the high and low soft limits. */
				if (pos1IsMotor)
				{
					sprintf(pvName, "%s", strtok(scan1PosPV, "."));
					strcat(pvName, ".LLM");
					if (showDebugMessages > 0)
						printf("\nBatchscan message: state init: Positioner 1 low limit PV is %s.\n", pvName);
					pvAssign(pos1LowLimit, pvName);
					
					sprintf(pvName, "%s", strtok(scan1PosPV, "."));
					strcat(pvName, ".HLM");
					if (showDebugMessages > 0)
						printf("\nBatchscan message: state init: Positioner 1 high limit PV is %s.\n", pvName);
					pvAssign(pos1HighLimit, pvName);
				}
				else
				{
					pvAssign(pos1LowLimit,"");
					pvAssign(pos1HighLimit,"");
				}
					
				/* Positioner 2*/
				if(strlen(scan2PosPV) > 0)
					pvAssign(scan2PosVal, scan2PosPV);
				if(strlen(scan2PosRdbkPV) > 0)
					pvAssign(scan2PosRdbk, scan2PosRdbkPV);
					
				if (showDebugMessages > 0)
				{
					printf("\nBatchscan message: state reInit: Positioner 2 is %s.\n", scan2PosPV);
					printf("\nBatchscan message: state reInit: Positioner 2 readback is %s.\n", scan2PosRdbkPV);
				}
				
				/* If the positioner is a motor record, then assign  variables to the high and low soft limits. */
				if (pos2IsMotor)
				{
					sprintf(pvName, "%s", strtok(scan2PosPV, "."));
					strcat(pvName, ".LLM");
					pvAssign(pos2LowLimit, pvName);
					
					sprintf(pvName, "%s", strtok(scan2PosPV, "."));
					strcat(pvName, ".HLM");
					pvAssign(pos2HighLimit, pvName);
				}
				else
				{
					pvAssign(pos2LowLimit,"");
					pvAssign(pos2HighLimit,"");
				}

				/* Positioner 3*/
				/* This positioner does not necessarily need to be assigned a real value. */
				if(strlen(scan3PosPV) > 0)
					pvAssign(scan3PosVal, scan3PosPV);
				if(strlen(scan3PosRdbkPV) > 0)
					pvAssign(scan3PosRdbk, scan3PosRdbkPV);
				
				if (showDebugMessages > 0)
				{
					printf("\nBatchscan message: state reInit: Positioner 3 is %s.\n", scan3PosPV);
					printf("\nBatchscan message: state reInit: Positioner 3 readback is %s.\n", scan3PosRdbkPV);
				}
				
				/* If the positioner is a motor record, then assign  variables to the high and low soft limits. */
				if (pos3IsMotor)
				{
					sprintf(pvName, "%s", strtok(scan3PosPV, "."));
					strcat(pvName, ".LLM");
					pvAssign(pos3LowLimit, pvName);
					
					sprintf(pvName, "%s", strtok(scan3PosPV, "."));
					strcat(pvName, ".HLM");
					pvAssign(pos3HighLimit, pvName);
				}
				else
				{
					pvAssign(pos3LowLimit,"");
					pvAssign(pos3HighLimit,"");
				}
				
				/*****************************************************************************************/				
				
				/* Write the name of the sample to the local PV for display on the batch scan screen. */
				pvGet(sampleName);
				strcpy(batchSample, sampleName);
				pvPut(batchSample);
				
				/* Set the input link of the sample name PV so that it updates on the batch scan screen
				   when the user changes it elsewhere. */
				strcpy(batchSampleInLink, sampleNamePV);
				strcat(batchSampleInLink, " CPP NMS");
				pvPut(batchSampleInLink);
				
				sprintf(errorMessage, "Connecting PVs.");
				pvPut(errorMessage);
			}
			initialize = 0;
			
	    } state pvsConnecting
	}
}

/* This state set monitors the batch to see if a scan should be aborted and whether it is an individual */
/* scan that is aborted or the whole batch.  It also checks to see if a batch should be paused. */
ss scan_control {

	state init {
	
		when () {
		
		} state abort_pause	
	}
	
	/* This state will either pause the batch or abort it. */
	state abort_pause {
	
		/*  Finish the current scan line, then abort the rest of the batch. */
		when (abortBatch) {
		
			pvGet(executingLine);
			
			for (controlLoop = (executingLine + 1); controlLoop < (MAXBATCHSIZE); controlLoop++)
			{
				scanMode[controlLoop] = SKIP;
				pvPut(scanMode[controlLoop]);
			}
			
			/* Since all the scans have been set to skip, execute the code that counts scans. */
			efSet(modeChange);
			abortBatch = 0;
			
		} state abort_pause
		
		/* Finish the current scan line, then pause until the user clicks continue. */
		when (pauseScan) {
		
			pvGet(executingLine);
			
			if (scanNumber < (MAXBATCHSIZE - 1))
			{
				scanMode[executingLine + 1] = PAUSE; 
				pvPut(scanMode[executingLine + 1]);
			}
			
			pauseScan = 0;
			
		} state abort_pause
		
		/* Abort the current scan.  The batch will continue with the next scan. */
		when (abortScan) {
		
			scanRecAbort = 1;
			pvPut(scanRecAbort);
			
			abortScan = 0;
			
		} state abort_pause
		
		/* Abort the current scan line as well as the rest of the batch. */
		when (abortAll || efTestAndClear(scanErrorFlag))
		{
			pvGet(executingLine);
			
			for (controlLoop = (executingLine + 1); controlLoop < (MAXBATCHSIZE); controlLoop++)
			{
				scanMode[controlLoop] = SKIP;
				pvPut(scanMode[controlLoop]);
			}
			
			/* If the scan being executed is a 3D scan, make sure that the program doesn't just
			   continue with the next 2D portion of the scan. */
			remainingScan3Points = 0;
			pvPut(remainingScan3Points);
			
			scanRecAbort = 1;
			pvPut(scanRecAbort);
			
			/* Since all the scans have been set to skip, execute the code that counts scans. */
			efSet(modeChange);
			
			scanRecAbort = 0;
			abortAll = 0;
			
		} state abort_pause
	}
}

/* This state set allows the user to import/export scans configurations to/from the scan records.  It also allows */
/* the user to clear a single scan or all of the scans at once.  Lastly, the user can clear all comment fields. */
/* These actions will only occur if the allPvsConnected variable is true. */
ss modify_scans {

	state init {
	
		when () {
		
		} state load_scans
	}
		
	/* This state can load values from a scan record to the batch scan table, load values from the batch scan table
	   into a scan record, zero lines of the batch scan, zero all lines, or clear all comments and messages.*/	
	state load_scans {
	
		/* Load values from the currently connected scan records into the batch scan table.*/
	    when(loadFromScan) {
		
			if (allPvsConnected)
			{
				pvGet(scanNumber);
			
				/* Get the scan record information. */
				pvGet(dwellTime);
				pvGet(scan1RecNumPts);
				pvGet(scan1RecWidth);
				pvGet(scan2RecNumPts);
				pvGet(scan2RecWidth);
				pvGet(scan1PosVal);
				pvGet(scan2PosVal);
				pvGet(comment);

				/* Assign the scan record information to the batch scan variables. */
				scanDwellTime[scanNumber] = dwellTime;									
				scan1Center[scanNumber] = scan1PosVal;
				scan1NumPts[scanNumber] = scan1RecNumPts;
				scan1Width[scanNumber] = scan1RecWidth;
				scan2Center[scanNumber] = scan2PosVal;
				scan2NumPts[scanNumber] = scan2RecNumPts;
				scan2Width[scanNumber] = scan2RecWidth;
				strcpy(scanComment[scanNumber], comment);
				scanMode[scanNumber] = NORMAL;

				/* Put the scan record information into the batch scan database. */
				pvPut(scanDwellTime[scanNumber]);
				pvPut(scan1Center[scanNumber]);
				pvPut(scan1NumPts[scanNumber]);
				pvPut(scan1Width[scanNumber]);
				pvPut(scan2Center[scanNumber]);
				pvPut(scan2NumPts[scanNumber]);
				pvPut(scan2Width[scanNumber]);
				pvPut(scanComment[scanNumber]);
				pvPut(scanMode[scanNumber]);
				
				/* Trigger an update of the estimated time to complete the batch. */
				efSet(updateTime);
			}
			else
				printf("\nBatchscan messge: state load_scans: Error - not all batch scan variables connected.\n");
			
			loadFromScan = 0;

	    } state load_scans
	  	
	  	/* Send the information for an entry in the batch scan table to the connected scan records */
	  	/* where it can be executed. */
	    when(loadToScan && !batchRunning) {
	
			if (allPvsConnected)
			{
				pvGet(scanNumber);

				/* Get the values from the correct entry in the batch scan table. */
				pvGet(scanDwellTime[scanNumber]);			
				pvGet(scan1Center[scanNumber]);
				pvGet(scan2Center[scanNumber]);
				pvGet(scan1NumPts[scanNumber]);
				pvGet(scan2NumPts[scanNumber]);
				pvGet(scan1Width[scanNumber]);
				pvGet(scan2Width[scanNumber]);
				pvGet(scanComment[scanNumber]);
			
				/* Assign the batch scan table information to the scan record variables. */
				dwellTime = scanDwellTime[scanNumber];
				scan1PosVal = scan1Center[scanNumber];
				scan2PosVal = scan2Center[scanNumber];
				scan1RecNumPts = scan1NumPts[scanNumber];
				scan2RecNumPts = scan2NumPts[scanNumber];
				scan1RecWidth = scan1Width[scanNumber];
				scan2RecWidth = scan2Width[scanNumber];
				strcpy(comment, scanComment[scanNumber]);
			
				/* Put the batch scan table information in the scan record database. */
				pvPut(dwellTime);
				pvPut(scan1PosVal);
				pvPut(scan2PosVal);
				pvPut(scan1RecNumPts);
				pvPut(scan2RecNumPts);
				pvPut(scan1RecWidth);
				pvPut(scan2RecWidth);
				pvPut(comment);
			}
			else
				printf("\nBatchscan messge: state load_scans: Error - not all batch scan variables connected.\n");
			
			loadToScan = 0;
			
					
	    } state load_scans
		
		/* Set all values in a line of the batch scan table to zero, clear all messages, and set */
		/* the mode for that line to skip. */
		when (zeroScan) {
		
			if (allPvsConnected)
			{
				pvGet(scanNumber);
				
				scanDwellTime[scanNumber] = 0;					
				scan1Center[scanNumber] = 0;
				scan1NumPts[scanNumber] = 0;
				scan1Width[scanNumber] = 0;
				scan2Center[scanNumber] = 0;
				scan2NumPts[scanNumber] = 0;
				scan2Width[scanNumber] = 0;
				scan3Center[scanNumber] = 0;
				scan3NumPts[scanNumber] = 0;
				scan3Width[scanNumber] = 0;
				scanMode[scanNumber] = SKIP;
				execTransform[scanNumber] = NEVER;
				sprintf(scanComment[scanNumber], " ");
				sprintf(fileName[scanNumber], " ");
				sprintf(scanStarted[scanNumber], " ");
				sprintf(scanEnded[scanNumber], " ");	
				
				pvPut(scanDwellTime[scanNumber]);	
				pvPut(scan1Center[scanNumber]);
				pvPut(scan1NumPts[scanNumber]);
				pvPut(scan1Width[scanNumber]);
				pvPut(scan2Center[scanNumber]);
				pvPut(scan2NumPts[scanNumber]);
				pvPut(scan2Width[scanNumber]);
				pvPut(scan3Center[scanNumber]);
				pvPut(scan3NumPts[scanNumber]);
				pvPut(scan3Width[scanNumber]);
				pvPut(scanMode[scanNumber]);
				pvPut(execTransform[scanNumber]);
				pvPut(scanComment[scanNumber]);
				pvPut(fileName[scanNumber]);
				pvPut(scanStarted[scanNumber]);
				pvPut(scanEnded[scanNumber]);
				
			}
			else
				printf("\nBatchscan messge: state load_scans: Error - not all batch scan variables connected.\n");
			
			zeroScan = 0;
			efSet(updateTime);

	    } state load_scans
		
		/* Set values for all lines of the batch scan table to zero, clear all messages, and set */
		/* all modes to skip. */
		when (zeroAllScans) {
		
			if (allPvsConnected)
			{
				for(modifyLoop = 0; modifyLoop < MAXBATCHSIZE; modifyLoop++)
				{
				
					scanDwellTime[modifyLoop] = 0;					
					scan1Center[modifyLoop] = 0;
					scan1NumPts[modifyLoop] = 0;
					scan1Width[modifyLoop] = 0;
					scan2Center[modifyLoop] = 0;
					scan2NumPts[modifyLoop] = 0;
					scan2Width[modifyLoop] = 0;
					scan3Center[modifyLoop] = 0;
					scan3NumPts[modifyLoop] = 0;
					scan3Width[modifyLoop] = 0;
					scanMode[modifyLoop] = SKIP;
					execTransform[modifyLoop] = NEVER;
					sprintf(scanComment[modifyLoop], " ");
					sprintf(fileName[modifyLoop], " ");
					sprintf(scanStarted[modifyLoop], " ");
					sprintf(scanEnded[modifyLoop], " ");	
				
					pvPut(scanDwellTime[modifyLoop]);	
					pvPut(scan1Center[modifyLoop]);
					pvPut(scan1NumPts[modifyLoop]);
					pvPut(scan1Width[modifyLoop]);
					pvPut(scan2Center[modifyLoop]);
					pvPut(scan2NumPts[modifyLoop]);
					pvPut(scan2Width[modifyLoop]);
					pvPut(scan3Center[modifyLoop]);
					pvPut(scan3NumPts[modifyLoop]);
					pvPut(scan3Width[modifyLoop]);
					pvPut(scanMode[modifyLoop]);
					pvPut(execTransform[modifyLoop]);
					pvPut(scanComment[modifyLoop]);
					pvPut(fileName[modifyLoop]);
					pvPut(scanStarted[modifyLoop]);
					pvPut(scanEnded[modifyLoop]);
				}
				
			}
			else
				printf("\nBatchscan messge: state load_scans: Error - not all batch scan variables connected.\n");
			
			zeroAllScans = 0;
			
			/* Trigger an update of the estimated time to comlete the batch scan. */
			/* It should be zero. */
			efSet(updateTime);

	    } state load_scans
		
		/* Clear all comments and messages. */
		when (clearComments) {
		
			if (allPvsConnected)
			{
				for (modifyLoop = 0; modifyLoop < MAXBATCHSIZE; modifyLoop++)
				{
					sprintf(scanComment[modifyLoop], " ");
					sprintf(fileName[modifyLoop], " ");
					sprintf(scanStarted[modifyLoop], " ");
					sprintf(scanEnded[modifyLoop], " ");
					
					pvPut(scanComment[modifyLoop]);
					pvPut(fileName[modifyLoop]);
					pvPut(scanStarted[modifyLoop]);
					pvPut(scanEnded[modifyLoop]);
				}
			}
			else
				printf("\nBatchscan messge: state load_scans: Error - not all batch scan variables connected.\n");
				
			clearComments = 0;
			
		}state load_scans
		
		/* Reset the number of points that the 3rd positioner will perform back to 1.
			Do this for all scans. */
		when (resetPos3) {
		
			if (allPvsConnected)
			{
				for (modifyLoop = 0; modifyLoop < MAXBATCHSIZE; modifyLoop++)
				{
					scan3NumPts[modifyLoop] = 1;
					pvPut(scan3NumPts[modifyLoop]);
				}					
			}
			else
				printf("\nBatchscan messge: state load_scans: Error - not all batch scan variables connected.\n");
				
			resetPos3 = 0;
			
		} state load_scans
		
		/* Reset the number of points that the 3rd positioner will perform back to 0.
			Do this for all scans. */
		when (zeroPos3) {
		
			if (allPvsConnected)
			{
				for (modifyLoop = 0; modifyLoop < MAXBATCHSIZE; modifyLoop++)
				{
					scan3NumPts[modifyLoop] = 0;
					pvPut(scan3NumPts[modifyLoop]);
				}					
			}
			else
				printf("\nBatchscan messge: state load_scans: Error - not all batch scan variables connected.\n");
				
			zeroPos3 = 0;
			
		} state load_scans
	} 
}

ss calculate_data {

	char message[40];
	int scanLimitError = 0;
	int batchLimitError = 0;

	state init {
	
		when() {
		
		} state calculate
		
	}

	/* This state will calculate the total length of time to complete a batch, what time it should finish, and gives the
	   time of that last estimate.  It can recalulate the number of points based on a user supplied step size and
	   it can check all scans for motor soft limit violations. */
	state calculate {

		/* Execute this code when another section triggers the updateTime flag, or when a user clicks on one of the */
		/* two calculate buttons. */
		when (efTestAndClear(updateTime) || calculateTime || calculatePoints || checkLimits) {

			if (calculatePoints)
			{
				pvGet(xStepSize);
				pvGet(yStepSize);
				
				if (calculatePoints == 2) /* Calculate number of steps for each scan in the table */
				{
					for (timeLoop = 0; timeLoop < MAXBATCHSIZE; timeLoop++)
					{
						/* Get the width of the inner and outer loops of the scan. */
						pvGet(scan1Width[timeLoop]);
						pvGet(scan2Width[timeLoop]);
					
						if ((scan1Width[timeLoop] != 0) && (scan2Width[timeLoop] != 0))
						{
							/* Divide the width of the  inner scan by the step size the user entered. */
							/* Save the remainder.   If the remainder is greater than 0.5, add 1 to the */
							/* number of points. */
							pointsRemainder = modf(fabs(scan1Width[timeLoop] / xStepSize), &quotient);
						
							if (pointsRemainder >= 0.5)
								quotient++;
							
							scan1NumPts[timeLoop] = quotient + 1;
						
							/* Divide the width of the  outer scan by the step size the user entered. */
							/* Save the remainder.   If the remainder is greater than 0.5, add 1 to the */
							/* number of points. */
							pointsRemainder = modf(fabs(scan2Width[timeLoop] / yStepSize), &quotient);
						
							if (pointsRemainder >= 0.5)
								quotient++;
							
							scan2NumPts[timeLoop] = quotient + 1;
							
							/* Write the number of points to the table. */			
							pvPut(scan1NumPts[timeLoop]);
							pvPut(scan2NumPts[timeLoop]);
						}
					}
				}
				
				if (calculatePoints == 1) /* Calculate number of points for current scan. */
				{
					/* Get the current scan number. */
					pvGet(scanNumber);
					
					/* Get the width of the inner and outer loops of the scan. */
					pvGet(scan1Width[scanNumber]);
					pvGet(scan2Width[scanNumber]);
					
					if ((scan1Width[scanNumber] != 0) && (scan2Width[scanNumber] != 0))
					{
						/* Divide the width of the  inner scan by the step size the user entered. */
						/* Save the remainder.   If the remainder is greater than 0.5, add 1 to the */
						/* number of points. */
						pointsRemainder = modf(fabs(scan1Width[scanNumber] / xStepSize), &quotient);
						
						if (pointsRemainder >= 0.5)
							quotient++;
							
						scan1NumPts[scanNumber] = quotient + 1;
						
						/* Divide the width of the  outer scan by the step size the user entered. */
						/* Save the remainder.   If the remainder is greater than 0.5, add 1 to the */
						/* number of points. */
						pointsRemainder = modf(fabs(scan2Width[scanNumber] / yStepSize), &quotient);
						
						if (pointsRemainder >= 0.5)
							quotient++;
							
						scan2NumPts[scanNumber] = quotient + 1;
						
						/* Write the number of points to the table. */
						pvPut(scan1NumPts[scanNumber]);
						pvPut(scan2NumPts[scanNumber]);
					}
				}
				
			}
			
			/* Make sure that the positioners will not attempt to move outside of
			 * the soft limits during a scan.  This only works if the positioners
			 * are motor records. */
			if (checkLimits)
			{
				sprintf(message, "Scans");
				batchLimitError = 0;
				
				pvGet(pos1IsMotor);
				pvGet(pos2IsMotor);
				pvGet(pos3IsMotor);
				
				if (pos1IsMotor)
				{
					pvGet(pos1HighLimit);
					pvGet(pos1LowLimit);
				}
				
				if (pos2IsMotor)
				{
					pvGet(pos2HighLimit);
					pvGet(pos2LowLimit);
				}
				
				if (pos3IsMotor)
				{
					pvGet(pos3HighLimit);
					pvGet(pos3LowLimit);
				}
				
				for (timeLoop = 0; timeLoop < MAXBATCHSIZE; timeLoop++)
				{
			
					scanLimitError = 0;
					pvGet(scanMode[timeLoop]);
					
					if (scanMode[timeLoop] == NORMAL)
					{
			
						if (pos1IsMotor)
						{
						
							pvGet(scan1Center[timeLoop]);
							pvGet(scan1Width[timeLoop]);
				
							if ((scan1Center[timeLoop] - (fabs(scan1Width[timeLoop]) / 2)) < pos1LowLimit)
							{
								scanLimitError = 1;
					
							}
				
				 			if ((scan1Center[timeLoop] + (fabs(scan1Width[timeLoop]) / 2)) > pos1HighLimit)
							{
							scanLimitError = 1;
							}
						}
			
						if (pos2IsMotor)
						{
							pvGet(scan2Center[timeLoop]);
							pvGet(scan2Width[timeLoop]);	
				
							if ((scan2Center[timeLoop] - (fabs(scan2Width[timeLoop]) / 2)) < pos2LowLimit)
							{
								scanLimitError = 1;
							}
				
				 			if ((scan2Center[timeLoop] + (fabs(scan2Width[timeLoop]) / 2)) > pos2HighLimit)
							{
								scanLimitError = 1;
							}
						}
			
						if (pos3IsMotor)
						{
							pvGet(scan3NumPts[timeLoop]);
				
							if (scan3NumPts[timeLoop] > 0)
							{
								pvGet(scan3Center[timeLoop]);
								pvGet(scan3Width[timeLoop]);
					
								if ((scan3Center[timeLoop] - (fabs(scan3Width[timeLoop]) / 2)) < pos3LowLimit)
								{
									scanLimitError = 1;
								}
				
				 				if ((scan3Center[timeLoop] + (fabs(scan3Width[timeLoop]) / 2)) > pos3HighLimit)
								{
									scanLimitError = 1;
								}
							}
						}
			
						if (scanLimitError)
						{
							sprintf(message, "%s %d", message, timeLoop);
							batchLimitError = 1;
						}
					}
				}
				
				if (batchLimitError)
				{
					sprintf(message, "%s have limit errors.", message);
					sprintf(errorMessage, message);
					pvPut(errorMessage);
				}
				else
				{
					sprintf(errorMessage, "All scans within motor limits.");
					pvPut(errorMessage);
				}
			}
		
			/* Initialize the time variables to 0. */
			batchTime = 0;
			hours = 0;
			minutes = 0;
			seconds = 0;
			
			pvGet(overhead);
		
			/* Get the dwell time, number of points, and the mode for each scan. */
			for (timeLoop = 0; timeLoop < MAXBATCHSIZE; timeLoop++)
			{
				pvGet(scanDwellTime[timeLoop]);
				pvGet(scan1NumPts[timeLoop]);
				pvGet(scan2NumPts[timeLoop]);
				pvGet(scan3NumPts[timeLoop]);
				
				/* If the scan mode is normal and the scan has not already been run, then compute the time remaining for the batch. */
				/* The numPtsComplete adjusts for each line completed by the inner loop of the scan. The scan3TimeFactor adjusts  */
				/* for the presence of a 3rd positioner that would cause a 2D scan to run more than once. */
				if ((scanMode[timeLoop] == NORMAL) && (scanComplete[timeLoop] == FALSE))
				{
				
					
					if (scan3NumPts[timeLoop] < 1)
						scan3TimeFactor = 1;
					else							
						scan3TimeFactor = scan3NumPts[timeLoop];					
					
					if (scanType == STEP)
						batchTime = batchTime + (scanDwellTime[timeLoop] + overhead) * ((scan1NumPts[timeLoop] * scan2NumPts[timeLoop] * scan3TimeFactor)
					                                                                	- (scan1NumPts[timeLoop] * numPtsComplete[timeLoop]));
					else
						batchTime = batchTime + (((scanDwellTime[timeLoop] / 1000) * scan1NumPts[timeLoop]) + overhead) * ((scan2NumPts[timeLoop] * scan3TimeFactor) - (numPtsComplete[timeLoop]));
					
					if (showDebugMessages > 2)
					{
						printf("\nBatchscan message: state calculate: Dwell time for scan %d is %f.\n", timeLoop, scanDwellTime[timeLoop]);
						printf("\nBatchscan message: state calculate: Overhead for scan %d is %f.\n", timeLoop, overhead);
						printf("\nBatchscan message: state calculate: Number of points per line for scan %d is %d.\n", timeLoop, scan1NumPts[timeLoop]);
						printf("\nBatchscan message: state calculate: Number of lines for scan %d is %d.\n", timeLoop, scan2NumPts[timeLoop]);
						printf("\nBatchscan message: state calculate: Number of 2D scans for scan %d is %d.\n", timeLoop, scan3TimeFactor);
					}			
																									
				}
			}
			
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state calculate: Time remaining for batch is %f.\n", batchTime);


			/* See epicsTime.h in the Application Developer's Guide for function and data type information. */
			/* Get the current time from the operating system.  Convert it to a string and write it to a PV. */
			epicsTimeGetCurrent(&timeStamp);
			epicsTimeToStrftime(timeString, sizeof(timeString), "%a %b %d %Y %H:%M:%S.%f", &timeStamp);			
			strcpy (lastEstimate, timeString);			
			pvPut(lastEstimate);

			/* Take the estimated number of seconds for completing the batch and add it to the current time. */
			/* Convert that value to a string and then write it to a PV. */
			epicsTimeAddSeconds(&timeStamp, batchTime);
			epicsTimeToStrftime(timeString, sizeof(timeString), "%a %b %d %Y %H:%M:%S.%f", &timeStamp);
			strcpy (estimateScanDone, timeString);			
			pvPut(estimateScanDone);

			/* Calculate the number hours, minutes, and seconds it will take to complete the batch scan. */
			if (batchTime > 3600.0)
			{
				hours = floor(batchTime / 3600.0);
				batchTime = (batchTime - (hours * 3600.0));
			}

			if (batchTime > 60.0)
			{
				minutes = floor(batchTime / 60.0);
				batchTime = (batchTime - (minutes * 60.0));
			}

			seconds = floor(batchTime);

			sprintf(timeToComplete, "%.0fhrs %.0fmin %.0fsec", hours, minutes, seconds);
			pvPut(timeToComplete);
			
			calculateTime = 0;
			calculatePoints = 0;
			checkLimits = 0;
			
		} state calculate
	
	} 
}

/* This state set handles the execution of the batch.  It will step through the table, loading and running each scan. */
ss execute_batch {

	state init {
	
		when() {
		
		} state setup_scan
		
	}
	
	state setup_scan {
	
		/* The batch will not start if all variables are not connected to their Epics PVs. */
		when(beginScan && allPvsConnected && !batchRunning && !disable) {
		
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state setup_scan: Executing state setup_scan.\n");
			
			executingLine = 0;
			scanPaused = FALSE;
			beginScan = FALSE;
			scanValid = TRUE;
			batchRunning = TRUE;
			pvPut(batchRunning);
			
			sprintf(errorMessage, "All batch scan variables connected.");
			pvPut(errorMessage);
			
			/* Get the saveData path. */
			pvGet(saveDataPath);
			pvGet(logFileMount);
			sprintf(scanInfo.path, "%s%s", logFileMount, saveDataPath);
			scanInfo.newFile = TRUE;
			
			pvGet(scanType);
			
		} state check_scanline
		
	}
	
	state check_scanline {
	
		char message[40];
		int limit1Error = 0;
		int limit2Error = 0;
		int limit3Error = 0;
		
		entry {
						
			pvGet(pos1IsMotor);
			pvGet(pos2IsMotor);
			pvGet(pos3IsMotor);
			
			limit1Error = 0;
			limit2Error = 0;
			limit3Error = 0;
			
			if (pos1IsMotor)
			{
				pvGet(pos1HighLimit);
				pvGet(pos1LowLimit);
				pvGet(scan1Center[executingLine]);
				pvGet(scan1Width[executingLine]);
				
				if ((scan1Center[executingLine] - (fabs(scan1Width[executingLine]) / 2)) < pos1LowLimit)
				{
					scanMode[executingLine] = SKIP;
					limit1Error = 1;
					
				}
				
				 if ((scan1Center[executingLine] + (fabs(scan1Width[executingLine]) / 2)) > pos1HighLimit)
				{
					scanMode[executingLine] = SKIP;
					limit1Error = 1;
				}
				
				if (limit1Error)
					strcat(message, " 1");
	
			}
			
			if (pos2IsMotor)
			{
				pvGet(pos2HighLimit);
				pvGet(pos2LowLimit);
				pvGet(scan2Center[executingLine]);
				pvGet(scan2Width[executingLine]);	
				
				if ((scan2Center[executingLine] - (fabs(scan2Width[executingLine]) / 2)) < pos2LowLimit)
				{
					scanMode[executingLine] = SKIP;
					limit2Error = 1;
				}
				
				 if ((scan2Center[executingLine] + (fabs(scan2Width[executingLine]) / 2)) > pos2HighLimit)
				{
					scanMode[executingLine] = SKIP;
					limit2Error = 1;
				}
				
				if (limit2Error)
					strcat(message, " 2");

			}
			
			if (pos3IsMotor)
			{
				pvGet(scan3NumPts[executingLine]);
				
				if (scan3NumPts[executingLine] > 0)
				{
					pvGet(pos3HighLimit);
					pvGet(pos3LowLimit);
					pvGet(scan3Center[executingLine]);
					pvGet(scan3Width[executingLine]);
					
					if ((scan3Center[executingLine] - (fabs(scan3Width[executingLine]) / 2)) < pos3LowLimit)
					{
						scanMode[executingLine] = SKIP;
						limit3Error = 1;
					}
				
				 	if ((scan3Center[executingLine] + (fabs(scan3Width[executingLine]) / 2)) > pos3HighLimit)
					{
						scanMode[executingLine] = SKIP;
						limit3Error = 1;
					}
					
					if (limit3Error)
						strcat(message, " 3");					
				}
			}
			
			if (limit1Error || limit2Error || limit3Error)
			{
				strcat(message, " scan outside limits");
				strcpy(fileName[executingLine], message);
				pvPut(scanMode[executingLine]);
				pvPut(fileName[executingLine]);
				
			}
			
		}
	
		when (efTestAndClear(resetBatchFlag)) {
		
			if (resetBatch == 1)
			{
		
				printf("\nBatchscan message: state wait_for_scan: Resetting batch scan to initial state.\n");
			
				executingLine = MAXBATCHSIZE + 1;
				pvPut(executingLine);
			}
			
		} state check_scanline
	
		/* If the current scan to be run is larger than the number of the last scan in the batch table */
		/* whose mode is NORMAL, than the batch is finished.  Reset the numPtsComplete array to all */
		/* elements being zero. */
		when ((executingLine > lastScan) || (executingLine >= MAXBATCHSIZE) || disable)
		{
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state check_scanline: Executing state check_scanline with with invalid value of executingLine.\n");
		
			sprintf(scanStatus, "Batch finished.");
			pvPut(scanStatus);
			
			for (scanLoop = 0; scanLoop < MAXBATCHSIZE; scanLoop++)
			{
				numPtsComplete[scanLoop] = 0;
				pvPut(numPtsComplete[scanLoop]);
				scanComplete[scanLoop] = FALSE;
				pvPut(scanComplete[scanLoop]);
				transformComplete[scanLoop] = FALSE;
				pvPut(transformComplete[scanLoop]);
			}
			
			executingLine = -1;
			pvPut(executingLine);
			
			batchRunning = FALSE;
			pvPut(batchRunning);
			
			beginScan = 0;
			
			efSet(updateTime);
		
		} state setup_scan
		
		/* If the current scan to be run is both less than the number of the last scan whose mode is normal */
		/* and the maximum number of scans allowed, then get some preliminary values and continue. */
		when ((executingLine <= lastScan) && (executingLine < MAXBATCHSIZE) && !disable)
		{
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state check_scanline: Executing state check_scanline with with valid value of executingLine.\n");
		
			/* Set the current scan line. */
			pvPut(executingLine);
			
			pvGet(execTransform[executingLine]);
			
			sprintf(scanStatus, "Setting up scan line %d.", executingLine);
			pvPut(scanStatus);

			pvGet(scan1Execute);
			pvGet(scan2Execute);
						
		} state execute_scanline
	}
	
	/* This state will load all of the values from a line in the batch table into the scan records and then start the scan. 
	   If the current line mode is PAUSE or SKIP, it either suspends operation or goes to the next line. */
	state execute_scanline {
		option -e;		/* Execute the entry block every time, even if reentering from this state. */
	
		entry {
		
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state execute_scanline: Entering state execute_scanline.\n");
			
		}
		
		when (efTestAndClear(resetBatchFlag)) {
		
			if (resetBatch == 1)
			{
		
				printf("\nBatchscan message: state execute_scanline: Resetting batch scan to initial state.\n");
			
				executingLine = MAXBATCHSIZE + 1;
				pvPut(executingLine);
			}
			
		} state check_scanline
		
		/* This statement is true if the transform record will not execute */
		when (execTransform[executingLine] == NEVER && transformComplete[executingLine] == FALSE && (scanMode[executingLine] == NORMAL)) {
			
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state execute_scanline: No transform records will be executed this scan.\n");
			
			transformComplete[executingLine] = TRUE;
			pvPut(transformComplete[executingLine]);
			
		} state check_scanline
		
		/* This statement is true if the transform record should process before the scan is run. */
		when (execTransform[executingLine] == BEFORE && scanComplete[executingLine] == FALSE && (scanMode[executingLine] == NORMAL) 
			&& transformComplete[executingLine] == FALSE) {
			
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state execute_scanline: Executing transform record before scan.\n");
		
			if (executingLine <= lastScan)
			{
				transformComplete[executingLine] = WORKING;
				pvPut(transformComplete[executingLine]);
				sprintf(scanStatus, "Executing Transform %d.", executingLine);
				pvPut(scanStatus);
					
				procTransform[executingLine] = 1;
				pvPut(procTransform[executingLine], ASYNC);				
			}
		
		} state wait_for_transform
		
		/* This statement is true if the transform record should process after the scan is run. */
		when (execTransform[executingLine] == AFTER && scanComplete[executingLine] == TRUE && (scanMode[executingLine] == NORMAL)
			&& transformComplete[executingLine] == FALSE) {
			
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state execute_scanline: Executing transform record after scan.\n");
		
			if (executingLine <= lastScan)
			{
				transformComplete[executingLine] = WORKING;
				pvPut(transformComplete[executingLine]);
				sprintf(scanStatus, "Executing Transform %d.", executingLine);
				pvPut(scanStatus);
				
				procTransform[executingLine] = 1;
				pvPut(procTransform[executingLine], ASYNC);		
			}
		
		} state wait_for_transform
	
		/* If the mode of the current scan is normal and the number of the scan is less than the */
		/* maximum allowed and the scan record's busy fields are set to zero and the scan records */
		/* are idle and there are currently no transform records that must be processes, then begin executing the scan. */

		when ((scanMode[executingLine] == NORMAL) && (executingLine <= lastScan) && (scan1Execute == 0) && (scan2Execute == 0) &&
			(scan1Busy == 0) && (scan2Busy == 0) && ((transformComplete[executingLine] == TRUE) || (transformComplete[executingLine] == FALSE
			&&  execTransform[executingLine] == AFTER)) && scanComplete[executingLine] == FALSE) {
			
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state execute_scanline: Ready to start the scan.\n");
						
			sprintf(scanStatus, "Setting up scan line %d.", executingLine);
			pvPut(scanStatus);
			
			/* Get all of the parameters for the scan that needs to be run. */
			pvGet(scanDwellTime[executingLine]);					
			pvGet(scan1Center[executingLine]);
			pvGet(scan2Center[executingLine]);
			pvGet(scan1NumPts[executingLine]);
			pvGet(scan2NumPts[executingLine]);
			pvGet(scan1Width[executingLine]);
			pvGet(scan2Width[executingLine]);
			pvGet(scan3Center[executingLine]);
			pvGet(scan3NumPts[executingLine]);
			pvGet(scan3Width[executingLine]);
			pvGet(scanComment[executingLine]);
			
			/* Calculate how the 3rd positioner is to be moved, it start and end points, and the number of points. */
			/* If the width of the movement is zero and there is less than 1 point, then use default values. */
			if ((scan3Width[executingLine] != 0) && (scan3NumPts[executingLine] > 1))
			{
				if (showDebugMessages > 0)
					printf("\nBatchscan message: Calculating positioner 3 parameters.\n");
			
				pos3Increment = scan3Width[executingLine] / (scan3NumPts[executingLine] - 1);
				pos3Start = scan3Center[executingLine] - (scan3Width[executingLine] / 2);
				pos3End = scan3Center[executingLine] + (scan3Width[executingLine] / 2);
				remainingScan3Points = scan3NumPts[executingLine];
				
				if (showDebugMessages > 1)
				{
					printf("\nBatchscan message: state execute_scanline: Positioner 3 scan increment is %f.\n", pos3Increment);
					printf("\nBatchscan message: state execute_scanline: Positioner 3 scan start position is %f.\n", pos3Start);
					printf("\nBatchscan message: state execute_scanline: Positioner 3 scan end position is %f.\n", pos3End);
					printf("\nBatchscan message: state execute_scanline: Positioner 3 scan number of points is %d.\n", remainingScan3Points);
				}
					
				pvPut(remainingScan3Points);
			}
			else
			{
				if (showDebugMessages > 0)
					printf("\nBatchscan message: state execute_scanline: Positioner 3 is not being used in this scan.\n");
				
				pos3Increment = 0;
				pos3Start = scan3Center[executingLine];
				pos3End = scan3Center[executingLine];
				remainingScan3Points = scan3NumPts[executingLine];
				pvPut(remainingScan3Points);
			}
			
			/* Make sure that there are valid values for the parameters that were just retrieved. */
			if ((scanDwellTime[executingLine] != 0) && (scan1NumPts[executingLine] != 0) && (scan1Width[executingLine] != 0) &&
				(scan2NumPts[executingLine] != 0) && (scan2Width[executingLine] != 0))
			{				
				if (showDebugMessages > 0)
					printf("\nBatchscan message: state execute_scanline: Scan parameters are valid.\n");
					
				scanValid = TRUE;
								
				/* Get the current time and display it. */
				epicsTimeGetCurrent(&timeStamp);
				epicsTimeToStrftime(timeString, sizeof(timeString), "%a %b %d %Y %H:%M:%S.%f", &timeStamp);			
				strcpy (lastAlive, timeString);			
				pvPut(lastAlive);
							
				/* Set the scan record variables to the values that were retrieved from the batch table. */
				dwellTime = scanDwellTime[executingLine];
				scan1RecNumPts = scan1NumPts[executingLine];
				scan2RecNumPts = scan2NumPts[executingLine];
				scan1RecWidth = scan1Width[executingLine];
				scan2RecWidth = scan2Width[executingLine];
				strcpy(comment, scanComment[executingLine]);
				
				if (showDebugMessages > 0)
					printf("\nBatchscan message: state execute_scanline: Setting starting motor positions.\n");
			
				/* Write the values to the scan PVs. */
				pvPut(dwellTime, SYNC);
				
				pvPut(scan1RecNumPts, SYNC);
				pvPut(scan2RecNumPts, SYNC);
				pvPut(scan1RecWidth, SYNC);
				pvPut(scan2RecWidth, SYNC);
				pvPut(comment, SYNC);
					
				/* When these are set, the state sets move_positioner_X will see this and write
				   a value to the motor pvs. */
				if (showDebugMessages)
					printf("\nBatchscan message: state execute_scanline: Signaling motors to move.\n");	
				
				scan1PosVal = scan1Center[executingLine];
				scan2PosVal = scan2Center[executingLine];
				scan3PosVal = scan3Center[executingLine];
				
				pvPut(scan1PosVal, ASYNC);
				pvPut(scan2PosVal, ASYNC);
				if (scan3NumPts[executingLine] != 0)
					pvPut(scan3PosVal, ASYNC);	

				strcpy(scanStarted[executingLine], lastAlive);
				pvPut(scanStarted[executingLine]);
				
			}
			else
			{
				if (showDebugMessages > 0)
					printf("\nBatchscan message: state execute_scanline: Scan parameters are not valid.\n");
					
				/* If the values in the batch table for a particular scan are not valid, then change */
				/* that scan's mode to SKIP and go to the next scan. */
				if (showDebugMessages)
					printf("\nBatchscan messge: state execute_scanline: Scan values are zero, skipping to next line.\n");
				scanMode[executingLine] = SKIP;
				pvPut(scanMode[executingLine]);
				scanValid = FALSE;

			}
			
		} state wait_for_positioners
		
		/* When the scan mode is SKIP, simply increment the number of the scan being run and continue. */
		when (scanMode[executingLine] == SKIP) {
		
			if (showDebugMessages > 0)
					printf("\nBatchscan message: state execute_scanline: Skipping scan %d.\n", executingLine);

			executingLine++;
			
		} state check_scanline
		
		/* Pause the batch after the current scan is finished */
		when (scanMode[executingLine] == PAUSE) {
		
			if (showDebugMessages > 0)
					printf("\nBatchscan message: state execute_scanline: Pausing batch scan.\n");
		
			continueScan = FALSE;
			scanPaused = TRUE;
			
			sprintf(scanStatus, "Paused on scan line %d.", executingLine);
			pvPut(scanStatus);
			
		} state wait_for_scan				
	}
	
	state wait_for_transform {
	
		/* This statement is true when a transform record was processed before the scan was run. */
		when (pvPutComplete(procTransform[executingLine]) && execTransform[executingLine] == BEFORE && scanComplete[executingLine] == FALSE) {
		
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state execute_scanline: A transform record has been run before the scan.\n");
		
			transformComplete[executingLine] = TRUE;
			pvPut(transformComplete[executingLine]);
		
		} state check_scanline
		
		/* This statement is true when a transform record was processed after the scan was run. */
		when (pvPutComplete(procTransform[executingLine]) && execTransform[executingLine] == AFTER && scanComplete[executingLine] == TRUE) {
		
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state execute_scanline: A transform record has been run after the scan.\n");
				
			transformComplete[executingLine] = TRUE;
			pvPut(transformComplete[executingLine]);
			
			/* Since this is the last thing done before moving on to the next scan, increment the */
			/* value of executingLine. */
			executingLine++;
			
		} state check_scanline
	
	}
	
	state wait_for_positioners {
	
		when (efTestAndClear(resetBatchFlag)) {
		
			if (resetBatch == 1)
			{
		
				printf("\nBatchscan message: state wait_for_positioners: Resetting batch scan to initial state.\n");
			
				executingLine = MAXBATCHSIZE + 1;
				pvPut(executingLine);
			}
			
		} state check_scanline
		
		/* The scan parameters were not valid, so set the transform as complete, increment the current batch line
		 * number, and return to the beginning of the process. */
		when (scanValid == FALSE) {
		
			transformComplete[executingLine] = TRUE;
			pvPut(transformComplete[executingLine]);
			
			executingLine++;
		
		} state check_scanline
			
		/* This executes when all positioners are finished moving and */
		/* the number of points to do for positioner 3 is greater than zero. */
		when (pvPutComplete(scan1PosVal) && pvPutComplete(scan2PosVal) && pvPutComplete(scan3PosVal) && delay(1.0)) {
		
			float xDelta;
			float yDelta;
			float zDelta;

			if (showDebugMessages)
					printf("\nBatchscan message: state wait_for_positioners: Executing state wait_for_positioners.\n");
		
			pvGet(scan1PosVal);
			pvGet(scan1PosRdbk);
			pvGet(scan2PosVal);
			pvGet(scan2PosRdbk);
			pvGet(scan3PosVal);
			pvGet(scan3PosRdbk);
			pvGet(scan1Center[executingLine]);
			pvGet(scan2Center[executingLine]);
			pvGet(scan3Center[executingLine]);

			pvGet(maxDeltaPos1);
			pvGet(maxDeltaPos2);
			pvGet(maxDeltaPos3);
				
			xDelta = fabs(scan1PosVal - scan1PosRdbk);
			yDelta = fabs(scan2PosVal - scan2PosRdbk);
			zDelta = fabs(scan3PosVal - scan3PosRdbk);
			
			if ((scan1PosVal == scan1Center[executingLine]) && (scan2PosVal == scan2Center[executingLine]) && ((scan3NumPts[executingLine] == 0) || (scan3PosVal == scan3Center[executingLine])))
			{
			
				if ((xDelta > maxDeltaPos1) || (yDelta > maxDeltaPos2) || (zDelta > maxDeltaPos3))
				{
					if (showDebugMessages > 0)
						printf("\nBatchscan message: state wait_for_positioners: Possible motor position error. Readback value is different than commanded value. \n");
			
					errorCount++;
				}
				else
				{
					if (showDebugMessages > 0)
						printf("\nBatchscan message: state wait_for_positioners: Motor positioner error acceptable.\n");
					
					errorCount = 0;
					positionChecked = TRUE;
				}
			}
			else
			{
				if (showDebugMessages > 0)
						printf("\nBatchscan message: state wait_for_positioners: Possible motor position error. Commanded value does not equal center.\n");
				errorCount++;			
			}
			
		} state check_motor_error
	}
	
	state wait_for_positioner3 {
	
		when (efTestAndClear(resetBatchFlag)) {
		
			if (resetBatch == 1)
			{
		
				printf("\nBatchscan message: state wait_for_scan: Resetting batch scan to initial state.\n");
			
				executingLine = MAXBATCHSIZE + 1;
				pvPut(executingLine);
			}
			
		} state check_scanline
	
		when (pvPutComplete(scan3PosVal)) {
				
			remainingScan3Points--;
			pvPut(remainingScan3Points);	
			
			if (showDebugMessages > 1)
			{					
				printf("\nBatchscan message: state wait_for_positioner3: There are %d points remaining for positioner 3.\n", remainingScan3Points);
			}
			
		} state begin_scan
	}
	
	state check_motor_error {
		option -e;
		
		entry {
		
			if (showDebugMessages > 2)
			{
				printf("\nBatchscan message: state check_motor_error: Motor error count is %d.\n", errorCount);
				printf("\nBatchscan message: state check_motor_error: Value of positionChecked is %d.\n", positionChecked);
				printf("\nBatchscan message: state check_motor_error: Positioner 3 has %d points.\n", remainingScan3Points);
			}
		}
	
		when (efTestAndClear(resetBatchFlag)) {
		
			if (resetBatch == 1)
			{
		
				printf("\nBatchscan message: state wait_for_scan: Resetting batch scan to initial state.\n");
			
				executingLine = MAXBATCHSIZE + 1;
				pvPut(executingLine);
			}
			
		} state check_scanline
	
		/* If the motors did not move, try again to move them.  This is only tried a limited number of times. */
		when ((errorCount > 0) && (errorCount < 4)) {
			
			if (showDebugMessages  > 0)
				printf("\nBatchscan message: state check_motor_error: Motor error too large, trying again.\n");
				
			pvPut(scan1PosVal, ASYNC);
			pvPut(scan2PosVal, ASYNC);
			if (scan3NumPts[executingLine] != 0)
				pvPut(scan3PosVal, ASYNC);	
		} state wait_for_positioners
		
		/* If the motors have failed to move 4 times, there may be something wrong with a stage. */
		/* Set an error flag and end the batch scan. */
		when (errorCount >= 4) {
		
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state check_motor_error: Retried moving motors 4 times, all failed.\n");
				
			efSet(positionerErrorFlag);
			
			executingLine = MAXBATCHSIZE + 1;
			
		} state check_scanline
		
		/* If the position error is fine, continue with the scan. */
		when ((positionChecked == TRUE) && (scan3NumPts[executingLine] <= 0)) {
		
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state check_motor_error: Motor error acceptable.\n");
			
		} state begin_scan
		
		/* If the position error is fine and the third positioner is being used, */
		/* send the third positioner to its starting position. */
		when ((positionChecked == TRUE) && (remainingScan3Points > 0)) {
		
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state check_motor_error: Motor error acceptable.\n");
				
			/* Move positioner 3 to its next point */
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state check_motor_error: Moving positioner 3 to its position.\n");

			scan3PosVal = pos3Start + (pos3Increment * (scan3NumPts[executingLine] - remainingScan3Points));
			pvPut(scan3PosVal, ASYNC);
			
		} state wait_for_positioner3
	}
	
	state begin_scan {

		when () {

			/* Write a 1 to the outer scan record's execute PV, which will start the scan. */
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state begin_scan: Beginning scan.\n");
			scan2Execute = 1;
			pvPut(scan2Execute, SYNC);
			
			sprintf(scanStatus, "Executing scan %d.", executingLine);
			pvPut(scanStatus);

		} state wait_for_scan
	}	
	
	/* This state monitors the scan for completion and either moves positioner 3 to its next value or
	 * advances to the next scan line.  If the batch was paused,it will resume operation when the user
	 * pushes the continue button. */
	state wait_for_scan {
	
		entry {
		
			if (showDebugMessages > 2) {
				printf("\nBatchscan message: state wait_for_scan: Entering state.\n");
			}
		}
	
		when (efTestAndClear(resetBatchFlag)) {
		
			if (resetBatch == 1)
			{
		
				printf("\nBatchscan message: state wait_for_scan: Resetting batch scan to initial state.\n");
			
				executingLine = MAXBATCHSIZE + 1;
				pvPut(executingLine);
			}
			
		} state check_scanline
	
		
		/* This will execute when the normal 2D scan is completed and the third positioner must be moved.
			The 2D scan will then be executed again. */
		when ((scan2Busy == 0) && (!scanPaused) && (executingLine < MAXBATCHSIZE) && (remainingScan3Points > 0) && delay(1.0)) {
			
			/* Write a log file that has one line in it for each point of positioner 3. */	
			if (showDebugMessages > 0)
			{
				printf("\nBatchscan message: state wait_for_scan:  Begin writing log file for %s positioner 3.\n", scanInfo.fileNameStr);				
			}
						
			pvGet(saveDataFileName);
			pvGet(scan3PosVal);
			pvGet(sampleName);
			scanInfo.positioner3Val = scan3PosVal;
			scanInfo.scanLine = executingLine;
			sprintf(scanInfo.sample,"%s", sampleName);
			sprintf(scanInfo.fileNameStr,"%s", saveDataFileName);
			write_scan_info(&scanInfo);
			
			if (showDebugMessages > 0)
			{
				printf("\nBatchscan message: state wait_for_scan: Finished writing log file for %s positioner 3.\n", scanInfo.fileNameStr);
				printf("\nBatchscan message: state wait_for_scan: 2D scan finished, moving positioner 3.\n");		
			}
					
			scan3PosVal = pos3Start + (pos3Increment * (scan3NumPts[executingLine] - remainingScan3Points));
			pvPut(scan3PosVal, ASYNC);
			readyToStart = FALSE;
			
		} state wait_for_positioner3
		
		
		/* This will execute when the outer loop is finished.  The saved data file is written to the screen, as well as */
		/* the ending time of the scan. */
		when ((scan2Busy == 0) && (!scanPaused) && (executingLine < MAXBATCHSIZE) && (remainingScan3Points <= 0) && delay(1.0)) {
		
			if (scanValid)
			{
				/* Write a log file that has one line in it for each point of positioner 3. */
				if (scan3NumPts[executingLine] > 0)
				{
					if (showDebugMessages > 0)
						printf("\nBatchscan message: state wait_for_scan: Writing log file for positioner 3.\n");
				
					pvGet(saveDataFileName);
					pvGet(scan3PosVal);
					pvGet(sampleName);
					scanInfo.positioner3Val = scan3PosVal;
					scanInfo.scanLine = executingLine;
					sprintf(scanInfo.sample,"%s", sampleName);
					sprintf(scanInfo.fileNameStr,"%s", saveDataFileName);
					write_scan_info(&scanInfo);
					scanInfo.newFile = TRUE;					
				}
				
				readyToStart = FALSE;
			
				pvGet(saveMessage);
				strcpy(fileName[executingLine], saveMessage);
				pvPut(fileName[executingLine]);
			
				strcpy(scanEnded[executingLine], lastEstimate);
				pvPut(scanEnded[executingLine]);
		
			}
			
			scanComplete[executingLine] = TRUE;
			pvPut(scanComplete[executingLine]);
			
			efSet(updateTime);
			
			if (transformComplete[executingLine] == TRUE)
				executingLine++;
				
			if (showDebugMessages)
				printf("\nBatchscan message: Scan finished.\n");
						
		}state check_scanline
		
		/* If the batch has been paused and the user clicks the continue button, then set the current scan's */
		/* mode to NORMAL and resume the batch. */
		when (continueScan && scanPaused && (executingLine < MAXBATCHSIZE)) {
		
			scanMode[executingLine] = NORMAL;
			pvPut(scanMode[executingLine]);
		
			scanPaused = FALSE;
			continueScan = FALSE;
		
		} state check_scanline
		
	}		
	
}

/* This state set watches for a line to be finished and causes the total batch time to be updated. */
ss monitor_line_finished {

	state line_finished {
	
	
		when ((scan1Execute == 0) && (scan2Busy == 1) && (batchRunning == TRUE) && (efTest(scanLineFinished))) {
				
			if (scan2CurrentPoint > 0)
			{
				pvGet(executingLine);
			
				numPtsComplete[executingLine]++;
				pvPut(numPtsComplete[executingLine]);
		
				efSet(updateTime);
				
				if (showDebugMessages > 0)
					printf("\nBatchscan message: state monitor_line_finished: Line %d finished.\n", scan2CurrentPoint);
			}
			
			efClear(scanLineFinished);
			
		} state line_finished
	}
}

/* This state set monitors the size of the batch.  Every time a scan's mode is changed, this will */
/* run through the batch table and count the number of scans that have a mode of NORMAL. */
ss monitor_batchsize {

	state mode_change {
	
		when (efTestAndClear(modeChange)) {
		
			numScans = 0;
			extraScans = FALSE;
			lastScan = 0;
		
			for (modeLoop = 0; modeLoop < MAXBATCHSIZE; modeLoop++)
			{
				if ((scanMode[modeLoop] == NORMAL) || scanMode[modeLoop] == PAUSE )
				{
					numScans++;
					
					if (modeLoop > 9)
						extraScans = TRUE;
						
					if (modeLoop > lastScan)
						lastScan = modeLoop;
				}
			}

			if (showDebugMessages > 1)
			{
				printf("\nBatchscan message: state monitor_batchsize: Number of scans changed to %d.\n", numScans);
				printf("\nBatchscan message: state monitor_batchsize: Last scan run is %d.\n", lastScan + 1);
			}
			
			pvPut(numScans);
			pvPut(extraScans);
			pvPut(lastScan);
			
			efSet(updateTime);
						
		} state mode_change
	}
}

/* This state set prepares several pvs for fly or step scans. */
ss set_scan_mode {

	state set_mode {
	
		when (setScanType == SET_FLY_SCAN && scanType == STEP && !batchRunning) {		
		
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state set_scan_mode: Setting fly scan mode.\n");	
			
			scanType = FLY;
			pvPut(scanType);
			setScanType = 0;
						
			efSet(initFlag);
		
		} state set_mode
		
		when (setScanType == SET_STEP_SCAN && scanType == FLY && !batchRunning) {			
			
			if (showDebugMessages > 0)
				printf("\nBatchscan message: state set_scan_mode: Setting step scan mode.\n");
			
			scanType = STEP;
			pvPut(scanType);
			setScanType = 0;
			
			efSet(initFlag);
		
		} state set_mode	
	}
}

/* This state set simply tests the validity of the the saveData path plus the mount point */
/* that was entered in the setup screen.  It will also test this programs ability to create */
/* and write a file to that directory. */
ss test_save_file_path {

	state test_path {
	
		when(testPath) {

			pvGet(logFileMount);
			pvGet(saveDataPath);
			testPathStatus = test_file_path(logFileMount, saveDataPath);
			pvPut(testPathStatus);
			
			testPath = 0;
					
		} state test_path	
	}
} 

ss errorHandling {

	state init {
	
		when() {
		
		} state new_error
	}

	state new_error {
	
		when (efTest(positionerErrorFlag)) {
		
			efClear(positionerErrorFlag);
		
		} state positioner_error
	}
	
	state positioner_error {
	
		when () {
		
			sprintf(errorMessage, "Motor may not have moved.");
			pvPut(errorMessage);
			
		} state new_error
	}
}


/**************************************************************************************/
/* These are c functions that are used in this program.                               */
/**************************************************************************************/
%{

/* This function writes information about the value of positioner 3 for each mda file */
/* generated by the scan.  The file name is generated using the sample name and the scan */
/* number in the batch. The file is created in the same directory as saveData writes mda files.*/
void write_scan_info (fileInfo *info)
{
	char logFileName[255];
	FILE *pFile;
	
	sprintf(logFileName, "%s/%s_Scan_%d.csv", info->path, info->sample, info->scanLine);
	
	pFile = fopen(logFileName, "a");

	if (pFile != NULL)
	{		
		if (info->newFile == TRUE)
		{
			fprintf(pFile, "MDA File, Positioner 3\n");
			info->newFile = FALSE;
		}
		fprintf(pFile, "%s, %.3f\n", info->fileNameStr, info->positioner3Val);
		fclose(pFile);
		
		printf("\nBatchscan Message: write_scan_info: Wrote file to %s.\n", logFileName);

	}
	else
	{
		fclose(pFile);
		printf("\nBatchscan message: write_scan_info: cannot open file %s.\n", logFileName);
	}
	return;
}

/* This function tests the ability to create, write, and delete a file in the saveData directory. */
int test_file_path(char *mountPoint, char *path)
{
	char testFileName[255];
	FILE * pFile;
	int status;
	
	status = 0;
	
	sprintf(testFileName, "%s%s/TestFile.txt", mountPoint, path);
	printf("\nBatchscan message: test_file_path: test file path %s\n", testFileName);
	
	/* Try to open a stream to a file. */
	pFile = fopen(testFileName, "a");
	
	if (pFile != NULL)
	{
		/* Attempt to write to the file. */
		fprintf(pFile, "Test write of a file");
		fclose(pFile);
		
		/* Delete the test file */
		status = remove(testFileName);
		
		/* Remove returns a value of 0 if successful, but this function needs
			to return a value of 1 upon success.*/
		if (status == 0)
			status = 1;
		else
			status = 0;
			
		printf("\nBatchscan message: test_file_path: File %s successfully written\n", testFileName);
	}
	else
	{
		fclose(pFile);
		printf("\nBatchscan message: test_file_path: cannot open file %s.\n", testFileName);
	}
	
	return(status);
}
}%
