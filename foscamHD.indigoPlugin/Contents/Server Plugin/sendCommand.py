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
import logging
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

class ThreadSendCommand(threading.Thread):

    def __init__(self, globals, devId, event):

        threading.Thread.__init__(self)

        self.globals = globals

        self.sendMonitorLogger = logging.getLogger("Plugin.MonitorSend")
        self.sendMonitorLogger.setLevel(self.globals['debug']['monitorSend'])

        self.sendDebugLogger = logging.getLogger("Plugin.DebugSend")
        self.sendDebugLogger.setLevel(self.globals['debug']['debugSend'])

        self.receiveMonitorLogger = logging.getLogger("Plugin.MonitorReceive")
        self.receiveMonitorLogger.setLevel(self.globals['debug']['monitorReceive'])

        self.receiveDebugLogger = logging.getLogger("Plugin.DebugReceive")
        self.receiveDebugLogger.setLevel(self.globals['debug']['debugReceive'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        self.threadStop = event

        self.cameraDevId = int(devId)  # Set Indigo Device id (for camera) to value passed in Thread invocation
        self.cameraAddress = indigo.devices[self.cameraDevId].address
        self.cameraName = indigo.devices[self.cameraDevId].name
        self.cameraIpAddressPort = self.globals['cameras'][self.cameraDevId]['ipAddressPort']

        self.globals['threads']['sendCommand'][self.cameraDevId]['threadActive'] = True

        self.sendDebugLogger.debug(u"Initialised 'Send Command' Thread for %s [%s]" % (self.cameraName, self.cameraAddress))  
  
    def run(self):

        try:
            self.methodTracer.threaddebug(u"ThreadSendCommand")

            sleep(kDelayStartSendCommand)  # Allow devices to start?

            self.sendDebugLogger.debug(u"'Send Command' Thread for %s [%s] initialised and now running" % (self.cameraName, self.cameraAddress))  

            while not self.threadStop.is_set():
                try:
                    if self.cameraDevId not in self.globals['queues']['commandToSend']:
                        self.sendDebugLogger.debug(u"'Send Command' Thread for %s [%s] - Queue misssing so thread being ended" % (self.cameraName, self.cameraAddress))  
                        break

                    commandToHandle = self.globals['queues']['commandToSend'][self.cameraDevId].get(True,5)

                    if commandToHandle[0] == 'STOPTHREAD':
                        continue  # self.threadStop should be set

                    # Check if monitoring / debug options have changed and if so set accordingly
                    if self.globals['debug']['previousMonitorSend'] != self.globals['debug']['monitorSend']:
                        self.globals['debug']['previousMonitorSend'] = self.globals['debug']['monitorSend']
                        self.sendMonitorLogger.setLevel(self.globals['debug']['monitorSend'])

                    if self.globals['debug']['previousDebugSend'] != self.globals['debug']['debugSend']:
                        self.globals['debug']['previousDebugSend'] = self.globals['debug']['debugSend']
                        self.sendDebugLogger.setLevel(self.globals['debug']['debugSend'])

                    if self.globals['debug']['previousMonitorReceive'] != self.globals['debug']['monitorReceive']:
                        self.globals['debug']['previousMonitorReceive'] = self.globals['debug']['monitorReceive']
                        self.receiveMonitorLogger.setLevel(self.globals['debug']['monitorReceive'])

                    if self.globals['debug']['previousDebugReceive'] != self.globals['debug']['debugReceive']:
                        self.globals['debug']['previousDebugReceive'] = self.globals['debug']['debugReceive']
                        self.receiveDebugLogger.setLevel(self.globals['debug']['debugReceive'])

                    if self.globals['debug']['previousDebugMethodTrace'] !=self.globals['debug']['debugMethodTrace']:
                        self.globals['debug']['previousDebugMethodTrace'] = self.globals['debug']['debugMethodTrace']
                        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

                    commandType = commandToHandle[0]  # commandType = 'camera' | 'internal'
                    commandTuple = commandToHandle[1]
                    command = commandTuple[0]
                    # Determine Camera platform and set command to process accordingly
                    if (command == 'getMotionDetectConfig' or command == 'setMotionDetectConfig') and self.globals['cameras'][self.cameraDevId]['cameraPlatform'] == kAmba:
                        command = command + '1'  
                    commandFunction = ''
                    commandOption = ''
                    if len(commandToHandle[1]) > 1:
                        commandFunction = commandToHandle[1][1]
                        commandOption = commandToHandle[1][2]
                    params = commandToHandle[2]

                    self.sendDebugLogger.debug(u"Command: %s [%s]" % (command, commandType))

                    # Reserved for future use
                    if commandType == 'internal':  # i.e. don't send to camera - just add it to the responseFromCamera queue to directly process it
                        # self.globals['queues']['responseFromCamera'][self.cameraDevId].put([command, params])
                        continue

                    # commandType = 'camera'
 
                    paramsExtracted = ''
                    for param in params:
                        paramsExtracted = paramsExtracted + '&%s=%s' % (param, params[param])

                    url = str('http://%s/cgi-bin/CGIProxy.fcgi?usr=%s&pwd=%s&cmd=%s%s' % (self.cameraIpAddressPort,
                                                                                               self.globals['cameras'][self.cameraDevId]['username'], 
                                                                                               self.globals['cameras'][self.cameraDevId]['password'], 
                                                                                               command, 
                                                                                               paramsExtracted))
                    urlHidden = str('http://%s/cgi-bin/CGIProxy.fcgi?usr=%s&pwd=%s&cmd=%s%s' % (self.cameraIpAddressPort,
                                                                                                     '<USERNAME>',
                                                                                                     '<PASSWORD>', 
                                                                                                     command,
                                                                                                     paramsExtracted))
                    self.sendMonitorLogger.debug(u"Command Sent To Camera %s [%s]: %s" % (self.cameraName, self.cameraAddress, urlHidden))

                    process = subprocess.Popen(['curl', '-H', 'Accept: application/xml', '-H', 'Content-Type: application/xml', '-X', 'GET', url], stdout=subprocess.PIPE)

                except Queue.Empty:
                    continue

                except StandardError, e:
                    self.sendDebugLogger.error(u"ThreadSendCommand detected internal error. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))
                    continue

                try:
                    responseFromCamera = ''
                    for line in iter(process.stdout.readline, ''):
                        responseFromCamera = responseFromCamera + line

                    resultOK = False
                    result   = -9  # Default to unspecified error
                    resultUi = 'Unspecified Error'

                    if len(responseFromCamera) > 40 and responseFromCamera[0:12] != '<CGI_Result>' and command == 'snapPicture2':
                        self.receiveDebugLogger.debug(u"Image received from camera %s [%s]" % (self.cameraName, self.cameraAddress)) 
                        resultOK = True
                        resultUi = 'Success'
                    else:
                        if len(responseFromCamera) == 0:
                            self.receiveDebugLogger.debug(u"No Response from camera %s [%s]" % (self.cameraName, self.cameraAddress))
                            indigo.devices[self.cameraDevId].setErrorStateOnServer(u"no ack") 
                        else:   
                            self.receiveDebugLogger.debug(u"%s" % (responseFromCamera))

                            # self.receiveDebugLogger.debug(u"Response from camera %s [%s]:\n%s" % (self.cameraName, self.cameraAddress, self.responseFromCamera))

                            if len(responseFromCamera) > 40:
                                if responseFromCamera[0:12] == '<CGI_Result>'  :
                                    result = responseFromCamera[0:50].split('<result>')
                                    if len(result) > 1:
                                        result = result[1].split('</result>')
                                        if len(result) > 1:
                                            result = result[0]
                                            if result == '0':
                                                resultOK = True
                                                resultUi = 'Success'
                                            else:
                                                resultOK = False
                                                if result == '-1':
                                                    resultUi = 'CGI format error'
                                                elif result == '-2':
                                                    resultUi = 'User/pswd error'
                                                elif result == '-3':
                                                    resultUi = 'Access deny'
                                                elif result == '-4':
                                                    resultUi = 'CGI execute fail'
                                                elif result == '-5':
                                                    resultUi = 'Timeout'
                                                elif result == '-6':
                                                    resultUi = 'Reserve'
                                                elif result == '-7':
                                                    resultUi = 'Unknown error'
                                                elif result == '-8':
                                                    resultUi = 'Reserve'
                                                else:
                                                    resultUi = str('Error %s' % result)

                                                indigo.devices[self.cameraDevId].setErrorStateOnServer(resultUi)

                            if resultOK == True:
                                if command == 'snapPicture2':
                                    self.receiveDebugLogger.debug(u"Image received from camera: %s [%s]" % (self.cameraName, self.cameraAddress))
                                else:    
                                    self.receiveDebugLogger.debug(u"Response received from camera: %s [%s] to '%s' =\n%s" % (self.cameraName, self.cameraAddress, command, responseFromCamera))
                                self.globals['queues']['responseFromCamera'][self.cameraDevId].put([commandTuple, responseFromCamera])
                            else:
                                self.receiveDebugLogger.error(u"'responseFromCamera' Error %s:%s [%s:%s]" % (str(result), resultUi, str(len(responseFromCamera)), responseFromCamera)) 
                              

                except StandardError, e:
                    self.receiveDebugLogger.error(u"ThreadSendCommand detected internal error. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   
        except StandardError, e:
            self.sendDebugLogger.error(u"ThreadSendCommand detected error. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   

        self.sendDebugLogger.debug(u"ThreadSendCommand ended for camera: %s [%s]" % (self.cameraName, self.cameraAddress))  

        self.globals['threads']['sendCommand'][self.cameraDevId]['threadActive'] = False


