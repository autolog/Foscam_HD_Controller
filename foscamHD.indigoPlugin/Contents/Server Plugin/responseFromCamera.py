#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2019-2023
# Requires Indigo 2022.1+
#

# ============================== Native Imports ===============================
import datetime
import ftplib
from ftplib import FTP
from pathlib import Path
import os
import queue
import subprocess
import sys
import threading
import time
import traceback

try:
    import xml.etree.cElementTree as et
except ImportError:
    import xml.etree.ElementTree as et

# ============================== Custom Imports ===============================
from constants import *
try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass


class ThreadResponseFromCamera(threading.Thread):

    def __init__(self, plugin_globals, devId, event):

        threading.Thread.__init__(self)

        self.globals = plugin_globals

        self.responseFromCameraLogger = logging.getLogger("Plugin.Response")

        self.responseFromCameraLogger.debug("Initialising Foscam HD Controller Response From Camera Thread")

        self.threadStop = event

        self.cameraDevId = int(devId)  # Set Indigo Device id (for camera) to value passed in Thread invocation
        self.cameraDev = indigo.devices[self.cameraDevId]
        self.cameraAddress = self.cameraDev.address
        self.cameraName = self.cameraDev.name

        self.globals[THREADS][HANDLE_RESPONSE][self.cameraDevId][THREAD_ACTIVE] = True

        self.all_existing_images_downloaded = False

        self.responseFromCameraLogger.debug(f"Initialised 'ResponseFromCamera' Thread for {self.cameraName} [{self.cameraAddress}]")
  
    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]  # noqa [Ignore duplicate code warning]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method} [{self.globals[PLUGIN_INFO][PLUGIN_VERSION]}]'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.responseFromCameraLogger.error(log_message)

    def run(self):

        try:
            time.sleep(DELAY_START_RESPONSE_FROM_CAMERA)  # Allow devices to start?

            self.responseFromCameraLogger.debug(f"'ResponseFromCamera' Thread for {self.cameraName} [{self.cameraAddress}] initialised and now running")

            # TODO: if ftp enable and FTP client mode
            if self.globals[CAMERAS][self.cameraDevId][FTP_PROCESS_MODE] == 1:  # FTP Client mode
                #   Only retrieve FTP files if FTP Client mode enabled and Snap Enabled and motion previously detected
                self._ftpClientRetrieve(True)  # To pick up any files since motion detection ended.Not an 'initialise' call
            elif self.globals[CAMERAS][self.cameraDevId][FTP_PROCESS_MODE] == 2:  # FTP Server mode
                #   Only process FTP'd files if FTP Server mode enabled and Snap Enabled and motion previously detected
                self._ftpServerProcess()  # To pick up any files since motion detection ended

            while not self.threadStop.is_set():
                try:
                    responseToHandle = self.globals[QUEUES][RESPONSE_FROM_CAMERA][self.cameraDevId].get(True, 5)
                    if responseToHandle[0] == CameraResponse.STOP_THREAD:
                        continue  # self.threadStop should be set

                    # self.responseFromCameraLogger.warning(f"responseToHandle = {responseToHandle}")  # TODO: Set to debug
                    commandTuple = responseToHandle[0]
                    # self.responseFromCameraLogger.warning(f"commandTuple = {commandTuple}")  # TODO: Set to debug
                    command = commandTuple[0]
                    response = responseToHandle[1]

                    processCommandMethod = "process" + command[0:1].upper() + command[1:]
                    # self.responseFromCameraLogger.warning(f"processCommand = {processCommandMethod}")  # TODO: Set to debug

                    # try:
                    #     processCommandMethodMethod = getattr(self, processCommandMethod)
                    #
                    #     processCommandMethodMethod(commandTuple, response)
                    # except Exception as exception_error:
                    #     self.exception_handler(exception_error, True)  # Log error and display failing statement

                    # self.responseFromCameraLogger.warning(f"Foscam Camera command '{command}' received.")
                    match command:
                        case CameraResponse.GET_RECORD_LIST:
                            self.processGetRecordList(commandTuple, response)
                        case CameraResponse.GET_RECORD_LIST1:
                            self.processGetRecordList1(commandTuple, response)
                        case CameraResponse.START_RECORD:
                            self.processStartRecord(commandTuple, response)
                        case CameraResponse.STOP_RECORD:
                            self.processStopRecord(commandTuple, response)
                        case CameraResponse.GET_SYSTEM_TIME:
                            self.processGetSystemTime(commandTuple, response)
                        case CameraResponse.SET_SYSTEM_TIME:
                            self.processSetSystemTime(commandTuple, response)
                        case CameraResponse.OPEN_INFRA_LED:
                            self.processOpenInfraLed(commandTuple, response)
                        case CameraResponse.CLOSE_INFRA_LED:
                            self.processCloseInfraLed(commandTuple, response)
                        case CameraResponse.REBOOT_SYSTEM:
                            self.processRebootSystem(commandTuple, response)
                        case CameraResponse.GET_MOTION_DETECT_CONFIG:
                            self.processGetMotionDetectConfig(commandTuple, response)
                        case CameraResponse.GET_MOTION_DETECT_CONFIG1:
                            self.processGetMotionDetectConfig1(commandTuple, response)
                        case CameraResponse.SET_MOTION_DETECT_CONFIG:
                            self.processSetMotionDetectConfig(commandTuple, response)
                        case CameraResponse.GET_SCHEDULE_RECORD_CONFIG:
                            self.processGetScheduleRecordConfig(commandTuple, response)
                        case CameraResponse.SET_SCHEDULE_RECORD_CONFIG:
                            self.processSetScheduleRecordConfig(commandTuple, response)
                        case CameraResponse.GET_DEV_NAME:
                            self.processGetDevName(commandTuple, response)
                        case CameraResponse.GET_PRODUCT_MODEL:
                            self.processGetProductModel(commandTuple, response)
                        case CameraResponse.GET_PRODUCT_MODEL_NAME:
                            self.processGetProductModelName(commandTuple, response)
                        case CameraResponse.GET_DEV_INFO:
                            self.processGetDevInfo(commandTuple, response)
                        case CameraResponse.GET_DEV_STATE:
                            self.processGetDevState(commandTuple, response)
                        case CameraResponse.SNAP_PICTURE2:
                            self.processSnapPicture2(commandTuple, response)
                        case CameraResponse.REFRESH:
                            self.processRefreshCamera(commandTuple, response)
                        case _:
                            self.responseFromCameraLogger.warning(f"Foscam Camera command '{command}' is not handled by the plugin.")

                except queue.Empty:
                    pass

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

            self.globals[CAMERAS][self.cameraDevId][KEEP_THREAD_ALIVE] = False

            self.responseFromCameraLogger.debug(f"Handle Command Thread ended for {self.cameraName} [{self.cameraAddress}]")

        self.responseFromCameraLogger.debug(f"ThreadResponseFromCamera ended for camera: {self.cameraName} [{self.cameraAddress}]")

        self.globals[THREADS][HANDLE_RESPONSE][self.cameraDevId][THREAD_ACTIVE] = False

    def processGetRecordList(self, commandTuple, responseFromCamera):  # 'getRecordList' Response handling
        self.processGetRecordList1(commandTuple, responseFromCamera)

    def processGetRecordList1(self, commandTuple, responseFromCamera):  # 'getRecordList1' Response handling
        pass

    def processStartRecord(self, commandTuple, responseFromCamera):  # 'getRecordList1' Response handling
        pass

    def processStopRecord(self, commandTuple, responseFromCamera):  # 'getRecordList1' Response handling
        pass

    def processGetSystemTime(self, commandTuple, responseFromCamera):  # 'getSystemTime' Response handling
        try:
            dynamicParams = {}  # Initialise the dictionary to store the GetSystemTime response from camera that will be used for SetSystemTime
            tree = et.ElementTree(et.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.responseFromCameraLogger.debug(f"XML: '{child_of_root.tag}' = {child_of_root.text}")
                if child_of_root.tag != "result":
                    if child_of_root.tag in ("ntpServer", "dateFormat", "timeFormat"):
                        dynamicParams[child_of_root.tag] = child_of_root.text  # store GetMotionDetectConfig element from original value

            indigoDateTime = datetime.datetime.utcnow()
            indigoDateTimeRAW = indigoDateTime.strftime("%Y%m%d%H%M%S")
            indigoDateTimeYear   = indigoDateTimeRAW[0:4] 
            indigoDateTimeMon    = indigoDateTimeRAW[4:6] 
            indigoDateTimeDay    = indigoDateTimeRAW[6:8] 
            indigoDateTimeHour   = indigoDateTimeRAW[8:10] 
            indigoDateTimeMinute = indigoDateTimeRAW[10:12] 
            indigoDateTimeSec    = indigoDateTimeRAW[12:14] 
                   
            dynamicParams["isDst"]      = '0'
            dynamicParams["dst"]        = '0'
            dynamicParams["year"]       = indigoDateTimeYear
            dynamicParams["mon"]        = indigoDateTimeMon.lstrip("0")
            dynamicParams["day"]        = indigoDateTimeDay.lstrip("0")
            dynamicParams["hour"]       = indigoDateTimeHour.lstrip("0")
            dynamicParams["minute"]     = indigoDateTimeMinute.lstrip("0")
            dynamicParams["sec"]        = indigoDateTimeSec.lstrip("0")
            timeZone                    = time.timezone if (time.localtime().tm_isdst == 0) else time.altzone
            dynamicParams["timeZone"]   = str(timeZone)
            dynamicParams["timeSource"] = "1"  # Set Time Manually

            timeZoneHours = int((timeZone / 3600) * -1)
            # timeZoneUi = f"{timeZoneHours}"
            # timezoneUi = '{0:+d}'.format((timeZone / 3600) * -1)  # From '2to3' conversion
            # timezoneUi = '00'
            timeZoneUi = f"-{timeZoneHours}" if timeZoneHours < 0 else f"+{timeZoneHours}"

            if ("dateFormat" in dynamicParams) and (dynamicParams["dateFormat"] == "2"):
                dateTimeUi = indigoDateTime.strftime("%m/%d/%Y")
            elif ("dateFormat" in dynamicParams) and (dynamicParams["dateFormat"] == "1"):
                dateTimeUi = indigoDateTime.strftime("%d/%m/%Y")
            else:  # Assume present and = '0'
                dateTimeUi = indigoDateTime.strftime("%Y-%m-%d")

            if ('timeFormat' in dynamicParams) and (dynamicParams["timeFormat"] == "0"):
                dateTimeUi = dateTimeUi + indigoDateTime.strftime(" %H:%M:%S %p")
            else:  # Assume present and = '1'
                dateTimeUi = dateTimeUi + indigoDateTime.strftime(" %H:%M:%S")

            indigo.server.log(f"'{self.cameraDev.name}' camera time synchronised to '{dateTimeUi} UTC {timeZoneUi}'")

            params = dynamicParams

            self.responseFromCameraLogger.debug(f"SET SYSTEM TIME for {self.cameraDev} : {params}")

            self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ('setSystemTime',), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processSetSystemTime(self, commandTuple, responseFromCamera):  # 'setSystemTime' Response handling
        pass

    def processOpenInfraLed(self, commandTuple, responseFromCamera):  # 'openInfraLed' Response handling
        params = {}
        self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ("getDevState",), params])  # Refresh state

    def processCloseInfraLed(self, commandTuple, responseFromCamera):  # 'closeInfraLed' Response handling
        params = {}
        self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ("getDevState",), params])  # Refresh state

    def processRebootSystem(self, commandTuple, responseFromCamera):  # 'rebootSystem' Response handling
        pass

    def processRefreshCamera(self, commandTuple, responseFromCamera):  # 'rebootSystem' Response handling
        try:
            if self.globals[CAMERAS][self.cameraDevId][FTP_PROCESS_MODE] == 1:  # FTP Client mode
                #   Only retrieve FTP files if FTP Client mode enabled and Snap Enabled and motion previously detected
                self._ftpClientRetrieve(True)
            elif self.globals[CAMERAS][self.cameraDevId][FTP_PROCESS_MODE] == 2:  # FTP Server mode
                #   Only process FTP'd files if FTP Server mode enabled and Snap Enabled and motion previously detected
                self._ftpServerProcess()

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processGetMotionDetectConfig(self, commandTuple, responseFromCamera):  # 'motionAlarmGet' Response handling
        self.processGetMotionDetectConfig1(commandTuple, responseFromCamera)

    def processGetMotionDetectConfig1(self, commandTuple, responseFromCamera):  # 'motionAlarmGet' Response handling
        try:
            keyValueList = []                   # Initialise list of Key Values for Camera Indigo device update of 'linkage' and 'isEnable'
            responseGetMotionDetectConfigDict = {}  # Initialise the dictionary to store the GetMotionDetectConfig response from camera
            tree = et.ElementTree(et.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.responseFromCameraLogger.debug(f"XML: '{child_of_root.tag}' = {child_of_root.text}")
                if child_of_root.tag != "result":
                    if child_of_root.tag == "linkage":
                        keyValue = {"key": child_of_root.tag, "value": child_of_root.text}
                        keyValueList.append(keyValue)  # for state update
                    elif child_of_root.tag == "isEnable":
                        keyValue = {"key": "motionDetectionIsEnabled", "value": child_of_root.text}
                        keyValueList.append(keyValue)  # for state update
                    else:
                        responseGetMotionDetectConfigDict[child_of_root.tag] = child_of_root.text  # store GetMotionDetectConfig element 
            self.cameraDev.updateStatesOnServer(keyValueList)  # Update linkage and isEnable states in Indigo camera device

            if len(commandTuple) != 3:  # if setMotionDetectConfig not required - return
                return 

            # At this point the real request is for a setMotionDetectConfig - the getMotionDetectConfig was done to ensure u-to-date values will be processed
            commandFunction = commandTuple[1]
            commandOption = commandTuple[2]

            executeSetMotionDetectConfig = False

            if commandFunction == ENABLE_MOTION_DETECT:
                motionDetectionIsEnabled = int(self.cameraDev.states["motionDetectionIsEnabled"])
                if commandOption == kOn:
                    motionDetectionIsEnabled = int(1)
                elif commandOption == kOff:    
                    motionDetectionIsEnabled = int(0)
                elif commandOption == kToggle:
                    motionDetectionIsEnabled = motionDetectionIsEnabled ^ 1  # Toggle bit 0
                else:
                    self.responseFromCameraLogger.error(f"Invalid EnableMotionDetect Command Option for '{self.cameraDev.name}': '{commandOption}'")
                    return 
                linkage = int(self.cameraDev.states["linkage"])
                executeSetMotionDetectConfig = True

            elif commandFunction == SNAP_PICTURE:
                linkage = int(self.cameraDev.states["linkage"])
                if commandOption == kOn:
                    linkage = linkage | 4  # Turn ON bit 2
                elif commandOption == kOff:    
                    linkage = linkage & ~4  # Turn OFF bit 2
                elif commandOption == kToggle:
                    linkage = linkage ^ 4  # Toggle bit 2
                else:
                    self.responseFromCameraLogger.error(f"Invalid Snap Command Option for '{self.cameraDev.name}': '{commandOption}'")
                    return 
                motionDetectionIsEnabled = int(self.cameraDev.states["motionDetectionIsEnabled"])
                executeSetMotionDetectConfig = True

            elif commandFunction == MOTION_DETECTION_RECORD:
                linkage = int(self.cameraDev.states["linkage"])
                if commandOption == kOn:
                    linkage = linkage | 8  # Turn ON bit 3
                elif commandOption == kOff:    
                    linkage = linkage & ~8  # Turn OFF bit 3
                elif commandOption == kToggle:
                    linkage = linkage ^ 8  # Toggle bit 3
                else:
                    self.responseFromCameraLogger.error(f"Invalid Snap Command Option for '{self.cameraDev.name}': '{commandOption}'")
                    return 
                motionDetectionIsEnabled = int(self.cameraDev.states["motionDetectionIsEnabled"])
                executeSetMotionDetectConfig = True

            elif commandFunction == RING:
                linkage = int(self.cameraDev.states["linkage"])
                if commandOption == kOn:
                    linkage = linkage | 1  # Turn ON bit 0
                elif commandOption == kOff:    
                    linkage = linkage & ~1  # Turn OFF bit 0
                elif commandOption == kToggle:
                    linkage = linkage ^ 1  # Toggle bit 0
                else:
                    self.responseFromCameraLogger.error(f"Invalid Ring Command Option for '{self.cameraDev.name}': '{commandOption}'")
                    return 
                motionDetectionIsEnabled = int(self.cameraDev.states["motionDetectionIsEnabled"])
                executeSetMotionDetectConfig = True

            if executeSetMotionDetectConfig:
                dynamicParams = dict(isEnable=str(motionDetectionIsEnabled), linkage=str(linkage))  # noqa

                params = dynamicParams.copy()
                params.update(responseGetMotionDetectConfigDict)

                self.responseFromCameraLogger.debug(f"SET MOTION DETECT CONFIG for {self.cameraDev} : {params}")

                self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ("setMotionDetectConfig",), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processSetMotionDetectConfig(self, commandTuple, responseFromCamera):  # 'motionAlarmEnable' / 'motionAlarmDisable' Response handling
        self.processSetMotionDetectConfig1(commandTuple, responseFromCamera)

    def processSetMotionDetectConfig1(self, commandTuple, responseFromCamera):  # 'motionAlarmEnable' / 'motionAlarmDisable' Response handling
        try:
            params = {}
            self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ("getDevState",), params])  # Refresh state

            params = {}
            self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ("getMotionDetectConfig",), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processGetScheduleRecordConfig(self, commandTuple, responseFromCamera):  # 'motionAlarmGet' Response handling
        try:
            keyValueList = []                   # Initialise list of Key Values for Camera Indigo device update of 'linkage' and 'isEnable'
            responseGetScheduleRecordConfig = {}  # Initialise the dictionary to store the GetMotionDetectConfig response from camera
            tree = et.ElementTree(et.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.responseFromCameraLogger.debug(f"XML: '{child_of_root.tag}' = {child_of_root.text}")
                if child_of_root.tag != "result":
                    if child_of_root.tag == "isEnable":
                        keyValue = {"key": "scheduleRecordEnabled", "value": bool(int(child_of_root.text))}
                        keyValueList.append(keyValue)  # for state update
                    else:
                        responseGetScheduleRecordConfig[child_of_root.tag] = child_of_root.text  # store GetMotionDetectConfig element 
            self.cameraDev.updateStatesOnServer(keyValueList)  # Update scheduleRecordIsEnable state in Indigo camera device

            if len(commandTuple) != 3:  # if setScheduleRecordConfig not required - return
                return 

            # At this point the real request is for a setMotionDetectConfig - the getMotionDetectConfig was done to ensure u-to-date values will be processed
            commandFunction = commandTuple[1]
            commandOption = commandTuple[2]

            executeScheduleRecordConfig = False
            scheduleRecordEnabled = None  # To avoid Pycharm warning

            if commandFunction == SCHEDULE_RECORD:
                scheduleRecordEnabled = int(self.cameraDev.states["scheduleRecordEnabled"])
                if commandOption == kOn:
                    scheduleRecordEnabled = "1"
                elif commandOption == kOff:    
                    scheduleRecordEnabled = "0"
                elif commandOption == kToggle:
                    scheduleRecordEnabled = str(scheduleRecordEnabled ^ 1)  # Toggle bit 0
                else:
                    self.responseFromCameraLogger.error(f"Invalid EnableScheduleRecord Command Option for '{self.cameraDev.name}': '{commandOption}'")
                    return 
                executeScheduleRecordConfig = True

            if executeScheduleRecordConfig:
                dynamicParams = dict(isEnable=scheduleRecordEnabled)

                params = dynamicParams.copy()
                params.update(responseGetScheduleRecordConfig)

                self.responseFromCameraLogger.debug(f"SET SCHEDULE RECORD CONFIG for {self.cameraDev} : {params}")

                self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ("setScheduleRecordConfig",), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processSetScheduleRecordConfig(self, commandTuple, responseFromCamera):  # 'motionAlarmEnable' / 'motionAlarmDisable' Response handling
        try:
            params = {}
            self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ("getDevState",), params])  # Refresh state

            params = {}
            self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ("getScheduleRecordConfig",), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processGetDevName(self, commandTuple, responseFromCamera):  # 'getDevName' Response handling
        pass

    def processGetProductModel(self, commandTuple, responseFromCamera):  # 'getProductModel' Response handling
        try:
            keyValueList = []
            tree = et.ElementTree(et.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.responseFromCameraLogger.debug(f"XML: '{child_of_root.tag}' = {child_of_root.text}")
                if child_of_root.tag == "model":
                    keyValue = {"key": child_of_root.tag, "value": child_of_root.text}
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processGetProductModelName(self, commandTuple, responseFromCamera):  # 'getProductModelName' Response handling
        try:
            modelName = ''
            keyValueList = []
            tree = et.ElementTree(et.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.responseFromCameraLogger.debug(f"XML: '{child_of_root.tag}' = {child_of_root.text}")
                if child_of_root.tag == "modelName":
                    modelName = child_of_root.text
                    keyValue = {"key": child_of_root.tag, "value": child_of_root.text}
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)

            if modelName != "":
                if self.cameraDev.model != modelName:
                    self.cameraDev.model = modelName
                    self.cameraDev.replaceOnServer()

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processGetDevInfo(self, commandTuple, responseFromCamera):  # 'getDevInfo' Response handling
        try:
            keyValueList = []
            tree = et.ElementTree(et.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                self.responseFromCameraLogger.debug(f"XML: '{child_of_root.tag}' = {child_of_root.text}")
                if child_of_root.tag in ("productName", "serialNo", "devName", "mac", "firmwareVer", "hardwareVer"):
                    if child_of_root.tag == "firmwareVer":
                        props = self.cameraDev.pluginProps
                        props["version"] = child_of_root.text
                        self.cameraDev.replacePluginPropsOnServer(props)
                    keyValue = {"key": child_of_root.tag, "value": child_of_root.text}
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processGetDevState(self, commandTuple, responseFromCamera):  # 'getDevState' Response handling
        try:
            keyValueList = []
            tree = et.ElementTree(et.fromstring(responseFromCamera))
            root = tree.getroot()
            for child_of_root in root:
                #  self.responseFromCameraLogger.debug(f"XML: '{child_of_root.tag}' = {child_of_root.text}")
                if child_of_root.tag != "result":
                    keyValue = {"key": child_of_root.tag}
                    # Next bit of logic stores SD space values as a numeric, so it can be compared in trigger conditions
                    if child_of_root.tag in ("sdFreeSpace", "sdTotalSpace"):
                        spaceValue = child_of_root.text
                        if child_of_root.text[-1:] == "k":
                            spaceValue = child_of_root.text[:-1]  # Remove trailing 'k'
                        try:
                            int(spaceValue) + 1  # Numeric Test
                        except ValueError:
                            spaceValue = 0  # Default to zero if no trailing k or invalid numeric
                        keyValue["value"] = spaceValue
                    else:
                        keyValue["value"] = child_of_root.text
                    keyValueList.append(keyValue)
            self.cameraDev.updateStatesOnServer(keyValueList)

            # motionDetectAlarm:   0 = Motion Detection Disabled
            #                      1 = Motion Detection Enabled - No motion detected
            #                      2 = Motion Detection Enabled - Motion detected
            motionDetectAlarm  = int(self.cameraDev.states["motionDetectAlarm"])

            snap_enabled  = bool((int(self.cameraDev.states["linkage"]) & 4) >> 2)

            if motionDetectAlarm == "0":  # 0 = Disabled
                pass
            else:
                if motionDetectAlarm == "2":  # Motion Detection Enabled and motion detected
                    if snap_enabled:
                        if self.globals[CAMERAS][self.cameraDevId][FTP_PROCESS_MODE] == 1:  # FTP Client mode
                            # Only retrieve FTP files if FTP Client mode enabled and Snap Enabled
                            self._ftpClientRetrieve(False)  # Not an 'initialise' call
                        elif self.globals[CAMERAS][self.cameraDevId][FTP_PROCESS_MODE] == 2:  # FTP Server mode
                            # Only process FTP'd files if FTP Server mode enabled and Snap Enabled
                            self._ftpServerProcess() 

                else:  # Motion Detection Enabled and no motion detected
                    if snap_enabled and self.globals[CAMERAS][self.cameraDevId][MOTION][PREVIOUSLY_DETECTED]:
                        if self.globals[CAMERAS][self.cameraDevId][FTP_PROCESS_MODE] == 1:  # FTP Client mode
                            #   Only retrieve FTP files if FTP Client mode enabled and Snap Enabled and motion previously detected
                            self._ftpClientRetrieve(False)  # To pick up any files since motion detection ended.Not an 'initialise' call
                        elif self.globals[CAMERAS][self.cameraDevId][FTP_PROCESS_MODE] == 2:  # FTP Server mode
                            #   Only process FTP'd files if FTP Server mode enabled and Snap Enabled and motion previously detected
                            self._ftpServerProcess()  # To pick up any files since motion detection ended 

            self.globals[CAMERAS][self.cameraDevId][MOTION][PREVIOUSLY_DETECTED] = bool(motionDetectAlarm >> 1)  # Only True if motionDetectAlarm value was 2
            self.responseFromCameraLogger.debug(f"{self.cameraName} [{self.cameraAddress}] Motion Detect Alarm value: '{motionDetectAlarm}'")

            stateImageSel = indigo.kStateImageSel.SensorOff
            uiState = "off"
            if motionDetectAlarm != 0:  # 0 = Motion Detection Disabled
                if motionDetectAlarm == 2:  # Motion Detection Enabled - Motion detected
                    # Set timer to turn off motion detected (allows for user specified timing of how long motion should indicate motion detected for)
                    if self.cameraDevId in self.globals[THREADS][MOTION_TIMER]:
                        self.globals[THREADS][MOTION_TIMER][self.cameraDevId].cancel()
                    motionTimerSeconds = self.globals[CAMERAS][self.cameraDevId][MOTION][DETECTION_INTERVAL]
                    self.globals[THREADS][MOTION_TIMER][self.cameraDevId] = threading.Timer(motionTimerSeconds, self.handleTimerQueuedStatusCommand, [self.cameraDev, self.globals])
                    self.globals[THREADS][MOTION_TIMER][self.cameraDevId].start()
                    self.globals[CAMERAS][self.cameraDevId][MOTION][TIMER_ACTIVE] = True
                    stateImageSel = indigo.kStateImageSel.MotionSensorTripped
                    uiState = "tripped"
                else:
                    # motionDetectAlarm = 1 = Motion Detection Enabled - No motion detected
                    if self.globals[CAMERAS][self.cameraDevId][MOTION][TIMER_ACTIVE]:
                        stateImageSel = indigo.kStateImageSel.MotionSensorTripped
                        uiState = "tripped"
                    else:
                        # only set "not tripped" if no timer active - if timer active, when timer fires, it will set to "not tripped"
                        stateImageSel = indigo.kStateImageSel.MotionSensor
                        uiState = "no motion"
            
            self.cameraDev.updateStateImageOnServer(stateImageSel)

            keyValueList = [
                dict(key="motionDetectionEnabled", value=bool(motionDetectAlarm & 3)),  # True if motionDetectAlarm = 1 or 2
                dict(key="motionDetected", value=bool(motionDetectAlarm & 2)),  # True if motionDetectAlarm = 2
                dict(key="onOffState", value=self.globals[CAMERAS][self.cameraDevId][MOTION][TIMER_ACTIVE], uiValue=uiState)
            ]
            self.cameraDev.updateStatesOnServer(keyValueList)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handleTimerQueuedStatusCommand(self, cameraDev, plugin_globals):
        # Motion Timer - Turn off Motion detected
        self.globals = plugin_globals
        if self.cameraDev.states["onOffState"]:  # Only turn-off motion detected if it is currently showing True (i.e. on)
            self.globals[CAMERAS][self.cameraDevId][MOTION][TIMER_ACTIVE] = False
            cameraDev.updateStateOnServer(key="onOffState", value=False, uiValue="no motion")
            self.cameraDev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor)
        else:
            self.responseFromCameraLogger.debug(f"handleTimerQueuedStatusCommand: {cameraDev.name} - Timer ignored as motion detected already off")

    def _ftpServerProcess(self):
        self.responseFromCameraLogger.debug(f"_ftpServerProcess called for '{self.cameraDev.name}'")
        try:
            dynamic_view = int(self.globals[CAMERAS][self.cameraDevId][MOTION][DYNAMIC_VIEW])
        except ValueError:
            dynamic_view = 0
        if dynamic_view != 0:
            indigo.server.broadcastToSubscribers("updateDynamicView", self.globals[CAMERAS][self.cameraDevId][MOTION][DYNAMIC_VIEW])

    def _ftpClientRetrieve(self, initialise):
        try:
            alarmSaveRootFolder = self.globals[CAMERAS][self.cameraDevId][ROOT_FOLDER]
            ftpCameraFolder = f"{self.cameraDev.states['productName'].split('+')[0]}_{self.cameraDev.states['mac']}"  # truncate productName on '+' e.g. 'FI9831W_A1B2C3D4E5F6' (productName_mac)
            self.globals[CAMERAS][self.cameraDevId][FTP_CAMERA_FOLDER] = ftpCameraFolder
            if self.globals[CAMERAS][self.cameraDevId][CAMERA_FOLDER] == '':
                alarmSaveFolderCamera = ftpCameraFolder
            else:
                alarmSaveFolderCamera = self.globals[CAMERAS][self.cameraDevId][CAMERA_FOLDER]

            alarmSaveFolderBase = f"{alarmSaveRootFolder}/{alarmSaveFolderCamera}"

            alarmFoldersToProcess = list()  # e.g. [[20230910, 20230910-133000],]
            alarmTimeUi = "N/A"

            if not initialise:
                alarmTime = indigo.server.getTime()
                alarmTimeUi = alarmTime.strftime("%Y%m%d-%H%M%S")  # e.g. '20160903-141636'
                alarmFtpDateFolder = alarmTime.strftime("%Y%m%d")  # e.g. '20160831'

                alarmTimeMinute = alarmTime.strftime("%M")  # e.g. '45'
                if alarmTimeMinute < "30":
                    derivedBaseHalfHour = "00"
                else:
                    derivedBaseHalfHour = "30"
                alarmFtpImageFolder = f"{alarmTime.strftime('%Y%m%d-%H')}{derivedBaseHalfHour}00"  # e.g. 20150415-143000

                alarmFoldersToProcess = [[alarmFtpDateFolder, alarmFtpImageFolder]]  # e.g. (20230910, 20230910-133000)

                alarmTimeDay = alarmFtpImageFolder[6:8]  # e.g. 15
                alarmTimeHour = alarmFtpImageFolder[9:11]  # e.g. 14
                alarmTimeHourMinute = alarmTimeHour + alarmTimeMinute

                # Logic to handle motion being detected over change of day, hour and half-hour
                if alarmTimeHourMinute == "0000":  # e.g. 20160831-000000
                    alarmTimeYesterday = alarmTime - datetime.timedelta(days=1)
                    alarmFtpDateFolder = alarmTimeYesterday.strftime("%Y%m%d")  # e.g. 20150415
                    alarmFtpImageFolder = f"{alarmTimeYesterday.strftime('%Y%m%d')}-233000"  # e.g. 20150414-233000
                    alarmFoldersToProcess[:0] = [[alarmFtpDateFolder, alarmFtpImageFolder]]  # Prepend to list
                elif alarmTimeMinute == "00" or alarmTimeMinute == "01":
                    alarmTimeLastHour = alarmTime - datetime.timedelta(hours=1)
                    alarmFtpDateFolder = alarmTimeLastHour.strftime("%Y%m%d")  # e.g. 20150415
                    alarmFtpImageFolder = f"{alarmTimeLastHour.strftime('%Y%m%d-%H')}3000"  # e.g. 20150414-123000
                    alarmFoldersToProcess[:0] = [[alarmFtpDateFolder, alarmFtpImageFolder]]  # Prepend to list
                elif alarmTimeMinute == '30' or alarmTimeMinute == "31":
                    alarmFtpImageFolder = f"{alarmTime.strftime('%Y%m%d-%H')}{derivedBaseHalfHour}00"  # e.g. 20150415-143000
                    alarmFoldersToProcess[:0] = [[alarmFtpDateFolder, alarmFtpImageFolder]]  # Prepend to list

            try:
                os.makedirs(alarmSaveFolderBase)
            except FileExistsError:
                pass
            except Exception as exception_error:
                pass
                self.exception_handler(exception_error, True)  # Log error and display failing statement

            try:
                ftp = FTP()
                ftp.connect(str(self.globals[CAMERAS][self.cameraDevId][IP_ADDRESS]), self.globals[CAMERAS][self.cameraDevId][FTP_PORT])
                ftp.login(str(self.globals[CAMERAS][self.cameraDevId][USERNAME]), str(self.globals[CAMERAS][self.cameraDevId][PASSWORD]))
                ftp.set_pasv(0)

                ftpSubDirectory = f"/IPCamera/{ftpCameraFolder}/snap"

                # DEBUGING RECURSIVE CALL Start ...

                # https://stackoverflow.com/questions/65123271/recursive-file-list-with-ftp

                # alarmFoldersToProcess = [[alarmFtpDateFolder, alarmFtpImageFolder]]  # e.g. (20230910, 20230910-133000)

                if initialise:
                    self.responseFromCameraLogger.info(f"Syncing the camera's SDD images to the Indigo Foscam images folder using FTP. ...")

                    def list_recursive(ftp, remotedir):
                        try:
                            ftp.cwd(remotedir)
                            for entry in ftp.mlsd():
                                if entry[1]['type'] == 'dir':
                                    # print(f"DIR ENTRY: {entry}")
                                    remotepath = remotedir + "/" + entry[0]
                                    # t_1 = time.time_ns()
                                    # t_diff = float((t_1 - t_0)//1000000) / 1000
                                    # print(f"Dir [{t_diff}]: {remotepath}")

                                    if len(entry[0]) == 15:  # e.g. 20170827-120000
                                        date = entry[0][0:8]
                                        half_hour = entry[0][9:15]
                                        alarmFoldersToProcess.append([date, f"{date}-{half_hour}"])

                                    list_recursive(ftp, remotepath)
                                # else:
                                #     if entry[0][0:7]  == "MDAlarm":
                                #         pass
                                #         # print(f"  {entry[0]}")
                        except Exception as exception_message:
                            print(exception_message)

                    # t_0 = time.time_ns()
                    list_recursive(ftp, ftpSubDirectory)
                    aaa = 1
                    # ... DEBUGING RECURSIVE CALL End
            except ftplib.error_perm as exception_error:
                self.exception_handler(exception_error, True)  # Log error and display failing statement
                try:
                    ftp.quit()  # noqa
                except ftplib.error_perm as exception_error:
                    pass    
                return

            file_count = 0

            for alarmFolderList in alarmFoldersToProcess:
                if initialise:
                    self.responseFromCameraLogger.info(f"Syncing Camera SSD Image Folder: {alarmFolderList[1]}")
                try:
                    ftp.cwd(ftpSubDirectory)  # e.g. '/IPCamera/FI9831W_A1B2C3D4E5F6/snap' (using productName_mac)
                except ftplib.error_perm as exception_error:
                    self.exception_handler(exception_error, True)  # Log error and display failing statement
                    ftp.quit()
                    return

                # self.responseFromCameraLogger.warning(f"Alarm Time [{alarmTimeUi}]: F1='{alarmFolderList[0]}', F2='{alarmFolderList[1]}'")  # TODO: Set to debug

                alarmFtpDateFolder = alarmFolderList[0]
                alarmFtpImageFolder = alarmFolderList[1]
                try:
                    currentPath = ftp.pwd()
                    # self.responseFromCameraLogger.warning(f"Current FTP Path: '{currentPath}',  alarmFtpImageFolder: '{alarmFtpImageFolder}'")  # TODO: Set to debug
                    ftp.cwd(alarmFtpDateFolder)
                except ftplib.error_perm as exception_error:
                    if str(exception_error)[0:3] == "550":  # if folder not found - continue to next
                        continue
                    else:
                        self.exception_handler(exception_error, True)  # Log error and display failing statement
                        ftp.quit()
                        return

                alarmSaveDateFolder = str(f"{alarmSaveFolderBase}/{alarmFtpDateFolder}")

                try:
                    Path(alarmSaveDateFolder).mkdir(parents=True, exist_ok=True)
                except Exception as exception_error:
                    pass
                    self.exception_handler(exception_error, True)  # Log error and display failing statement

                pass
                try:
                    currentPath = ftp.pwd()
                    # self.responseFromCameraLogger.warning(f"Current FTP Path: '{currentPath}',  alarmFtpImageFolder: '{alarmFtpImageFolder}'")  # TODO: Set to debug
                    ftp.cwd(alarmFtpImageFolder)
                except ftplib.error_perm as exception_error:
                    if str(exception_error)[0:3] == "550":  # if folder not found - continue to next
                        continue
                    else:
                        self.exception_handler(exception_error, True)  # Log error and display failing statement
                        ftp.quit()
                        return

                alarmSaveImageFolder = f'{alarmSaveDateFolder}/{alarmFtpImageFolder}'
                # returnCode = subprocess.call(["makedirs", alarmSaveImageFolder])
                # self.responseFromCameraLogger.warning(f"alarmSaveImageFolder [{alarmSaveImageFolder}]: RC={str(returnCode)}")  # TODO: Reset to debug

                try:
                    os.makedirs(alarmSaveImageFolder, exist_ok=True)
                except Exception as exception_error:
                    pass
                    self.exception_handler(exception_error, True)  # Log error and display failing statement

                indigoList = []
                # self.responseFromCameraLogger.warning(f"Alarm Save Image Folder: {alarmSaveImageFolder}")
                for file in sorted(os.listdir(alarmSaveImageFolder)):
                    if file.endswith(".jpg") and file.startswith("MDAlarm"):
                        indigoFilename = str(file).split(".jpg")[0]
                        indigoList.append(indigoFilename)
                        file_count += 1
                        # self.responseFromCameraLogger.warning(f"Indigo image: {indigoFilename} [{file_count}]")

                ftpList = []
                ftpListIn = []
                ftp.dir(ftpListIn.append)
                for ftpListEntry in ftpListIn:
                    ftpSplit = ftpListEntry.split()
                    ftpFileName = ftpSplit[len(ftpSplit)-1]
                    if ftpFileName.endswith(".jpg"):
                        ftpFileName = ftpFileName.split(".jpg")[0]
                        ftpList.append(ftpFileName)
                        # self.responseFromCameraLogger.warning(f"Found FTP Camera Image: {ftpFileName}")

                missingFromSavedList = list(set(ftpList) - set(indigoList))
                missingFromSavedList.sort()

                for missingFromSavedListEntry in missingFromSavedList:
                    # self.responseFromCameraLogger.warning(f"Saving FTP image to Apple Mac: {missingFromSavedListEntry}")
                    savedFileName = f"{alarmSaveImageFolder}/{missingFromSavedListEntry}.jpg"
                    savedFile = open(savedFileName, "wb")
                    ftpRetr = f"RETR {missingFromSavedListEntry}.jpg"
                    ftp.retrbinary(ftpRetr, savedFile.write)
                    savedFile.close()
                    time.sleep(0.1)  # To avoid overloading the camera

            ftp.quit()

            if initialise:
                self.responseFromCameraLogger.info(f"... Syncing complete.")

            try:
                dynamic_view = int(self.globals[CAMERAS][self.cameraDevId][MOTION][DYNAMIC_VIEW])
            except ValueError:
                dynamic_view = 0
            if dynamic_view != 0:
                indigo.server.broadcastToSubscribers("updateDynamicView", self.globals[CAMERAS][self.cameraDevId][MOTION][DYNAMIC_VIEW])

            # self.globals['cameras'][self.cameraDevId]['motion']['imageFolder'] = ''  # Force to latest folder

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processSnapPicture2(self, commandTuple, responseFromCamera):  # 'snapPicture2' Response handling
        self.responseFromCameraLogger.info("SNAP IMAGE PROCESSING NOT YET AVAILABLE!")

    #     try:
    #         snappath = "T B A"
    #         f = open(snappath, 'w')
    #         f.write(responseFromCamera)
    #         f.close()
    #     except Exception as exception_error:
    #         self.exception_handler(exception_error, True)  # Log error and display failing statement
