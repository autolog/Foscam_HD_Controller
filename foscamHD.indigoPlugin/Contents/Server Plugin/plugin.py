#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2016-2107
# Requires Indigo 7
#

try:
    import indigo
except ImportError:
    pass
import inspect
import logging
import Queue
import sys
import threading
from time import time
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from constants import *
from ghpu import GitHubPluginUpdater
from polling import ThreadPolling
from sendCommand import ThreadSendCommand
from responseFromCamera import ThreadResponseFromCamera


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        # Initialise dictionary to store plugin Globals
        self.globals = {}

        # Initialise dictionary for debug in plugin Globals
        self.globals['debug'] = {}
        self.globals['debug']['monitorDebugEnabled']  = False  # if False it indicates no debugging is active else it indicates that at least one type of debug is active

        self.globals['debug']['filteredIpAddress']    = ''     # Set to Camera IP Address to limit processing for debug purposes

        self.globals['debug']['debugGeneral']     = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['monitorSend']      = logging.INFO  # For monitoring messages sent to camera(s) 
        self.globals['debug']['debugSend']        = logging.INFO  # For debugging messages sent to camera(s)
        self.globals['debug']['monitorReceive']   = logging.INFO  # For monitoring responses received from camera(s) 
        self.globals['debug']['debugReceive']     = logging.INFO  # For debugging responses received from camera(s)
        self.globals['debug']['monitorHandleMsg'] = logging.INFO  # For monitoring message handling
        self.globals['debug']['debugHandleMsg']   = logging.INFO  # For debugging message handling
        self.globals['debug']['debugMethodTrace'] = logging.INFO  # For displaying method invocations i.e. trace method
        self.globals['debug']['debugPolling']     = logging.INFO  # For polling debugging

        self.globals['debug']['previousDebugGeneral']     = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['previousMonitorSend']      = logging.INFO  # For monitoring messages sent to camera(s)
        self.globals['debug']['previousDebugSend']        = logging.INFO  # For debugging messages sent to camera(s)
        self.globals['debug']['previousMonitorReceive']   = logging.INFO  # For monitoring messages received from camera(s)
        self.globals['debug']['previousDebugReceive']     = logging.INFO  # For debugging messages received from camera(s)
        self.globals['debug']['previousMonitorHandleMsg'] = logging.INFO  # For monitoring message handling
        self.globals['debug']['previousDebugHandleMsg']   = logging.INFO  # For debugging message handling
        self.globals['debug']['previousDebugMethodTrace'] = logging.INFO  # For displaying method invocations i.e. trace method
        self.globals['debug']['previousDebugPolling']     = logging.INFO  # For polling debugging

        # Setup Logging

        logformat = logging.Formatter('%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(logformat)

        self.plugin_file_handler.setLevel(logging.INFO)  # Master Logging Level for Plugin Log file

        self.indigo_log_handler.setLevel(logging.INFO)   # Logging level for Indigo Event Log

        self.generalLogger = logging.getLogger("Plugin.general")
        self.generalLogger.setLevel(self.globals['debug']['debugGeneral'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        # Initialising Message
        self.generalLogger.info(u"Autolog 'Foscam HD Controller' initializing . . .")

        # Initialise dictionary to store internal details about cameras
        self.globals['cameras'] = {}

        # Initialise dictionary for polling thread
        self.globals['polling'] = {}

        self.globals['testSymLink'] = False

        # Initialise dictionary for update checking
        self.globals['update'] = {}

        self.validatePrefsConfigUi(pluginPrefs)  # Validate the Plugin Config before plugin initialisation

        self.setDebuggingLevels(pluginPrefs)  # Check monitoring and debug options  

        # set possibly updated logging levels
        self.generalLogger.setLevel(self.globals['debug']['debugGeneral'])
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

    def __del__(self):
        indigo.PluginBase.__del__(self)


    def updatePlugin(self):
        self.globals['update']['updater'].update()

    def checkForUpdates(self):
        self.globals['update']['updater'].checkForUpdate()

    def forceUpdate(self):
        self.globals['update']['updater'].update(currentVersion='0.0.0')

    def checkRateLimit(self):
        limiter = self.globals['update']['updater'].getRateLimit()
        indigo.server.log('RateLimit {limit:%d remaining:%d resetAt:%d}' % limiter)

    def startup(self):

        self.methodTracer.threaddebug(u"CLASS: Plugin")

        # Set-up update checker
        self.globals['update']['updater'] = GitHubPluginUpdater(self)
        self.globals['update']['nextCheckTime'] = time()

        self.globals['queues'] = {}
        self.globals['queues']['commandToSend'] = {}  # There will be one 'commandToSend' queue for each camera - set-up in camera device start
        self.globals['queues']['responseFromCamera'] = {}  # There will be one 'responseFromCamera' queue for each camera - set-up in camera device start

        indigo.devices.subscribeToChanges()

        self.globals['threads'] = {}
        self.globals['threads']['sendCommand'] = {}   # One thread per camera
        self.globals['threads']['handleResponse'] = {}  # One thread per camera
        self.globals['threads']['pollCamera'] = {}  # One thread per camera
        self.globals['threads']['motionTimer'] = {} # One thread per camera

        self.generalLogger.info(u"Autolog 'Foscam HD Controller' initialization complete")


    def shutdown(self):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.info(u"Autolog 'Foscam HD Controller' Plugin shutdown complete")


    def validatePrefsConfigUi(self, valuesDict):

        self.methodTracer.threaddebug(u"CLASS: Plugin")

        return True


    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"'closePrefsConfigUi' called with userCancelled = %s" % (str(userCancelled)))  

        if userCancelled == True:
            return

        # Check monitoring and debug options  
        self.setDebuggingLevels(valuesDict)


    def setDebuggingLevels(self, valuesDict):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.globals['debug']['monitorDebugEnabled'] = bool(valuesDict.get("monitorDebugEnabled", False))

        self.globals['debug']['debugGeneral']     = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['monitorSend']      = logging.INFO  # For monitoring messages sent to camera(s)
        self.globals['debug']['debugSend']        = logging.INFO  # For debugging messages sent to camera(s)
        self.globals['debug']['monitorReceive']   = logging.INFO  # For monitoring messages received from camera(s) 
        self.globals['debug']['debugReceive']     = logging.INFO  # For debugging messages received to camera(s)
        self.globals['debug']['monitorMessageHandling'] = logging.INFO  # For monitoring message handling
        self.globals['debug']['debugMessageHandling']   = logging.INFO  # For debugging message handling
        self.globals['debug']['debugMethodTrace'] = logging.INFO  # For displaying method invocations i.e. trace method
        self.globals['debug']['debugPolling']     = logging.INFO  # For polling debugging

        if self.globals['debug']['monitorDebugEnabled'] == False:
            self.plugin_file_handler.setLevel(logging.INFO)
        else:
            self.plugin_file_handler.setLevel(logging.THREADDEBUG)

        debugGeneral           = bool(valuesDict.get("debugGeneral", False))
        monitorSend            = bool(valuesDict.get("monitorSend", False))
        debugSend              = bool(valuesDict.get("debugSend", False))
        monitorReceive         = bool(valuesDict.get("monitorReceive", False))
        debugReceive           = bool(valuesDict.get("debugReceive", False))
        monitorMessageHandling = bool(valuesDict.get("monitorMessageHandling", False))
        debugMessageHandling   = bool(valuesDict.get("debugMessageHandling", False))
        debugMethodTrace       = bool(valuesDict.get("debugMethodTrace", False))
        debugPolling           = bool(valuesDict.get("debugPolling", False))

        if debugGeneral:
            self.globals['debug']['debugGeneral'] = logging.DEBUG 
        if monitorSend:
            self.globals['debug']['monitorSend'] = logging.DEBUG
        if debugSend:
            self.globals['debug']['debugSend'] = logging.DEBUG
        if monitorReceive:
            self.globals['debug']['monitorReceive'] = logging.DEBUG
        if debugReceive:
            self.globals['debug']['debugReceive'] = logging.DEBUG
        if monitorMessageHandling:
            self.globals['debug']['monitorMessageHandling'] = logging.DEBUG
        if debugMessageHandling:
            self.globals['debug']['debugMessageHandling'] = logging.DEBUG
        if debugMethodTrace:
            self.globals['debug']['debugMethodTrace'] = logging.THREADDEBUG
        if debugPolling:
            self.globals['debug']['debugPolling'] = logging.DEBUG

        self.globals['debug']['monitoringActive'] = monitorSend or monitorReceive or monitorMessageHandling

        self.globals['debug']['debugActive'] = debugGeneral or debugSend or debugReceive or debugMessageHandling or debugMethodTrace or debugPolling

        if not self.globals['debug']['monitorDebugEnabled'] or (not self.globals['debug']['monitoringActive'] and not self.globals['debug']['debugActive']):
            self.generalLogger.info(u"No monitoring or debugging requested")
        else:
            if not self.globals['debug']['monitoringActive']:
                self.generalLogger.info(u"No monitoring requested")
            else:
                monitorTypes = []
                if monitorSend:
                    monitorTypes.append('Send')
                if monitorReceive:
                    monitorTypes.append('Receive')
                if monitorMessageHandling:
                    monitorTypes.append('Message Handling')
                message = self.listActive(monitorTypes)   
                self.generalLogger.warning(u"Monitoring enabled for Foscam HD: %s" % (message))  

            if not self.globals['debug']['debugActive']:
                self.generalLogger.info(u"No debugging requested")
            else:
                debugTypes = []
                if debugGeneral:
                    debugTypes.append('General')
                if debugSend:
                    debugTypes.append('Send')
                if debugReceive:
                    debugTypes.append('Receive')
                if debugMessageHandling:
                    debugTypes.append('Message Handling')
                if debugMethodTrace:
                    debugTypes.append('Method Trace')
                if debugPolling:
                    debugTypes.append('Polling')
                message = self.listActive(debugTypes)   
                self.generalLogger.warning(u"Debugging enabled for Foscam HD: %s" % (message))  

    def listActive(self, monitorDebugTypes):            
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        loop = 0
        listedTypes = ''
        for monitorDebugType in monitorDebugTypes:
            if loop == 0:
                listedTypes = listedTypes + monitorDebugType
            else:
                listedTypes = listedTypes + ', ' + monitorDebugType
            loop += 1
        return listedTypes

    def runConcurrentThread(self):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        # This thread is used to detect plugin close down only

        try:
            while True:
                self.sleep(60) # in seconds
        except self.StopThread:
            self.generalLogger.info(u"Autolog 'Foscam HD Controller' Plugin shutdown requested")

            self.generalLogger.debug(u"runConcurrentThread being ended . . .")   
            for self.cameraDevId in self.globals['threads']['motionTimer']:
                self.globals['threads']['motionTimer'][self.cameraDevId].cancel()

            for self.cameraDevId in self.globals['threads']['pollCamera']:
                if self.globals['threads']['pollCamera'][self.cameraDevId]['threadActive']:
                    self.generalLogger.debug(u"%s 'polling camera' BEING STOPPED" % (indigo.devices[self.cameraDevId].name))
                    self.globals['threads']['pollCamera'][self.cameraDevId]['event'].set()  # Stop the Thread

            for self.cameraDevId in self.globals['threads']['sendCommand']:
                if self.globals['threads']['sendCommand'][self.cameraDevId]['threadActive']:
                    self.generalLogger.debug(u"'sendCommand' BEING STOPPED")
                    self.globals['threads']['sendCommand'][self.cameraDevId]['event'].set()  # Stop the Thread
                    self.globals['queues']['commandToSend'][self.cameraDevId].put(['STOPTHREAD'])

            for self.cameraDevId in self.globals['threads']['handleResponse']:
                if self.globals['threads']['handleResponse'][self.cameraDevId]['threadActive']:
                    self.generalLogger.debug(u"''handleResponse' BEING STOPPED")
                    self.globals['threads']['handleResponse'][self.cameraDevId]['event'].set()  # Stop the Thread
                    self.globals['queues']['responseFromCamera'][self.cameraDevId].put(['STOPTHREAD'])

            for self.cameraDevId in self.globals['threads']['pollCamera']:
                if self.globals['threads']['pollCamera'][self.cameraDevId]['threadActive']:
                    self.globals['threads']['pollCamera'][self.cameraDevId]['thread'].join(7.0)  # wait for thread to end
                    self.generalLogger.debug(u"%s 'polling camera' NOW STOPPED" % (indigo.devices[self.cameraDevId].name))

            for self.cameraDevId in self.globals['threads']['sendCommand']:
                if self.globals['threads']['sendCommand'][self.cameraDevId]['threadActive']:
                    self.globals['threads']['sendCommand'][self.cameraDevId]['thread'].join(7.0)  # wait for thread to end
                    self.generalLogger.debug(u"'sendCommand' NOW STOPPED")

            for self.cameraDevId in self.globals['threads']['handleResponse']:
                if self.globals['threads']['handleResponse'][self.cameraDevId]['threadActive']:
                    self.globals['threads']['handleResponse'][self.cameraDevId]['thread'].join(7.0)  # wait for thread to end
                    self.generalLogger.debug(u"''handleResponse' NOW STOPPED")

        self.generalLogger.debug(u". . . runConcurrentThread now ended")   



    def deviceStartComm(self, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.currentTime = indigo.server.getTime()

        dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used

        try:
            self.globals['cameras'][dev.id] = {}

            self.globals['cameras'][dev.id]['datetimeStarted'] = self.currentTime
            self.globals['cameras'][dev.id]['ipAddress'] = dev.pluginProps.get('ipaddress', 'unknown')
            self.globals['cameras'][dev.id]['port'] = dev.pluginProps['port']
            self.globals['cameras'][dev.id]['username'] = dev.pluginProps['username']
            self.globals['cameras'][dev.id]['password'] = dev.pluginProps['password']
            self.globals['cameras'][dev.id]['ipAddressPort'] = dev.pluginProps['ipaddress'] + ":" + dev.pluginProps['port']
            self.globals['cameras'][dev.id]['ipAddressPortName'] = (self.globals['cameras'][dev.id]['ipAddressPort'].replace('.','-')).replace(':','-')
            self.globals['cameras'][dev.id]['enableFTP'] = dev.pluginProps.get("enableFTP", True)
            self.globals['cameras'][dev.id]['ftpPort'] = int(dev.pluginProps.get('ftport', 50021))
            self.globals['cameras'][dev.id]['ftpFolderCamera'] = dev.pluginProps.get('ftpFolderCamera', '')
            self.globals['cameras'][dev.id]['rootFolder'] =  dev.pluginProps.get('rootFolder', '~/Documents')
            self.globals['cameras'][dev.id]['cameraFolder'] =  dev.pluginProps.get('cameraFolder', '')
            self.globals['cameras'][dev.id]['enableAutoTimeSync'] = dev.pluginProps.get("enableAutoTimeSync", True)

            self.globals['cameras'][dev.id]['cameraPlatform'] = int(dev.pluginProps.get('cameraPlatform', kOriginal))
            self.globals['cameras'][dev.id]['status'] = 'starting'
            self.globals['cameras'][dev.id]['motion'] = {}
            self.globals['cameras'][dev.id]['motion']['setMotionDetectConfigFunction'] = kNotSet  # kNotSet, kEnableMotionDetect, kRing, kSnapPicture
            self.globals['cameras'][dev.id]['motion']['setMotionDetectConfigOption'] = kNotSet  # kNotSet, kOn, kOff, kToggle
            # self.globals['cameras'][dev.id]['motion']['detectionEnabled'] = False
            self.globals['cameras'][dev.id]['motion']['previouslyDetected'] = False
            self.globals['cameras'][dev.id]['motion']['detectionInterval'] = float(dev.pluginProps.get('motionDetectionInterval', 30.0))
            self.globals['cameras'][dev.id]['motion']['dynamicView'] = str(dev.pluginProps.get('dynamicView', ''))
            self.globals['cameras'][dev.id]['motion']['timerActive'] = False

            self.globals['cameras'][dev.id]['motion']['ringEnabled'] = False
            self.globals['cameras'][dev.id]['motion']['snapEnabled'] = False

            self.globals['cameras'][dev.id]['motion']['lastAlertFileTime'] = 0
            self.globals['cameras'][dev.id]['motion']['images'] = []  # List of alarm images
            self.globals['cameras'][dev.id]['motion']['imageNumber'] = 0  
            self.globals['cameras'][dev.id]['motion']['imageFile'] = ''
            self.globals['cameras'][dev.id]['motion']['imageFilePrevious'] = ''  
            self.globals['cameras'][dev.id]['motion']['imageFolderList'] = []
            self.globals['cameras'][dev.id]['motion']['imageFolder'] = ''
            self.globals['cameras'][dev.id]['motion']['imageFolderPrevious'] = ''
            self.globals['cameras'][dev.id]['motion']['days'] = []
            self.globals['cameras'][dev.id]['motion']['lastDisplayedImageHalfHour'] = ''
            self.globals['cameras'][dev.id]['motion']['lastDisplayedImageDay'] = ''
            self.globals['cameras'][dev.id]['motion']['lastDisplayedImageSelected'] = ''

            updatePropsRequired = False
            self.props = dev.pluginProps
            if 'address' not in self.props or self.props['address'] != self.globals['cameras'][dev.id]['ipAddressPort']:
                self.props['address'] = self.globals['cameras'][dev.id]['ipAddressPort']
                updatePropsRequired = True
            if 'AllowOnStateChange' not in self.props or self.props['AllowOnStateChange'] != True:   
                self.props['AllowOnStateChange'] = True
                updatePropsRequired = True
            if updatePropsRequired:
                self.generalLogger.debug(u"Updating props and restarting device %s ..." % (indigo.devices[dev.id].name))
                dev.replacePluginPropsOnServer(self.props)
                return

            if 'commandToSend' in self.globals['queues']:
                if dev.id in self.globals['queues']['commandToSend']:
                    with self.globals['queues']['commandToSend'][dev.id].mutex:
                        self.globals['queues']['commandToSend'][dev.id].queue.clear  # clear existing 'commandToSend' queue for camera
                else: 
                    self.globals['queues']['commandToSend'][dev.id] = Queue.Queue()  # set-up 'commandToSend' queue for camera

            if 'responseFromCamera' in self.globals['queues']:
                if dev.id in self.globals['queues']['responseFromCamera']:
                    with self.globals['queues']['responseFromCamera'][dev.id].mutex:
                        self.globals['queues']['responseFromCamera'][dev.id].queue.clear  # clear existing 'responseFromCamera'  queue for camera
                else: 
                    self.globals['queues']['responseFromCamera'][dev.id]= Queue.Queue()  # set-up 'responseFromCamera' queue for  camera

            if dev.id in self.globals['threads']['sendCommand'] and self.globals['threads']['sendCommand'][dev.id]['threadActive']:
                self.generalLogger.debug(u"'sendCommand' BEING STOPPED")
                self.globals['threads']['sendCommand'][dev.id]['event'].set()  # Stop the Thread
                self.globals['threads']['sendCommand'][dev.id]['thread'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"'sendCommand' NOW STOPPED")

            self.globals['threads']['sendCommand'][dev.id] = {}
            self.globals['threads']['sendCommand'][dev.id]['threadActive'] = False
            self.globals['threads']['sendCommand'][dev.id]['event'] = threading.Event()
            self.globals['threads']['sendCommand'][dev.id]['thread'] = ThreadSendCommand(self.globals, dev.id, self.globals['threads']['sendCommand'][dev.id]['event'])
            self.globals['threads']['sendCommand'][dev.id]['thread'].start()

            if dev.id in self.globals['threads']['handleResponse'] and self.globals['threads']['handleResponse'][dev.id]['threadActive']:
                self.generalLogger.debug(u"''handleResponse' BEING STOPPED")
                self.globals['threads']['handleResponse'][dev.id]['event'].set()  # Stop the Thread
                self.globals['threads']['handleResponse'][dev.id]['thread'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"''handleResponse' NOW STOPPED")
 
            self.globals['threads']['handleResponse'][dev.id] = {}
            self.globals['threads']['handleResponse'][dev.id]['threadActive'] = False
            self.globals['threads']['handleResponse'][dev.id]['event'] = threading.Event()
            self.globals['threads']['handleResponse'][dev.id]['thread'] = ThreadResponseFromCamera(self.globals, dev.id, self.globals['threads']['handleResponse'][dev.id]['event'])
            self.globals['threads']['handleResponse'][dev.id]['thread'].start()

            if dev.id in self.globals['threads']['pollCamera'] and self.globals['threads']['pollCamera'][dev.id]['threadActive']:
                self.generalLogger.debug(u"%s 'polling camera' BEING STOPPED" % (indigo.devices[dev.id].name))
                self.globals['threads']['pollCamera'][dev.id]['event'].set()  # Stop the Thread
                self.globals['threads']['pollCamera'][dev.id]['thread'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"%s 'polling camera' NOW STOPPED" % (indigo.devices[dev.id].name))

            if self.props["statusPolling"]:
                self.globals['polling'][dev.id] = {}
                self.globals['polling'][dev.id]['status']    = True
                self.globals['polling'][dev.id]['seconds']   = float(self.props['pollingSeconds'])

                self.globals['threads']['pollCamera'][dev.id] = {}
                self.globals['threads']['pollCamera'][dev.id]['threadActive'] = False
                self.globals['threads']['pollCamera'][dev.id]['event'] = threading.Event()
                self.globals['threads']['pollCamera'][dev.id]['thread'] = ThreadPolling(self.globals, dev.id, self.globals['threads']['pollCamera'][dev.id]['event'])
                self.globals['threads']['pollCamera'][dev.id]['thread'].start() 

            keyValueList = []
            keyValue = {}
            keyValue['key'] = 'motionDetectionEnabled'
            keyValue['value'] = False
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'motionDetected'
            keyValue['value'] = False
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'onOffState'
            keyValue['value'] = False
            keyValueList.append(keyValue)
            dev.updateStatesOnServer(keyValueList)
            dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            indigo.devices[dev.id].setErrorStateOnServer(u"no ack")  # default to "no ack" at device startup - will be corrected when communication established

            if self.globals['cameras'][dev.id]['enableAutoTimeSync']:
                params = {}
                self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getSystemTime',), params])

            params = {}
            self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getProductModel',), params])

            self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getProductModelName',), params])

            self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getDevInfo',), params])

            self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getDevState',), params])

            self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig',), params])

            self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getScheduleRecordConfig',), params])

            self.generalLogger.debug(u"%s Device Start Completed" % (indigo.devices[dev.id].name))
        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.generalLogger.error(u"deviceStartComm: StandardError detected for '%s' at line '%s' = %s" % (dev.name, exc_tb.tb_lineno,  e))   


    def getDeviceConfigUiValues(self, pluginProps, typeId, devId):

        # Set default values for Edit Device Settings... (ConfigUI)

        pluginProps["enableFTP"] = pluginProps.get("enableFTP", True)
        pluginProps["ftpPort"] = pluginProps.get("ftpPort", '50021')

        pluginProps["ftpCameraFolder"] = pluginProps.get("ftpCameraFolder", '')
        if devId in self.globals['cameras']:
            ftpCameraFolder = self.globals['cameras'][devId].get("ftpCameraFolder", '')
            if ftpCameraFolder != '':
                pluginProps["ftpCameraFolder"] = ftpCameraFolder

        pluginProps["rootFolder"] = pluginProps.get("rootFolder", '~/Documents')
        pluginProps["cameraFolder"] = pluginProps.get("cameraFolder", '')
        pluginProps["enableAutoTimeSync"] = pluginProps.get("enableAutoTimeSync", True)
        pluginProps["ShowPasswordButtonDisplayed"] = pluginProps.get("ShowPasswordButtonDisplayed", True)

        pluginProps["dynamicView"] = pluginProps.get("dynamicView", '')

        if pluginProps["ShowPasswordButtonDisplayed"]:
            pluginProps["passwordInClearText"] = '*' * len(pluginProps.get("password", ''))
        else:            
            pluginProps["passwordInClearText"] = pluginProps.get("password", '')

        pluginProps["cameraPlatform"] = pluginProps.get("cameraPlatform", 0)

        pluginProps["statusPolling"] = pluginProps.get("statusPolling", True)

        pluginProps["pollingSeconds"] = pluginProps.get("pollingSeconds", 5)

        pluginProps["motionDetectionInterval"] = pluginProps.get("motionDetectionInterval", 30)

        return super(Plugin, self).getDeviceConfigUiValues(pluginProps, typeId, devId)

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        if typeId == "camera":

            # Validate 'motionDetectionInterval ' value
            motionDetectionIntervalIsValid = True
            motionDetectionInterval = valuesDict["motionDetectionInterval"]
            if motionDetectionInterval != "":
                try:
                    validateField = int(motionDetectionInterval)
                    if validateField < 15:
                        motionDetectionIntervalIsValid = False  # Not in valid range
                except:
                    motionDetectionIntervalIsValid = False   # Not numeric

                if motionDetectionIntervalIsValid == False:
                    errorDict = indigo.Dict()
                    errorDict["motionDetectionInterval"] = "Default Detection Interval must be an integer and greater than 15."
                    errorDict["showAlertText"] = "You must enter a valid Detection Interval value for the camera. It must be an integer greater than 15."
                    return (False, valuesDict, errorDict)
                else:
                    valuesDict["motionDetectionInterval"] = motionDetectionInterval
            else:
                valuesDict["motionDetectionInterval"] = '30'  # Default in seconds

        return (True, valuesDict)

    def deviceShowPassword(self, valuesDict, typeId, devId):
        valuesDict["ShowPasswordButtonDisplayed"] = False
        valuesDict["passwordInClearText"] = valuesDict["password"]
        return valuesDict

    def deviceHidePassword(self, valuesDict, typeId, devId):
        valuesDict["ShowPasswordButtonDisplayed"] = True
        valuesDict["passwordInClearText"] = '*' * len(valuesDict.get("password", ''))
        return valuesDict

    def deviceStopComm(self, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            if dev.id in self.globals['threads']['motionTimer']:
                self.globals['cameras'][dev.id]['motion']['timerActive'] = False
                self.globals['threads']['motionTimer'][dev.id].cancel()

            if dev.id in self.globals['threads']['pollCamera'] and self.globals['threads']['pollCamera'][dev.id]['threadActive']:
                # self.generalLogger.debug(u"%s 'polling camera' BEING STOPPED" % (indigo.devices[dev.id].name))
                self.generalLogger.debug(u"Device Stop: %s 'polling camera' BEING STOPPED" % (dev.name))
                self.globals['threads']['pollCamera'][dev.id]['event'].set()  # Stop the Thread
                self.globals['threads']['pollCamera'][dev.id]['thread'].join(7.0)  # wait for thread to end
                # self.generalLogger.debug(u"%s 'polling camera' NOW STOPPED" % (indigo.devices[dev.id].name))
                self.generalLogger.debug(u"Device Stop: %s 'polling camera' NOW STOPPED" % (dev.name))
                self.globals['threads']['pollCamera'].pop(dev.id, None)  # Remove Thread


            if dev.id in self.globals['threads']['sendCommand'] and self.globals['threads']['sendCommand'][dev.id]['threadActive']:
                self.generalLogger.debug(u"Device Stop: 'sendCommand' BEING STOPPED")
                self.globals['threads']['sendCommand'][dev.id]['event'].set()  # Stop the Thread
                self.globals['queues']['commandToSend'][dev.id].put(['STOPTHREAD'])
                self.globals['threads']['sendCommand'][dev.id]['thread'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"Device Stop: 'sendCommand' NOW STOPPED")
                self.globals['threads']['sendCommand'].pop(dev.id, None)  # Remove Thread

            if dev.id in self.globals['threads']['handleResponse'] and self.globals['threads']['handleResponse'][dev.id]['threadActive']:
                self.generalLogger.debug(u"Device Stop: 'handleResponse' BEING STOPPED")
                self.globals['threads']['handleResponse'][dev.id]['event'].set()  # Stop the Thread
                self.globals['queues']['responseFromCamera'][dev.id].put(['STOPTHREAD'])
                self.globals['threads']['handleResponse'][dev.id]['thread'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"Device Stop: 'handleResponse' NOW STOPPED")
                self.globals['threads']['handleResponse'].pop(dev.id, None)  # Remove Thread

            if 'commandToSend' in self.globals['queues']:
                self.globals['queues']['commandToSend'].pop(dev.id, None)  # Remove Queue

            if 'responseFromCamera' in self.globals['queues']:
                self.globals['queues']['responseFromCamera'].pop(dev.id, None)  # Remove Queue

            self.globals['cameras'].pop(dev.id, None)  # Remove Camera plugin internal storage

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.generalLogger.error(u"deviceStopComm: StandardError detected for '%s' at line '%s' = %s" % (dev.name, exc_tb.tb_lineno,  e))   


    def checkCameraEnabled(self, dev, pluginActionName):    
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        if dev == None:
            callingAction = inspect.stack()[1][3]
            self.generalLogger.error(u"Plugin Action '%s' [%s] ignored as no camera device defined." % (pluginActionName, callingAction))
            return False
        elif dev.enabled == False:
            callingAction = inspect.stack()[1][3]
            self.generalLogger.error(u"'%s'Plugin Action '%s' [%s] ignored as Camera '%s' is not enabled." % (pluginActionName, callingAction, dev.name))
            return False

        return True


    def actionControlSensor(self, action, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u'actionControlSensor: Action = %s' % action)
        self.generalLogger.debug(u'actionControlSensor: Dev = %s' % dev)

        if self.checkCameraEnabled(dev, action.sensorAction) == False: return

        ###### TURN ON ######
        if action.sensorAction == indigo.kSensorAction.TurnOn:
            self.motionDetectionOn(action, dev)            

        ###### TURN OFF ######
        elif action.sensorAction == indigo.kSensorAction.TurnOff:
            self.motionDetectionOff(action, dev)            

        ###### REQUEST STATUS ######
        elif  action.sensorAction == indigo.kSensorAction.RequestStatus:
            self.updateCameraStatus(action, dev)            

    def motionDetectionToggle(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kEnableMotionDetect, kToggle), params])

    def motionDetectionOn(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kEnableMotionDetect, kOn), params])


    def motionDetectionOff(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kEnableMotionDetect, kOff), params])


    def updateCameraStatus(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
            
        indigo.server.log(u'updateCameraStatus: pluginAction = %s' % pluginAction)

        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getDevState',), params])
        self.generalLogger.info(u'sent "%s" %s' % (dev.name, "request status"))

    def motionDetectionGet(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig',), params])

    def ringToggle(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kRing, kToggle), params])

    def ringON(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kRing, kOn), params])

    def ringOFF(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kRing, kOff), params])


    def snapToggle(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kSnapPicture, kToggle), params])


    def snapOn(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kSnapPicture, kOn), params])


    def snapOff(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kSnapPicture, kOff), params])


    def motionDetectionRecordToggle(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kMotionDetectionRecord, kToggle), params])


    def motionDetectionRecordOn(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kMotionDetectionRecord, kOn), params])


    def motionDetectionRecordOff(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getMotionDetectConfig', kMotionDetectionRecord, kOff), params])


    def scheduleRecordToggle(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getScheduleRecordConfig', kScheduleRecord, kToggle), params])


    def scheduleRecordOn(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getScheduleRecordConfig', kScheduleRecord, kOn), params])


    def scheduleRecordOff(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getScheduleRecordConfig', kScheduleRecord, kOff), params])


    def snap(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('snapPicture2',), params])

    def synchroniseCameraTime(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        self.globals['queues']['commandToSend'][dev.id].put(['camera', ('getSystemTime',), params])

    def experimental(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        pass

    def experimental1(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if self.checkCameraEnabled(dev, pluginAction.description) == False: return

        params = {}
        pass