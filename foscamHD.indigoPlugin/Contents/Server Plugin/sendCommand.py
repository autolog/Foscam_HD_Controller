#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2019-2023
# Requires Indigo 2022.1+
#

# ============================== Native Imports ===============================
import queue
import subprocess
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


class ThreadSendCommand(threading.Thread):

    def __init__(self, plugin_globals, devId, event):

        threading.Thread.__init__(self)

        self.globals = plugin_globals

        self.sendCommandLogger = logging.getLogger("Plugin.Send")

        self.sendCommandLogger.debug("Initialising Foscam HD Controller Send Command Thread")

        self.threadStop = event

        self.cameraDevId = int(devId)  # Set Indigo Device id (for camera) to value passed in Thread invocation
        self.cameraAddress = indigo.devices[self.cameraDevId].address
        self.cameraName = indigo.devices[self.cameraDevId].name
        self.cameraIpAddressPort = self.globals[CAMERAS][self.cameraDevId][IP_ADDRESS_PORT]

        self.globals[THREADS][SEND_COMMAND][self.cameraDevId][THREAD_ACTIVE] = True

        self.sendCommandLogger.debug(f"Initialised 'Send Command' Thread for {self.cameraName} [{self.cameraAddress}]")
  
    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]  # noqa [Ignore duplicate code warning]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method} [{self.globals[PLUGIN_INFO][PLUGIN_VERSION]}]'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.sendCommandLogger.error(log_message)

    def run(self):

        try:
            sleep(DELAY_START_SEND_COMMAND)  # Allow devices to start?

            self.sendCommandLogger.debug(f"'Send Command' Thread for {self.cameraName} [{self.cameraAddress}] initialised and now running")

            while not self.threadStop.is_set():
                try:
                    if self.cameraDevId not in self.globals[QUEUES][COMMAND_TO_SEND]:
                        self.sendCommandLogger.debug(f"'Send Command' Thread for {self.cameraName} [{self.cameraAddress}] - Queue missing so thread being ended")
                        break

                    commandToHandle = self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].get(True, 5)

                    if commandToHandle[0] == CameraResponse.STOP_THREAD:
                        continue  # self.threadStop should be set

                    commandType = commandToHandle[0]  # commandType = CAMERA | INTERNAL
                    commandTuple = commandToHandle[1]
                    command = commandTuple[0]
                    # Determine Camera platform and set command to process accordingly
                    if (command == "getMotionDetectConfig" or command == "setMotionDetectConfig") and self.globals[CAMERAS][self.cameraDevId][CAMERA_PLATFORM] == CAMERA_PLATFORM_AMBA:
                        command = command + '1'  
                    commandFunction = ''
                    commandOption = ''
                    if len(commandToHandle[1]) > 1:
                        commandFunction = commandToHandle[1][1]
                        commandOption = commandToHandle[1][2]
                    params = commandToHandle[2]

                    self.sendCommandLogger.debug(f"Command: {command} [{commandType}]")

                    if commandType == INTERNAL:  # i.e. don't send to camera - just add it to the responseFromCamera queue to directly process it
                        self.globals[QUEUES][RESPONSE_FROM_CAMERA][self.cameraDevId].put([(command,), params])
                        continue

                    # commandType = CAMERA
 
                    paramsExtracted = ''
                    for param in params:
                        paramsExtracted = paramsExtracted + f'&{param}={params[param]}'

                    # url (not urlHidden) is only used for developer debugging!
                    url = f"http://{self.cameraIpAddressPort}/cgi-bin/CGIProxy.fcgi?usr={self.globals[CAMERAS][self.cameraDevId][USERNAME]}&pwd={self.globals[CAMERAS][self.cameraDevId][PASSWORD]}&cmd={command}{paramsExtracted}"
                    urlHidden = f"http://{self.cameraIpAddressPort}/cgi-bin/CGIProxy.fcgi?usr=<USERNAME>&pwd=<PASSWORD>&cmd={command}{paramsExtracted}"
                    self.sendCommandLogger.debug(f"Command Sent To Camera {self.cameraName} [{self.cameraAddress}]: {urlHidden}")
                    # TODO - Change to Requests?
                    process = subprocess.Popen(['curl', '-H', 'Accept: application/xml', '-H', 'Content-Type: application/xml', '-X', 'GET', url], stdout=subprocess.PIPE)  # TODO = Change to Requests

                except queue.Empty:
                    continue

                except Exception as exception_error:
                    self.exception_handler(exception_error, True)  # Log error and display failing statement
                    continue

                try:
                    responseFromCamera = ''
                    for line_bytes in iter(process.stdout.readline, ''):
                        if line_bytes == b"":
                            break
                        line_str = line_bytes.decode("utf-8")
                        responseFromCamera = responseFromCamera + line_str

                    resultOK = False
                    result   = -9  # Default to unspecified error
                    resultUi = "Unspecified Error"

                    if len(responseFromCamera) > 40 and responseFromCamera[0:12] != "<CGI_Result>" and command == "snapPicture2":
                        self.sendCommandLogger.debug(f"Image received from camera {self.cameraName} [{self.cameraAddress}]")
                        resultOK = True
                        resultUi = "Success"
                    else:
                        if len(responseFromCamera) == 0:
                            self.sendCommandLogger.debug(f"No Response from camera {self.cameraName} [{self.cameraAddress}]")
                            indigo.devices[self.cameraDevId].setErrorStateOnServer("no ack")
                        else:   
                            self.sendCommandLogger.debug(f"{responseFromCamera}")

                            # self.sendCommandLogger.debug(f"Response from camera {self.cameraName} [{self.cameraAddress}]:\n{self.responseFromCamera}")

                            if len(responseFromCamera) > 40:
                                if responseFromCamera[0:12] == "<CGI_Result>":
                                    result = responseFromCamera[0:50].split("<result>")
                                    if len(result) > 1:
                                        result = result[1].split("</result>")
                                        if len(result) > 1:
                                            result = result[0]
                                            if result == "0":
                                                resultOK = True
                                                resultUi = "Success"
                                            else:
                                                resultOK = False
                                                if result == "-1":
                                                    resultUi = "CGI format error"
                                                elif result == "-2":
                                                    resultUi = "User/pswd error"
                                                elif result == "-3":
                                                    resultUi = "Access deny"
                                                elif result == "-4":
                                                    resultUi = "CGI execute fail"
                                                elif result == "-5":
                                                    resultUi = "Timeout"
                                                elif result == "-6":
                                                    resultUi = "Reserve"
                                                elif result == "-7":
                                                    resultUi = "Unknown error"
                                                elif result == "-8":
                                                    resultUi = "Reserve"
                                                else:
                                                    resultUi = f"Error {result}"

                                                indigo.devices[self.cameraDevId].setErrorStateOnServer(resultUi)

                            if resultOK:
                                if command == "snapPicture2":
                                    self.sendCommandLogger.debug(f"Image received from camera: {self.cameraName} [{self.cameraAddress}]")
                                else:    
                                    self.sendCommandLogger.debug(f"Response received from camera: {self.cameraName} [{self.cameraAddress}] to '{command}' =\n{responseFromCamera}")
                                self.globals[QUEUES][RESPONSE_FROM_CAMERA][self.cameraDevId].put([commandTuple, responseFromCamera])
                            else:
                                self.sendCommandLogger.error(f"Response received from camera: {self.cameraName} [{self.cameraAddress}],"
                                                             f" Error {str(result)}:{resultUi} [{str(len(responseFromCamera))}:{responseFromCamera}]")
                except Exception as exception_error:
                    self.exception_handler(exception_error, True)  # Log error and display failing statement

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        self.sendCommandLogger.debug(f"ThreadSendCommand ended for camera: {self.cameraName} [{self.cameraAddress}]")

        self.globals[THREADS][SEND_COMMAND][self.cameraDevId][THREAD_ACTIVE] = False


