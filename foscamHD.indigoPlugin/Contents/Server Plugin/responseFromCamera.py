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
from time import sleep
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

        self.messageHandlingDebugLogger.debug(u"Initialising 'ResponseFromCamera' Thread for %s [%s]" % (self.cameraName, self.cameraAddress))  
  
    def run(self):

        self.methodTracer.threaddebug(u"ThreadResponseFromCamera")  

        sleep(2)  # Allow devices to start?

        try:

            self.messageHandlingDebugLogger.debug(u"ResponseFromCamera Thread initialised for %s [%s]" % (self.cameraName, self.cameraAddress))  

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

                    command = responseToHandle[0]
                    response = responseToHandle[1]

                    processCommandMethod = 'process' + command[0:1].upper() + command[1:]
                    self.messageHandlingDebugLogger.debug(u"processCommand = %s" % (processCommandMethod))

                    self.cameraDev = indigo.devices[self.cameraDevId]
                    try:                    
                        processCommandMethodMethod = getattr(self, processCommandMethod)

                        processCommandMethodMethod(response)
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


    def processGetMotionDetectConfig(self, responseFromCamera):  # 'motionAlarmGet' Response handling
        self.processGetMotionDetectConfig1(responseFromCamera)

    def processGetMotionDetectConfig1(self, responseFromCamera):  # 'motionAlarmGet' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            keyValueList = []
            self.globals['cameras'][self.cameraDevId]['savedConfigDict'] = {}
            tree = ET.ElementTree(ET.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.messageHandlingDebugLogger.debug(u"XML: '%s' = %s" % (child_of_root.tag, child_of_root.text))
                if child_of_root.tag != 'result':
                    if (child_of_root.tag == 'linkage') or (child_of_root.tag == 'isEnable'):
                        keyValue = {}
                        keyValue['key'] = child_of_root.tag
                        keyValue['value'] = child_of_root.text
                        keyValueList.append(keyValue)
                    else:
                        self.globals['cameras'][self.cameraDevId]['savedConfigDict'][child_of_root.tag] = child_of_root.text
            self.cameraDev.updateStatesOnServer(keyValueList)

            linkage = int(self.cameraDev.states["linkage"])
            self.globals['cameras'][self.cameraDevId]['motion']['ringEnabled'] = bool(linkage & 1)  # bit 0
            self.globals['cameras'][self.cameraDevId]['motion']['snapEnabled'] = bool(linkage & 4)  # bit 2 

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))   


    def processSetMotionDetectConfig(self, responseFromCamera):  # 'motionAlarmEnable' / 'motionAlarmDisable' Response handling
        self.processSetMotionDetectConfig1(responseFromCamera)

    def processSetMotionDetectConfig1(self, responseFromCamera):  # 'motionAlarmEnable' / 'motionAlarmDisable' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            params = {}
            self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', 'getDevState', params])  # Refresh state

            params = {}
            # Determine Camera platform and process accordingly
            if self.globals['cameras'][self.cameraDevId]['cameraPlatform'] == kOriginal:
                self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', 'getMotionDetectConfig', params])
            else:
                # kAmba
                self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', 'getMotionDetectConfig1', params])


        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"processSetMotionDetectConfig: StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))   


    def processGetDevName(self, responseFromCamera):  # 'getDevName' Response handling
        self.methodTracer.threaddebug(u"CLASS: Plugin")

    def processGetProductModel(self, responseFromCamera):  # 'getProductModel' Response handling
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


    def processGetProductModelName(self, responseFromCamera):  # 'getProductModelName' Response handling
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


    def processGetDevInfo(self, responseFromCamera):  # 'getDevInfo' Response handling
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



    def processGetDevState(self, responseFromCamera):  # 'getDevState' Response handling
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
                    keyValue['value'] = child_of_root.text
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)

            motionDetectAlarm = self.cameraDev.states['motionDetectAlarm']

            # set whether alarm is disabled or enabled and whether detected
            motionDetectionEnabled = False
            motionDetected = False
            if motionDetectAlarm == '0':  # 0 = Disabled
                pass
            else:
                motionDetectionEnabled = True
                if motionDetectAlarm == '2':  # 2 = Detect Alarm
                    motionDetected = True
                    if self.globals['cameras'][self.cameraDevId]['motion']['snapEnabled']:
                        # Only retrive FTP files if Snap Enabled
                        self.processFtpRetrieve()
                else:  # 1 = No Alarm
                    if  self.globals['cameras'][self.cameraDevId]['motion']['snapEnabled'] and self.globals['cameras'][self.cameraDevId]['motion']['detected']:
                        # Only retrive FTP files if Snap Enabled and motion previously detected
                        self.processFtpRetrieve()  # To pick up any files since motion detection ended

            self.globals['cameras'][self.cameraDevId]['motion']['detectionEnabled'] = motionDetectionEnabled
            self.globals['cameras'][self.cameraDevId]['motion']['detected'] = motionDetected
            self.messageHandlingDebugLogger.debug(u"%s [%s] Motion Detected: '%s'" % (self.cameraName, self.cameraAddress, str(motionDetected)))


            stateImageSel = indigo.kStateImageSel.SensorOff
            uiState = 'off'
            if motionDetectionEnabled:
                if motionDetected:
                    # Set timer to turn off motion detected (allows for user soecified timing of how long motion should indicate motion detected for)
                    if self.cameraDevId in self.globals['threads']['motionTimer']:
                        self.globals['threads']['motionTimer'][self.cameraDevId].cancel()
                    motionTimerSeconds = self.globals['cameras'][self.cameraDevId]['motion']['detectionInterval']
                    self.globals['threads']['motionTimer'][self.cameraDevId] = threading.Timer(motionTimerSeconds, self.handleTimerQueuedStatusCommand, [self.cameraDev, self.globals])
                    self.globals['threads']['motionTimer'][self.cameraDevId].start()
                    self.globals['cameras'][self.cameraDevId]['motion']['timerActive'] = True
                    stateImageSel = indigo.kStateImageSel.MotionSensorTripped
                    uiState = 'tripped'
                else:
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
            keyValue['value'] = motionDetectionEnabled
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'motionDetected'
            keyValue['value'] = motionDetected
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


    def processFtpRetrieve(self):
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
            alarmSaveFolderCamera = str('%s_%s' % (self.cameraDev.states["productName"].split("+")[0], self.cameraDev.states["mac"]))  # truncate productName on '+' e.g. 'FI9831W_A1B2C3D4E5F6' (productName_mac)
            alarmSaveFolderBase = str('%s/%s' % (alarmSaveRootFolder, alarmSaveFolderCamera))
            returnCode = subprocess.call(['mkdir', alarmSaveFolderBase])
            self.messageHandlingDebugLogger.debug(u"alarmSaveFolderBase [%s]: RC=%s" % (alarmSaveFolderBase, str(returnCode)))
            self.messageHandlingDebugLogger.debug(u"alarmFoldersToProcess: %s" % (alarmFoldersToProcess))



            try:
                ftp = FTP()
                ftp.connect(str(self.globals['cameras'][self.cameraDevId]['ipAddress']), self.globals['cameras'][self.cameraDevId]['ftpPort'])
                ftp.login(str(self.globals['cameras'][self.cameraDevId]['username']), str(self.globals['cameras'][self.cameraDevId]['password']))
                ftp.set_pasv(0)

                ftpSubDirectory = str('/IPCamera/%s/snap' % (alarmSaveFolderCamera))

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
                    if str(e) == '550':  # if folder not found - continue to next 
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
                    if str(e) == '550':  # if folder not found - continue to next 
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
            self.messageHandlingDebugLogger.error(u"processFtpRetrieve: StandardError detected for '%s' at line '%s' = %s" % (self.cameraDev.name, exc_tb.tb_lineno,  e))


    def processSnapPicture2(self, responseFromCamera):  # 'snapPicture2' Response handling
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
