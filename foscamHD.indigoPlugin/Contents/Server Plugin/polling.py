#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2016-2017
# Requires Indigo 7
#

try:
    import indigo
except ImportError:
    pass
import logging
import sys
import threading

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from constants import *

class ThreadPolling(threading.Thread):

    def __init__(self, globals, devId, event):

        threading.Thread.__init__(self)

        self.globals = globals

        self.pollingLogger = logging.getLogger("Plugin.polling")
        self.pollingLogger.setLevel(self.globals['debug']['debugPolling'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        self.threadStop = event

        self.cameraDevId = int(devId)  # Set Indigo Device id (for camera) to value passed in Thread invocation

        self.cameraDev = indigo.devices[self.cameraDevId]

        self.cameraAddress = self.cameraDev.address
        self.cameraName = self.cameraDev.name

        self.previousPollingSeconds = self.globals['polling'][self.cameraDevId]['seconds']

        self.globals['threads']['pollCamera'][self.cameraDevId]['threadActive'] = True

        self.pollingLogger.info(u"'%s' [%s] has been initialised to poll at %i second intervals" % (self.cameraName, self.cameraAddress, self.globals['polling'][self.cameraDevId]['seconds']))  

    def run(self):
        try:  
            self.methodTracer.threaddebug(u"ThreadPolling")

            self.pollingLogger.debug(u"'%s' [%s] Polling thread NOW running" % (self.cameraName, str(self.cameraDevId)))

            params = {}
            self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', 'getDevState', params])

            self.pollingLogger.debug(u"'%s' [%s] Polling thread NOW running and command queued" % (self.cameraName, self.cameraAddress))

            while not self.threadStop.wait(float(self.globals['polling'][self.cameraDevId]['seconds'])):

                # Check if monitoring / debug options have changed and if so set accordingly
                if self.globals['debug']['previousDebugPolling'] != self.globals['debug']['debugPolling']:
                    self.globals['debug']['previousDebugPolling'] = self.globals['debug']['debugPolling']
                    self.pollingLogger.setLevel(self.globals['debug']['debugPolling'])
                if self.globals['debug']['previousDebugMethodTrace'] !=self.globals['debug']['debugMethodTrace']:
                    self.globals['debug']['previousDebugMethodTrace'] = self.globals['debug']['debugMethodTrace']
                    self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

                # Check if polling seconds interval has changed and if so set accordingly
                if self.globals['polling'][self.cameraDevId]['seconds'] != self.previousPollingSeconds:
                    self.pollingLogger.info(u"'%s' [%s] Changing to poll at %i second intervals (was %i seconds)" % (self.cameraName, self.cameraAddress, self.globals['polling'][self.cameraDevId]['seconds'], self.previousPollingSeconds))  
                    self.previousPollingSeconds = self.globals['polling'][self.cameraDevId]['seconds']

                self.pollingLogger.debug(u"'%s' [%s] Start of While Loop ..." % (self.cameraName, self.cameraAddress))

                if self.threadStop.isSet():  # Check if polling thread to end and if so break out of while loop
                    break

                params = {}
                self.globals['queues']['commandToSend'][self.cameraDevId].put(['camera', 'getDevState', params])

            self.pollingLogger.debug(u"Polling thread for camera %s [%s] ending" % (self.cameraName, self.cameraAddress)) 

        except Exception, e:
            self.pollingLogger.error(u"Polling Thread for camera %s [%s] encountered an error at line %s: %s" % (self.cameraName, self.cameraAddress, sys.exc_traceback.tb_lineno, e))   

        self.pollingLogger.debug(u"Polling Thread for camera %s [%s] ended." % (self.cameraName, self.cameraAddress))    
 
        self.globals['threads']['pollCamera'][self.cameraDevId]['threadActive'] = False

