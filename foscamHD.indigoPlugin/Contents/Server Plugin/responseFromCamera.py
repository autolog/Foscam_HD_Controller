#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2016-2107
# Requires Indigo 7
#

import datetime

try:
    import indigo
except ImportError:
    pass
import ftplib
from ftplib import FTP
import logging
import os
import Queue
import subprocess
import sys
import threading
import time
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from constants import *


class ThreadResponseFromCamera(threading.Thread):

    def __init__(self, globals, devId, event):

        threading.Thread.__init__(self)

        self.globals = globals

        self.messageHandlingMonitorLogger = logging.getLogger("Plugin.MonitorMessageHandling")
        self.messageHandlingMonitorLogger.setLevel(self.globals['debug']['monitorMessageHandling'])

        self.messageHandlingDebugLogger = logging.getLogger("Plugin.DebugMessageHandling")
        self.messageHandlingDebugLogger.setLevel(self.globals['debug']['debugMessageHandling'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        self.threadStop = event

        self.cameraDevId = int(devId)  # Set Indigo Device id (for camera) to value passed in Thread invocation
        self.cameraAddress = indigo.devices[self.cameraDevId].address
        self.cameraName = indigo.devices[self.cameraDevId].name

        self.globals['threads']['handleResponse'][self.cameraDevId]['threadActive'] = True

        self.messageHandlingDebugLogger.debug(u"Initialised 'ResponseFromCamera' Thread for %s [%s]" % (self.cameraName, self.cameraAddress))  
  
    def run(self):

        try:
            self.methodTracer.threaddebug(u"ThreadResponseFromCamera")  

            time.sleep(kDelayStartResponseFromcamera)  # Allow devices to start?

            self.messageHandlingDebugLogger.debug(u"'ResponseFromCamera' Thread for %s [%s] initialised and now running" % (self.cameraName, self.cameraAddress))  

            while not self.threadStop.is_set():
                try:

                    if self.globals['debug']['previousMonitorHandleMsg'] != self.globals['debug']['monitorHandleMsg']:
                        self.globals['debug']['previousMonitorHandleMsg'] = self.globals['debug']['monitorHandleMsg']
                        self.messageHandlingMonitorLogger.setLevel(self.globals['debug']['monitorHandleMsg'])

                    if self.globals['debug']['previousDebugHandleMsg'] != self.globals['debug']['debugHandleMsg']:
                        self.globals['debug']['previousDebugHandleMsg'] = self.globals['debug']['debugHandleMsg']
                        self.messageHandlingDebugLogger.setLevel(self.globals['debug']['debugHandleMsg'])

                    if self.globals['debug']['previousDebugMethodTrace'] !=self.globals['debug']['debugMethodTrace']:
                        self.globals['debug']['previousDebugMethodTrace'] = self.globals['debug']['debugMethodTrace']
                        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

                    responseToHandle = self.globals['queues']['responseFromCamera'][self.cameraDevId].get(True,5)
                    if responseToHandle[0] == 'STOPTHREAD':
                        continue  # self.threadStop should be set

                    commandTuple = responseToHandle[0]
                    command = commandTuple[0]
                    response = responseToHandle[1]

                    processCommandMethod = 'process' + command[0:1].upper() + command[1:]
                    self.messageHandlingDebugLogger.debug(u"processCommand = %s" % (processCommandMethod))

                    self.cameraDev = indigo.devices[self.cameraDevId]
                    try:                    
                        processCommandMethodMethod = getattr(self, processCommandMethod)

                        processCommandMethodMethod(commandTuple, response)
                    except StandardError, e:
                        self.messageHandlingDebugLogger.error(u"Process Command Method detected error. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e)) 
                except Queue.Empty:
                    pass

        except StandardError, e:
            self.messageHandlingDebugLogger.error(u"Handle Command Thread  detected error. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   

            self.globals['cameras'][self.cameraDevId]['keepThreadAlive'] = False

            self.messageHandlingDebugLogger.debug(u"Handle Command Thread ended for %s [%s]" % (self.cameraName, self.cameraAddress))

        self.messageHandlingDebugLogger.debug(u"ThreadResponseFromCamera ended for camera: %s [%s]" % (self.cameraName, self.cameraAddress))  

        self.globals['threads']['handleResponse'][self.cameraDevId]['threadActive'] = False

    def processGetRecordList(self, commandTuple, responseFromCamera):  # 'getRecordList' Response handling
        self.processGetRecordList1(commandTuple, responseFromCamera)


    def processGetRecordList1(self, commandTuple, responseFromCamera):  # 'getRecordList1' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        pass

    def processStartRecord(self, commandTuple, responseFromCamera):  # 'getRecordList1' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        pass

    def processStopRecord(self, commandTuple, responseFromCamera):  # 'getRecordList1' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        pass


    def processGetSystemTime(self, commandTuple, responseFromCamera):  # 'getSystemTime' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            dynamicParams = {}  # Initialise the dictionary to store the GetSystemTime reponse from camera that will be used for SetSystemTime
            tree = ET.ElementTree(ET.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.messageHandlingDebugLogger.debug(u"XML: '%s' = %s" % (child_of_root.tag, child_of_root.text))
                if child_of_root.tag != 'result':
                    if child_of_root.tag in ('ntpServer', 'dateFormat', 'timeFormat'):
                        dynamicParams[child_of_root.tag] = child_of_root.text  # store GetMotionDetectConfig element from original value

            indigoDateTime = datetime.datetime.utcnow()
            indigoDateTimeRAW = indigoDateTime.strftime("%Y%m%d%H%M%S")
            indigoDateTimeYear   = indigoDateTimeRAW[0:4] 
            indigoDateTimeMon    = indigoDateTimeRAW[4:6] 
            indigoDateTimeDay    = indigoDateTimeRAW[6:8] 
            indigoDateTimeHour   = indigoDateTimeRAW[8:10] 
            indigoDateTimeMinute = indigoDateTimeRAW[10:12] 
            indigoDateTimeSec    = indigoDateTimeRAW[12:14] 
                   
            dynamicParams['isDst']      = '0'
            dynamicParams['dst']        = '0'
            dynamicParams['year']       = indigoDateTimeYear
            dynamicParams['mon']        = indigoDateTimeMon.lstrip('0')
            dynamicParams['day']        = indigoDateTimeDay.lstrip('0')
            dynamicParams['hour']       = indigoDateTimeHour.lstrip('0')
            dynamicParams['minute']     = indigoDateTimeMinute.lstrip('0')
            dynamicParams['sec']        = indigoDateTimeSec.lstrip('0')
            timeZone                    = time.timezone if (time.localtime().tm_isdst == 0) else time.altzone
            dynamicParams['timeZone']   = str(timeZone)
            dynamicParams['timeSource'] = '1'  # Set Time Manually

            timezoneUi = '{0:+d}'.format((timeZone / 3600) * -1)

            if ('dateFormat' in dynamicParams) and (dynamicParams['dateFormat'] == '2'):
                dateTimeUi = indigoDateTime.strftime("%m/%d/%Y")
            elif ('dateFormat' in dynamicParams) and (dynamicParams['dateFormat'] == '1'):
                dateTimeUi = indigoDateTime.strftime("%d/%m/%Y")
            else:  # Assume present and = '0'
                dateTimeUi = indigoDateTime.strftime("%Y-%m-%d")

            if ('timeFormat' in dynamicParams) and (dynamicParams['timeFormat'] == '0'):
                dateTimeUi = dateTimeUi + indigoDateTime.strftime(" %H:%M:%S %p")
            else:  # Assume present and = '1'
                dateTimeUi = dateTimeUi + indigoDateTime.strftime(" %H:%M:%S")

            indigo.server.log("'%s' camera time synchronised to '%s UTC %s'" %(self.cameraDev.name, dateTimeUi, timezoneUi))

            params = dynamicParams

            self.messageHandlingDebugLogger.debug(u'SET SYSTEM TIME for %s : %s' % (self.cameraDev, params))

            self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', ('setSystemTime',), params])

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))

    def processSetSystemTime(self, commandTuple, responseFromCamera):  # 'setSystemTime' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        pass

    def processGetMotionDetectConfig(self, commandTuple, responseFromCamera):  # 'motionAlarmGet' Response handling
        self.processGetMotionDetectConfig1(commandTuple, responseFromCamera)

    def processGetMotionDetectConfig1(self, commandTuple, responseFromCamera):  # 'motionAlarmGet' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            keyValueList = []                   # Initialise list of Key Values for Camera Indigo device update of 'linkage' and 'isEnable'
            responseGetMotionDetectConfigDict = {}  # Initialise the dictionary to store the GetMotionDetectConfig reponse from camera
            tree = ET.ElementTree(ET.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.messageHandlingDebugLogger.debug(u"XML: '%s' = %s" % (child_of_root.tag, child_of_root.text))
                if child_of_root.tag != 'result':
                    if child_of_root.tag == 'linkage':
                        keyValue = {}
                        keyValue['key'] = child_of_root.tag
                        keyValue['value'] = child_of_root.text
                        keyValueList.append(keyValue)  # for state update
                    elif child_of_root.tag == 'isEnable':
                        keyValue = {}
                        keyValue['key'] = 'motionDetectionIsEnabled'
                        keyValue['value'] = child_of_root.text
                        keyValueList.append(keyValue)  # for state update
                    else:
                        responseGetMotionDetectConfigDict[child_of_root.tag] = child_of_root.text  # store GetMotionDetectConfig element 
            self.cameraDev.updateStatesOnServer(keyValueList)  # Update linkage and isEnable states in Indigo camera device

            if len(commandTuple) != 3:  # if setMotionDetectConfig not required - return
                return 

            # At this point the real request is for a setMotionDetectConfig - the getMotionDetectConfig was done to ensure u-to-date values will be processed
            commandFunction = commandTuple[1]
            commandOption =  commandTuple[2]

            executeSetMotionDetectConfig = False

            if commandFunction == kEnableMotionDetect:
                motionDetectionIsEnabled = int(self.cameraDev.states['motionDetectionIsEnabled'])
                if commandOption == kOn:
                    motionDetectionIsEnabled = int(1)
                elif commandOption == kOff:    
                    motionDetectionIsEnabled = int(0)
                elif commandOption == kToggle:
                    motionDetectionIsEnabled = motionDetectionIsEnabled ^ 1 # Toggle bit 0
                else:
                    self.messageHandlingDebugLogger.error(u"Invalid EnableMotionDetect Command Option for '%s': '%s'" % (self.cameraDev.name, commandOption))   
                    return 
                linkage = int(self.cameraDev.states["linkage"])
                executeSetMotionDetectConfig = True

            elif commandFunction == kSnapPicture:
                linkage = int(self.cameraDev.states["linkage"])
                if commandOption == kOn:
                    linkage = linkage | 4  # Turn ON bit 2
                elif commandOption == kOff:    
                    linkage = linkage & ~4  # Turn OFF bit 2
                elif commandOption == kToggle:
                    linkage = linkage ^ 4 # Toggle bit 2
                else:
                    self.messageHandlingDebugLogger.error(u"Invalid Snap Command Option for '%s': '%s'" % (self.cameraDev.name, commandOption))   
                    return 
                motionDetectionIsEnabled = int(self.cameraDev.states['motionDetectionIsEnabled'])
                executeSetMotionDetectConfig = True

            elif commandFunction == kMotionDetectionRecord:
                linkage = int(self.cameraDev.states["linkage"])
                if commandOption == kOn:
                    linkage = linkage | 8  # Turn ON bit 3
                elif commandOption == kOff:    
                    linkage = linkage & ~8  # Turn OFF bit 3
                elif commandOption == kToggle:
                    linkage = linkage ^ 8 # Toggle bit 3
                else:
                    self.messageHandlingDebugLogger.error(u"Invalid Snap Command Option for '%s': '%s'" % (self.cameraDev.name, commandOption))   
                    return 
                motionDetectionIsEnabled = int(self.cameraDev.states['motionDetectionIsEnabled'])
                executeSetMotionDetectConfig = True

            elif commandFunction == kRing:
                linkage = int(self.cameraDev.states["linkage"])
                if commandOption == kOn:
                    linkage = linkage | 1  # Turn ON bit 0
                elif commandOption == kOff:    
                    linkage = linkage & ~1  # Turn OFF bit 0
                elif commandOption == kToggle:
                    linkage = linkage ^ 1 # Toggle bit 0
                else:
                    self.messageHandlingDebugLogger.error(u"Invalid Ring Command Option for '%s': '%s'" % (self.cameraDev.name, commandOption))   
                    return 
                motionDetectionIsEnabled = int(self.cameraDev.states['motionDetectionIsEnabled'])
                executeSetMotionDetectConfig = True

            if executeSetMotionDetectConfig:
                dynamicParams = {
                    'isEnable': str(motionDetectionIsEnabled),
                    'linkage': str(linkage),
                }

                params = dynamicParams.copy()
                params.update(responseGetMotionDetectConfigDict)

                self.messageHandlingDebugLogger.debug(u'SET MOTION DETECT CONFIG for %s : %s' % (self.cameraDev, params))

                self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', ('setMotionDetectConfig',), params])

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))   


    def processSetMotionDetectConfig(self, commandTuple, responseFromCamera):  # 'motionAlarmEnable' / 'motionAlarmDisable' Response handling
        self.processSetMotionDetectConfig1(commandTuple, responseFromCamera)

    def processSetMotionDetectConfig1(self, commandTuple, responseFromCamera):  # 'motionAlarmEnable' / 'motionAlarmDisable' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            params = {}
            self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', ('getDevState',), params])  # Refresh state

            params = {}
            self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', ('getMotionDetectConfig',), params])

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"processSetMotionDetectConfig: StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))   


    def processGetScheduleRecordConfig(self, commandTuple, responseFromCamera):  # 'motionAlarmGet' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            keyValueList = []                   # Initialise list of Key Values for Camera Indigo device update of 'linkage' and 'isEnable'
            responseGetScheduleRecordConfig = {}  # Initialise the dictionary to store the GetMotionDetectConfig reponse from camera
            tree = ET.ElementTree(ET.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.messageHandlingDebugLogger.debug(u"XML: '%s' = %s" % (child_of_root.tag, child_of_root.text))
                if child_of_root.tag != 'result':
                    if child_of_root.tag == 'isEnable':
                        keyValue = {}
                        keyValue['key'] = 'scheduleRecordEnabled'
                        keyValue['value'] = bool(int(child_of_root.text))
                        keyValueList.append(keyValue)  # for state update
                    else:
                        responseGetScheduleRecordConfig[child_of_root.tag] = child_of_root.text  # store GetMotionDetectConfig element 
            self.cameraDev.updateStatesOnServer(keyValueList)  # Update scheduleRecordIsEnable state in Indigo camera device

            if len(commandTuple) != 3:  # if setScheduleRecordConfig not required - return
                return 

            # At this point the real request is for a setMotionDetectConfig - the getMotionDetectConfig was done to ensure u-to-date values will be processed
            commandFunction = commandTuple[1]
            commandOption =  commandTuple[2]

            executeScheduleRecordConfig = False

            if commandFunction == kScheduleRecord:
                scheduleRecordEnabled = int(self.cameraDev.states['scheduleRecordEnabled'])
                if commandOption == kOn:
                    scheduleRecordEnabled = '1'
                elif commandOption == kOff:    
                    scheduleRecordEnabled = '0'
                elif commandOption == kToggle:
                    scheduleRecordEnabled = str(scheduleRecordEnabled ^ 1) # Toggle bit 0
                else:
                    self.messageHandlingDebugLogger.error(u"Invalid EnableScheduleRecord Command Option for '%s': '%s'" % (self.cameraDev.name, commandOption))   
                    return 
                executeStScheduleRecordConfig = True


            if executeStScheduleRecordConfig:
                dynamicParams = {
                    'isEnable': scheduleRecordEnabled
                }

                params = dynamicParams.copy()
                params.update(responseGetScheduleRecordConfig)

                self.messageHandlingDebugLogger.debug(u'SET SCHEDULE RECORD CONFIG for %s : %s' % (self.cameraDev, params))

                self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', ('setScheduleRecordConfig',), params])

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"processGetScheduleRecordConfig: StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))   


    def processSetScheduleRecordConfig(self, commandTuple, responseFromCamera):  # 'motionAlarmEnable' / 'motionAlarmDisable' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            params = {}
            self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', ('getDevState',), params])  # Refresh state

            params = {}
            self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', ('getScheduleRecordConfig',), params])

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"processSetScheduleRecordConfig: StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))   


    def processGetDevName(self, commandTuple, responseFromCamera):  # 'getDevName' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

    def processGetProductModel(self, commandTuple, responseFromCamera):  # 'getProductModel' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            keyValueList = []
            tree = ET.ElementTree(ET.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.messageHandlingDebugLogger.debug(u"XML: '%s' = %s" % (child_of_root.tag, child_of_root.text))
                if child_of_root.tag == 'model':

                    keyValue = {}
                    keyValue['key'] = child_of_root.tag
                    keyValue['value'] = child_of_root.text
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)
        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))


    def processGetProductModelName(self, commandTuple, responseFromCamera):  # 'getProductModelName' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            modelName = ''
            keyValueList = []
            tree = ET.ElementTree(ET.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.messageHandlingDebugLogger.debug(u"XML: '%s' = %s" % (child_of_root.tag, child_of_root.text))
                if child_of_root.tag == 'modelName':
                    modelName = child_of_root.text
                    keyValue = {}
                    keyValue['key'] = child_of_root.tag
                    keyValue['value'] = child_of_root.text
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)

            if modelName != '':
                if self.cameraDev.model != modelName:
                    self.cameraDev.model = modelName
                    self.cameraDev.replaceOnServer()

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))   


    def processGetDevInfo(self, commandTuple, responseFromCamera):  # 'getDevInfo' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            keyValueList = []
            tree = ET.ElementTree(ET.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.messageHandlingDebugLogger.debug(u"XML: '%s' = %s" % (child_of_root.tag, child_of_root.text))
                if child_of_root.tag in ('productName', 'serialNo', 'devName', 'mac', 'firmwareVer', 'hardwareVer'):
                    if child_of_root.tag == 'firmwareVer':
                        props = self.cameraDev.pluginProps
                        props["version"] = child_of_root.text
                        self.cameraDev.replacePluginPropsOnServer(props)
                    keyValue = {}
                    keyValue['key'] = child_of_root.tag
                    keyValue['value'] = child_of_root.text
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)


        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))   



    def processGetDevState(self, commandTuple, responseFromCamera):  # 'getDevState' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            keyValueList = []
            tree = ET.ElementTree(ET.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                # self.messageHandlingDebugLogger.debug(u"XML: '%s' = %s" % (child_of_root.tag, child_of_root.text))
                if child_of_root.tag != 'result':
                    keyValue = {}
                    keyValue['key'] = child_of_root.tag
                    # Next bit of logic stores SD space values as a numeric so it can be compared in trigger conditions
                    if (child_of_root.tag in ('sdFreeSpace', 'sdTotalSpace')):
                        spaceValue = child_of_root.text
                        if child_of_root.text[-1:] == 'k':
                            spaceValue = child_of_root.text[:-1]  # Remove trailing 'k'
                        try:
                            int(spaceValue) + 1  # Numeric Test
                        except ValueError:
                            spaceValue = 0  # Default to zero if no trailing k or invalid numeric
                        keyValue['value'] = spaceValue
                    else:
                        keyValue['value'] = child_of_root.text
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)

            # motionDetectAlarm:   0 = Motion Detection Disabled
            #                      1 = Motion Detection Enabled - No motion detected
            #                      2 = Motion Detection Enabled - Motion detected
            motionDetectAlarm  = int(self.cameraDev.states['motionDetectAlarm'])

            snap_enabled  = bool((int(self.cameraDev.states['linkage']) & 4) >> 2)

            if motionDetectAlarm == '0':  # 0 = Disabled
                pass
            else:
                if motionDetectAlarm == '2':  # Motion Detection Enabled and motion detected
                    if snap_enabled:
                        if self.globals['cameras'][self.cameraDevId]['ftpProcessMode'] == 1:  # FTP Client mode
                        #   Only retrieve FTP files if FTP Client mode enabled and Snap Enabled
                            self._ftpClientRetrieve()
                        elif self.globals['cameras'][self.cameraDevId]['ftpProcessMode'] == 2:  # FTP Server mode
                        #   Only process FTP'd files if FTP Server mode enabled and Snap Enabled
                            self._ftpServerProcess() 

                else:  # Motion Detection Enabled and no motion detected
                    if snap_enabled and self.globals['cameras'][self.cameraDevId]['motion']['previouslyDetected']:
                        if self.globals['cameras'][self.cameraDevId]['ftpProcessMode'] == 1:  # FTP Client mode
                        #   Only retrieve FTP files if FTP Client mode enabled and Snap Enabled and motion previously detected
                            self._ftpClientRetrieve()  # To pick up any files since motion detection ended
                        elif self.globals['cameras'][self.cameraDevId]['ftpProcessMode'] == 2:  # FTP Server mode
                        #   Only process FTP'd files if FTP Server mode enabled and Snap Enabled and motion previously detected
                            self._ftpServerProcess()  # To pick up any files since motion detection ended 

            self.globals['cameras'][self.cameraDevId]['motion']['previouslyDetected'] = bool(motionDetectAlarm >> 1)  # Only True if motionDetectAlarm value was 2
            self.messageHandlingDebugLogger.debug(u"%s [%s] Motion Detect Alarm value: '%s'" % (self.cameraName, self.cameraAddress, str(motionDetectAlarm)))

            stateImageSel = indigo.kStateImageSel.SensorOff
            uiState = 'off'
            if motionDetectAlarm != 0:  # 0 = Motion Detection Disabled
                if motionDetectAlarm == 2:  # Motion Detection Enabled - Motion detected
                    # Set timer to turn off motion detected (allows for user specified timing of how long motion should indicate motion detected for)
                    if self.cameraDevId in self.globals['threads']['motionTimer']:
                        self.globals['threads']['motionTimer'][self.cameraDevId].cancel()
                    motionTimerSeconds = self.globals['cameras'][self.cameraDevId]['motion']['detectionInterval']
                    self.globals['threads']['motionTimer'][self.cameraDevId] = threading.Timer(motionTimerSeconds, self.handleTimerQueuedStatusCommand, [self.cameraDev, self.globals])
                    self.globals['threads']['motionTimer'][self.cameraDevId].start()
                    self.globals['cameras'][self.cameraDevId]['motion']['timerActive'] = True
                    stateImageSel = indigo.kStateImageSel.MotionSensorTripped
                    uiState = 'tripped'
                else:
                    # motionDetectAlarm = 1 = Motion Detection Enabled - No motion detected
                    if self.globals['cameras'][self.cameraDevId]['motion']['timerActive']:
                        stateImageSel = indigo.kStateImageSel.MotionSensorTripped
                        uiState = 'tripped'
                    else:
                        # only set "not tripped" if no timer active - if timer active, when timer fires, it will set to "not tripped"
                        stateImageSel = indigo.kStateImageSel.MotionSensor
                        uiState = 'no motion'
            
            self.cameraDev.updateStateImageOnServer(stateImageSel)

            keyValueList = []
            keyValue = {}
            keyValue['key'] = 'onOffState'
            keyValue['value'] = self.globals['cameras'][self.cameraDevId]['motion']['timerActive']
            keyValue['uiValue'] = uiState
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'motionDetectionEnabled'
            keyValue['value'] = bool(motionDetectAlarm & 3)  # True if motionDetectAlarm = 1 or 2
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'motionDetected'
            keyValue['value'] = bool(motionDetectAlarm & 2)  # True if motionDetectAlarm = 2
            keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"StandardError detected for '%s' at line '%s' = %s" % (self.cameraName, exc_tb.tb_lineno,  e))   

    def handleTimerQueuedStatusCommand(self, cameraDev, globals):

        # Motion Timer - Turn off Motion detected
        self.globals = globals
        if self.cameraDev.states['onOffState']:  # Only turn-off motion detected if it is currently showing True (i.e. on)
            self.globals['cameras'][self.cameraDevId]['motion']['timerActive'] = False
            cameraDev.updateStateOnServer(key="onOffState", value=False, uiValue='no motion')
            self.cameraDev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor)
        else:
            self.messageHandlingDebugLogger.debug(u"handleTimerQueuedStatusCommand: %s - Timer ignored as motion detected already off" % (cameraDev.name))   


    def _ftpServerProcess(self):
        self.messageHandlingDebugLogger.info(u"_ftpServerProcess called for '%s'" % (self.cameraDev.name))   



    def _ftpClientRetrieve(self):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            alarmTime = indigo.server.getTime()
            alarmTimeUi = alarmTime.strftime('%Y%m%d-%H%M%S')  # e.g. '20160903-141636'
            alarmFtpDateFolder = alarmTime.strftime('%Y%m%d')  # e.g. '20160831'

            alarmTimeMinute = alarmTime.strftime('%M')  # e.g. '45'
            if alarmTimeMinute < '30':
                derivedBaseHalfHour = '00'
            else:
                derivedBaseHalfHour = '30'
            alarmFtpImageFolder = str('%s%s00' % (alarmTime.strftime('%Y%m%d-%H'), derivedBaseHalfHour))  # e.g. 20150415-143000

            alarmFoldersToProcess = [[alarmFtpDateFolder, alarmFtpImageFolder]]

            alarmTimeDay = alarmFtpImageFolder[6:8]  # e.g. 15
            alarmTimeHour = alarmFtpImageFolder[9:11]  # e.g. 14
            alarmTimeHourMinute = alarmTimeHour + alarmTimeMinute

            # Logic to handle motion being detected over change of day, hour and half-hour
            if alarmTimeHourMinute == '0000':  # e.g. 20160831-000000
                alarmTimeYesterday = alarmTime - datetime.timedelta(days=1)
                alarmFtpDateFolder = alarmTimeYesterday.strftime('%Y%m%d')  # e.g. 20150415
                alarmFtpImageFolder = str('%s-233000' % (alarmTimeYesterday.strftime('%Y%m%d')))  # e.g. 20150414-233000
                alarmFoldersToProcess[:0] = [[alarmFtpDateFolder, alarmFtpImageFolder]]  # Prepend to list
            elif alarmTimeMinute == '00' or alarmTimeMinute == '01':
                alarmTimeLastHour = alarmTime - datetime.timedelta(hours=1)
                alarmFtpDateFolder = alarmTimeLastHour.strftime('%Y%m%d')  # e.g. 20150415
                alarmFtpImageFolder = str('%s3000' % (alarmTimeLastHour.strftime('%Y%m%d-%H')))  # e.g. 20150414-123000
                alarmFoldersToProcess[:0] = [[alarmFtpDateFolder, alarmFtpImageFolder]]  # Prepend to list
            elif alarmTimeMinute == '30' or alarmTimeMinute == '31':
                alarmFtpImageFolder = str('%s%s00' % (alarmTime.strftime('%Y%m%d-%H'), derivedBaseHalfHour))  # e.g. 20150415-143000
                alarmFoldersToProcess[:0] = [[alarmFtpDateFolder, alarmFtpImageFolder]]  # Prepend to list

            alarmSaveRootFolder = self.globals['cameras'][self.cameraDevId]['rootFolder']
            ftpCameraFolder = str('%s_%s' % (self.cameraDev.states["productName"].split("+")[0], self.cameraDev.states["mac"]))  # truncate productName on '+' e.g. 'FI9831W_A1B2C3D4E5F6' (productName_mac)
            self.globals['cameras'][self.cameraDevId]['ftpCameraFolder'] = ftpCameraFolder
            if self.globals['cameras'][self.cameraDevId]['cameraFolder'] == '':
                alarmSaveFolderCamera = ftpCameraFolder
            else:
                alarmSaveFolderCamera = self.globals['cameras'][self.cameraDevId]['cameraFolder']

            alarmSaveFolderBase = str('%s/%s' % (alarmSaveRootFolder, alarmSaveFolderCamera))
            returnCode = subprocess.call(['mkdir', alarmSaveFolderBase])
            self.messageHandlingDebugLogger.debug(u"alarmSaveFolderBase [%s]: RC=%s" % (alarmSaveFolderBase, str(returnCode)))
            self.messageHandlingDebugLogger.debug(u"alarmFoldersToProcess: %s" % (alarmFoldersToProcess))



            try:
                ftp = FTP()
                ftp.connect(str(self.globals['cameras'][self.cameraDevId]['ipAddress']), self.globals['cameras'][self.cameraDevId]['ftpPort'])
                ftp.login(str(self.globals['cameras'][self.cameraDevId]['username']), str(self.globals['cameras'][self.cameraDevId]['password']))
                ftp.set_pasv(0)

                ftpSubDirectory = str('/IPCamera/%s/snap' % (ftpCameraFolder))

            except ftplib.error_perm, e:
                self.messageHandlingDebugLogger.error(u"alarmFtpDateFolder: Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))
                try:
                    ftp.quit()
                except ftplib.error_perm, e:
                    pass    
                return

            for alarmFolderList in alarmFoldersToProcess:
                try:
                    ftp.cwd(ftpSubDirectory)  # e.g. '/IPCamera/FI9831W_A1B2C3D4E5F6/snap' (using productName_mac)
                except ftplib.error_perm, e:
                    self.messageHandlingDebugLogger.error(u"alarmFtpDateFolder: Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))
                    ftp.quit()
                    return

                self.messageHandlingDebugLogger.debug(u"Alarm Time [%s]: F1='%s', F2='%s'" % (alarmTimeUi, alarmFolderList[0], alarmFolderList[1]))

                alarmFtpDateFolder = alarmFolderList[0]
                alarmFtpImageFolder = alarmFolderList[1]
                try:
                    currentPath = ftp.pwd()
                    self.messageHandlingDebugLogger.debug(u"Current FTP Path: '%s',  alarmFtpImageFolder: '%s'" % (currentPath, alarmFtpImageFolder))
                    ftp.cwd(alarmFtpDateFolder)
                except ftplib.error_perm, e:
                    if str(e)[0:3] == '550':  # if folder not found - continue to next 
                        continue
                    else:
                        self.messageHandlingDebugLogger.error(u"alarmFtpDateFolder: Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))
                        ftp.quit()
                        return

                alarmSaveDateFolder = str('%s/%s' % (alarmSaveFolderBase, alarmFtpDateFolder))
                returnCode = subprocess.call(['mkdir', alarmSaveDateFolder])
                # self.messageHandlingDebugLogger.debug(u"alarmSaveDateFolder [%s]: RC=%s" % (alarmSaveDateFolder, str(returnCode)))
                try:
                    currentPath = ftp.pwd()
                    self.messageHandlingDebugLogger.debug(u"Current FTP Path: '%s',  alarmFtpImageFolder: '%s'" % (currentPath, alarmFtpImageFolder))
                    ftp.cwd(alarmFtpImageFolder)
                except ftplib.error_perm, e:
                    if str(e)[0:3] == '550':  # if folder not found - continue to next 
                        continue
                    else:
                        self.messageHandlingDebugLogger.error(u"alarmFtpImageFolder: Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))
                        ftp.quit()
                        return

                alarmSaveImageFolder = str('%s/%s' % (alarmSaveDateFolder, alarmFtpImageFolder))
                returnCode = subprocess.call(['mkdir', alarmSaveImageFolder])
                self.messageHandlingDebugLogger.debug(u"alarmSaveImageFolder [%s]: RC=%s" % (alarmSaveImageFolder, str(returnCode)))

                indigoList = []
                for file in os.listdir(alarmSaveImageFolder):
                    if file.endswith('.jpg'):
                        indigoFilename = str(file).split('.jpg')[0]
                        indigoList.append(indigoFilename)

                ftpList = []
                ftpListIn = []
                ftp.dir(ftpListIn.append)
                for ftpListEntry in ftpListIn:
                    ftpSplit = ftpListEntry.split()
                    ftpFileName = ftpSplit[len(ftpSplit)-1]
                    if ftpFileName.endswith('.jpg'):
                        ftpFileName = ftpFileName.split('.jpg')[0]
                        ftpList.append(ftpFileName)

                missingFromSavedList = list(set(ftpList) - set(indigoList))
                missingFromSavedList.sort()

                for missingFromSavedListEntry in missingFromSavedList:
                    self.messageHandlingDebugLogger.debug(u"Found image: %s" % (missingFromSavedListEntry))
                    savedFileName = str('%s/%s.jpg' % (alarmSaveImageFolder, missingFromSavedListEntry))
                    savedFile = open(savedFileName, 'wb')
                    ftpRetr = str('RETR %s.jpg' % (missingFromSavedListEntry))
                    ftp.retrbinary(ftpRetr, savedFile.write)
                    savedFile.close()

            ftp.quit()

            indigo.server.broadcastToSubscribers(u"updateDynamicView", self.globals['cameras'][self.cameraDevId]['motion']['dynamicView'])

            # self.globals['cameras'][self.cameraDevId]['motion']['imageFolder'] = ''  # Force to latest folder

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"_ftpClientRetrieve: StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))


    def processSnapPicture2(self, commandTuple, responseFromCamera):  # 'snapPicture2' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.info(u"SNAP IMAGE PROCESSING NOT YET AVAILABLE!")

                       
    #     try:
    #         snappath = "T B A"
    #         f = open(snappath, 'w')
    #         f.write(responseFromCamera)
    #         f.close()
 
    #     except StandardError, e:
    #         exc_type, exc_obj, exc_tb = sys.exc_info()
    #         self.messageHandlingDebugLogger.error(u"_snapPicture2: StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))
