#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2019-2023
# Requires Indigo 2022.1+
#

# ============================== Native Imports ===============================
import sys
import threading
from time import sleep
import traceback

# ============================== Custom Imports ===============================
from constants import *
try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass



class ThreadPolling(threading.Thread):

    def __init__(self, plugin_globals, devId, event):

        threading.Thread.__init__(self)

        self.globals = plugin_globals

        self.pollingLogger = logging.getLogger("Plugin.polling")
 
        self.threadStop = event

        self.cameraDevId = int(devId)  # Set Indigo Device id (for camera) to value passed in Thread invocation
        self.cameraDev = indigo.devices[self.cameraDevId]
        self.cameraAddress = self.cameraDev.address
        self.cameraName = self.cameraDev.name

        self.previousPollingSeconds = self.globals[POLLING][self.cameraDevId][SECONDS]

        self.globals[THREADS][POLL_CAMERA][self.cameraDevId][THREAD_ACTIVE] = True

        self.pollingLogger.info(f"Initialised 'ThreadPolling' Thread for {self.cameraName} [{self.cameraAddress}] to poll at {self.globals[POLLING][self.cameraDevId][SECONDS]} second intervals")

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]  # noqa [Ignore duplicate code warning]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method}'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.pollingLogger.error(log_message)

    def run(self):

        try:  
            sleep(DELAY_START_POLLING)  # Allow devices to start?

            self.pollingLogger.debug(f"'Polling' Thread for {self.cameraName} [{self.cameraAddress}] initialised and now running")

            params = {}
            self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ('getDevState',), params])

            self.pollingLogger.debug(f"'{self.cameraName}' [{self.cameraAddress}] Polling thread NOW running and command queued")

            while not self.threadStop.wait(float(self.globals[POLLING][self.cameraDevId][SECONDS])):
                # Check if polling seconds interval has changed and if so set accordingly
                if self.globals[POLLING][self.cameraDevId][SECONDS] != self.previousPollingSeconds:
                    self.pollingLogger.info(f"'{self.cameraName}' [{self.cameraAddress}] Changing to poll at {self.globals[POLLING][self.cameraDevId][SECONDS]:0.2f} second intervals"
                                            f" (was {self.previousPollingSeconds:d} seconds)")
                    self.previousPollingSeconds = self.globals[POLLING][self.cameraDevId][SECONDS]

                self.pollingLogger.debug(f"'{self.cameraName}' [{self.cameraAddress}] Start of While Loop ...")

                if self.threadStop.isSet():  # Check if polling thread to end and if so break out of while loop
                    break

                params = dict()
                self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CAMERA, ('getDevState',), params])

            self.pollingLogger.debug(f"Polling thread for camera {self.cameraName} [{self.cameraAddress}] ending")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        self.pollingLogger.debug(f"Polling Thread for camera {self.cameraName} [{self.cameraAddress}] ended.")
 
        self.globals[THREADS][POLL_CAMERA][self.cameraDevId][THREAD_ACTIVE] = False
