#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2019-2023
# Requires Indigo 2022.1+
#

# ============================== Native Imports ===============================
import inspect
import os
import platform
import queue
import sys
import threading
import traceback

# try:
#     import xml.etree.cElementTree as ET
# except ImportError:
#     import xml.etree.ElementTree as ET

# ============================== Custom Imports ===============================
try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass
from constants import *
from polling import ThreadPolling
from sendCommand import ThreadSendCommand
from responseFromCamera import ThreadResponseFromCamera


class Plugin(indigo.PluginBase):

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super(Plugin, self).__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)

        logging.addLevelName(LOG_LEVEL_CAMERA, "camera")

        def topic(self, message, *args, **kws):  # noqa [Shadowing names from outer scope = self]
            # if self.isEnabledFor(K_LOG_LEVEL_TOPIC):
            # Yes, logger takes its '*args' as 'args'.
            self.log(LOG_LEVEL_CAMERA, message, *args, **kws)

        logging.Logger.topic = topic

        # Initialise dictionary to store plugin Globals
        self.globals = dict()

        # Initialise Indigo plugin info
        self.globals[PLUGIN_INFO] = dict()
        self.globals[PLUGIN_INFO][PLUGIN_ID] = plugin_id
        self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME] = plugin_display_name
        self.globals[PLUGIN_INFO][PLUGIN_VERSION] = plugin_version
        self.globals[PLUGIN_INFO][PATH] = indigo.server.getInstallFolderPath()
        self.globals[PLUGIN_INFO][API_VERSION] = indigo.server.apiVersion
        self.globals[PLUGIN_INFO][ADDRESS] = indigo.server.address

        log_format = logging.Formatter("%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.plugin_file_handler.setFormatter(log_format)
        self.plugin_file_handler.setLevel(LOG_LEVEL_INFO)  # Logging Level for plugin log file
        self.indigo_log_handler.setLevel(LOG_LEVEL_INFO)  # Logging level for Indigo Event Log

        self.logger = logging.getLogger("Plugin.Foscam")

        # Initialise dictionary to store internal details about cameras
        self.globals[CAMERAS] = dict()

        # Initialise dictionary for polling thread
        self.globals[POLLING] = dict()

        self.globals[TEST_SYM_LINK] = False

        self.validate_prefs_config_ui(plugin_prefs)  # Validate the Plugin Config before plugin initialisation

        # Set Plugin Config Values
        self.closed_prefs_config_ui(plugin_prefs, False)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    def display_plugin_information(self):
        try:
            def plugin_information_message():
                startup_message_ui = "Plugin Information:\n"
                startup_message_ui += f"{'':={'^'}80}\n"
                startup_message_ui += f"{'Plugin Name:':<30} {self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME]}\n"
                startup_message_ui += f"{'Plugin Version:':<30} {self.globals[PLUGIN_INFO][PLUGIN_VERSION]}\n"
                startup_message_ui += f"{'Plugin ID:':<30} {self.globals[PLUGIN_INFO][PLUGIN_ID]}\n"
                startup_message_ui += f"{'Indigo Version:':<30} {indigo.server.version}\n"
                startup_message_ui += f"{'Indigo License:':<30} {indigo.server.licenseStatus}\n"
                startup_message_ui += f"{'Indigo API Version:':<30} {indigo.server.apiVersion}\n"
                startup_message_ui += f"{'Indigo Reflector URL:':<30} {indigo.server.getReflectorURL()}\n"
                startup_message_ui += f"{'Indigo WebServer URL:':<30} {indigo.server.getWebServerURL()}\n"
                startup_message_ui += f"{'Architecture:':<30} {platform.machine()}\n"
                startup_message_ui += f"{'Python Version:':<30} {sys.version.split(' ')[0]}\n"
                startup_message_ui += f"{'Mac OS Version:':<30} {platform.mac_ver()[0]}\n"
                startup_message_ui += f"{'Plugin Process ID:':<30} {os.getpid()}\n"
                startup_message_ui += f"{'':={'^'}80}\n"
                return startup_message_ui

            self.logger.info(plugin_information_message())

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split("/")
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method} [{self.globals[PLUGIN_INFO][PLUGIN_VERSION]}]'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.logger.error(log_message)

    def startup(self):

        self.globals[QUEUES] = dict()
        self.globals[QUEUES][COMMAND_TO_SEND] = dict()  # There will be one COMMAND_TO_SEND queue for each camera - set-up in camera device start
        self.globals[QUEUES][RESPONSE_FROM_CAMERA] = dict()  # There will be one RESPONSE_FROM_CAMERA queue for each camera - set-up in camera device start

        indigo.devices.subscribeToChanges()

        self.globals[THREADS] = dict()
        self.globals[THREADS][SEND_COMMAND] = dict()  # One thread per camera
        self.globals[THREADS][HANDLE_RESPONSE] = dict()  # One thread per camera
        self.globals[THREADS][POLL_CAMERA] = dict()  # One thread per camera
        self.globals[THREADS][MOTION_TIMER] = dict()  # One thread per camera

        self.logger.info("Autolog 'Foscam HD Controller' initialization complete")

    def shutdown(self):

        self.logger.info("Autolog 'Foscam HD Controller' Plugin shutdown complete")

    # noinspection PyMethodMayBeStatic
    def validate_prefs_config_ui(self, valuesDict):

        return True

    def closedPrefsConfigUi(self, values_dict=None, user_cancelled=False):
        try:
            if user_cancelled:
                return

            # Get required Event Log and Plugin Log logging levels
            plugin_log_level = int(values_dict.get("pluginLogLevel", LOG_LEVEL_INFO))
            event_log_level = int(values_dict.get("eventLogLevel", LOG_LEVEL_INFO))

            # Ensure following logging level messages are output
            self.indigo_log_handler.setLevel(LOG_LEVEL_INFO)
            self.plugin_file_handler.setLevel(LOG_LEVEL_INFO)

            # Output required logging levels and TP Message Monitoring requirement to logs
            self.logger.info(f"Logging to Indigo Event Log at the '{LOG_LEVEL_TRANSLATION[event_log_level]}' level")
            self.logger.info(f"Logging to Plugin Event Log at the '{LOG_LEVEL_TRANSLATION[plugin_log_level]}' level")

            # Now set required logging levels
            self.indigo_log_handler.setLevel(event_log_level)
            self.plugin_file_handler.setLevel(plugin_log_level)

            # Set Camera Message Filter
            self.globals[CAMERA_FILTERS] = list()  # noqa - List is OK - Initialise Camera filters dictionary
            camera_message_filter = values_dict.get("cameraDeviceMessageFilter", [0])
            log_message = "Camera Filtering active for the following Foscam Camera device(s):"  # Not used if no logging required
            filtering_required = False

            spaces = " " * 35  # used to pad log messages

            # if len(camera_message_filter) == 0:
            #     self.globals[CAMERA_FILTERS] = ["dev-none"]
            # else:
            #     for entry_dev_id in camera_message_filter:
            #         entry_dev_id = int(entry_dev_id)
            #         if entry_dev_id == 0:  # Ignore '-- Don't Log Any Devices --'
            #             self.globals[CAMERA_FILTERS] = ["dev-none"]
            #             break
            #         elif entry_dev_id == 1:  # Ignore '-- Log All Devices --'
            #             self.globals[CAMERA_FILTERS] = ["dev-all"]
            #             log_message = f"{log_message}\n{spaces}All Foscam Camera Devices"
            #             filtering_required = True
            #             break
            #         else:
            #             pass
            #             export_device_name_ui = f"{indigo.devices[int(entry_dev_id)].name}"
            #             self.globals[CAMERA_FILTERS].append(f"dev-{entry_dev_id}")
            #             spaces = " " * 24
            #             log_message = f"{log_message}\n{spaces}Exported Indigo Device: '{export_device_name_ui}'"
            #             filtering_required = True
            # 
            # if filtering_required:
            #     self.logger.warning(f"{log_message}\n")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
            return True

    def runConcurrentThread(self):
        # This thread is used to detect plugin close down only

        try:
            try:
                while True:
                    self.sleep(60)  # in seconds
            except self.StopThread:
                self.logger.info("Autolog 'Foscam HD Controller' Plugin shutdown requested")
    
                self.logger.debug("runConcurrentThread being ended . . .")
                for self.cameraDevId in self.globals[THREADS][MOTION_TIMER]:
                    self.globals[THREADS][MOTION_TIMER][self.cameraDevId].cancel()
    
                for self.cameraDevId in self.globals[THREADS][POLL_CAMERA]:
                    if self.globals[THREADS][POLL_CAMERA][self.cameraDevId][THREAD_ACTIVE]:
                        self.logger.debug(f"{indigo.devices[self.cameraDevId].name} 'polling camera' BEING STOPPED")
                        self.globals[THREADS][POLL_CAMERA][self.cameraDevId][EVENT].set()  # Stop the Thread
    
                for self.cameraDevId in self.globals[THREADS][SEND_COMMAND]:
                    if self.globals[THREADS][SEND_COMMAND][self.cameraDevId][THREAD_ACTIVE]:
                        self.logger.debug("'sendCommand' BEING STOPPED")
                        self.globals[THREADS][SEND_COMMAND][self.cameraDevId][EVENT].set()  # Stop the Thread
                        self.globals[QUEUES][COMMAND_TO_SEND][self.cameraDevId].put([CameraResponse.STOP_THREAD])
    
                for self.cameraDevId in self.globals[THREADS][HANDLE_RESPONSE]:
                    if self.globals[THREADS][HANDLE_RESPONSE][self.cameraDevId][THREAD_ACTIVE]:
                        self.logger.debug("'handleResponse' BEING STOPPED")
                        self.globals[THREADS][HANDLE_RESPONSE][self.cameraDevId][EVENT].set()  # Stop the Thread
                        self.globals[QUEUES][RESPONSE_FROM_CAMERA][self.cameraDevId].put([CameraResponse.STOP_THREAD])
    
                for self.cameraDevId in self.globals[THREADS][POLL_CAMERA]:
                    if self.globals[THREADS][POLL_CAMERA][self.cameraDevId][THREAD_ACTIVE]:
                        self.globals[THREADS][POLL_CAMERA][self.cameraDevId][THREAD].join(7.0)  # wait for thread to end
                        self.logger.debug(f"{indigo.devices[self.cameraDevId].name} 'polling camera' NOW STOPPED")
    
                for self.cameraDevId in self.globals[THREADS][SEND_COMMAND]:
                    if self.globals[THREADS][SEND_COMMAND][self.cameraDevId][THREAD_ACTIVE]:
                        self.globals[THREADS][SEND_COMMAND][self.cameraDevId][THREAD].join(7.0)  # wait for thread to end
                        self.logger.debug("'sendCommand' NOW STOPPED")
    
                for self.cameraDevId in self.globals[THREADS][HANDLE_RESPONSE]:
                    if self.globals[THREADS][HANDLE_RESPONSE][self.cameraDevId][THREAD_ACTIVE]:
                        self.globals[THREADS][HANDLE_RESPONSE][self.cameraDevId][THREAD].join(7.0)  # wait for thread to end
                        self.logger.debug("'handleResponse' NOW STOPPED")
    
            self.logger.debug(". . . runConcurrentThread now ended")
        
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
            return True

    def deviceStartComm(self, dev):
        try:
            dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used
            
            self.globals[CAMERAS][dev.id] = dict()

            self.globals[CAMERAS][dev.id][DATETIME_STARTED] = indigo.server.getTime()
            self.globals[CAMERAS][dev.id][IP_ADDRESS] = dev.pluginProps.get("ipaddress", "unknown")
            self.globals[CAMERAS][dev.id][PORT] = dev.pluginProps["port"]
            self.globals[CAMERAS][dev.id][USERNAME] = dev.pluginProps["username"]
            self.globals[CAMERAS][dev.id][PASSWORD] = dev.pluginProps["password"]
            self.globals[CAMERAS][dev.id][IP_ADDRESS_PORT] = dev.pluginProps["ipaddress"] + ":" + dev.pluginProps["port"]
            self.globals[CAMERAS][dev.id][IP_ADDRESS_PORT_NAME] = (self.globals[CAMERAS][dev.id][IP_ADDRESS_PORT].replace(".", "-")).replace(":", "-")
            self.globals[CAMERAS][dev.id][FTP_PROCESS_MODE] = int(dev.pluginProps.get("ftpProcessMode", 0))
            self.globals[CAMERAS][dev.id][FTP_PORT] = int(dev.pluginProps.get("ftport", 50021))
            self.globals[CAMERAS][dev.id][FTP_CAMERA_FOLDER] = dev.pluginProps.get("ftpCameraFolder", "")
            self.globals[CAMERAS][dev.id][ROOT_FOLDER] = dev.pluginProps.get("rootFolder", "~/Documents")
            self.globals[CAMERAS][dev.id][CAMERA_FOLDER] = dev.pluginProps.get("cameraFolder", "")
            self.globals[CAMERAS][dev.id][ENABLE_AUTO_TIME_SYNC] = dev.pluginProps.get('enableAutoTimeSync', True)

            self.globals[CAMERAS][dev.id][CAMERA_PLATFORM] = int(dev.pluginProps.get("cameraPlatform", CAMERA_PLATFORM_ORIGINAL))
            self.globals[CAMERAS][dev.id][STATUS] = "starting"
            self.globals[CAMERAS][dev.id][MOTION] = dict()
            self.globals[CAMERAS][dev.id][MOTION][SET_MOTION_DETECT_CONFIG_FUNCTION] = NOT_SET  # kNotSet, kEnableMotionDetect, kRing, kSnapPicture
            self.globals[CAMERAS][dev.id][MOTION][SET_MOTION_DETECT_CONFIG_OPTION] = NOT_SET  # kNotSet, kOn, kOff, kToggle
            # self.globals[CAMERAS][dev.id][MOTION][DETECTION_ENABLED] = False
            self.globals[CAMERAS][dev.id][MOTION][PREVIOUSLY_DETECTED] = False
            self.globals[CAMERAS][dev.id][MOTION][DETECTION_INTERVAL] = float(dev.pluginProps.get("motionDetectionInterval", 30.0))
            try:
                dynamic_view = int(dev.pluginProps.get("dynamicView", 0))
            except ValueError:
                dynamic_view = 0
            self.globals[CAMERAS][dev.id][MOTION][DYNAMIC_VIEW] = dynamic_view
            self.globals[CAMERAS][dev.id][MOTION][TIMER_ACTIVE] = False

            self.globals[CAMERAS][dev.id][MOTION][RING_ENABLED] = False
            self.globals[CAMERAS][dev.id][MOTION][SNAP_ENABLED] = False

            self.globals[CAMERAS][dev.id][MOTION][LAST_ALERT_FILE_TIME] = 0
            self.globals[CAMERAS][dev.id][MOTION][IMAGES] = list()  # List of alarm images
            self.globals[CAMERAS][dev.id][MOTION][IMAGE_NUMBER] = 0
            self.globals[CAMERAS][dev.id][MOTION][IMAGE_FILE] = ""
            self.globals[CAMERAS][dev.id][MOTION][IMAGE_FILE_PREVIOUS] = ""
            self.globals[CAMERAS][dev.id][MOTION][IMAGE_FOLDER_LIST] = list()
            self.globals[CAMERAS][dev.id][MOTION][IMAGE_FOLDER] = ""
            self.globals[CAMERAS][dev.id][MOTION][IMAGE_FOLDER_PREVIOUS] = ""
            self.globals[CAMERAS][dev.id][MOTION][DAYS] = list()
            self.globals[CAMERAS][dev.id][MOTION][LAST_DISPLAYED_IMAGE_HALF_HOUR] = ""
            self.globals[CAMERAS][dev.id][MOTION][LAST_DISPLAYED_IMAGE_DAY] = ""
            self.globals[CAMERAS][dev.id][MOTION][LAST_DISPLAYED_IMAGE_SELECTED] = ""

            updatePropsRequired = False
            dev_plugin_props = dev.pluginProps
            if "address" not in dev_plugin_props or dev_plugin_props["address"] != self.globals[CAMERAS][dev.id][IP_ADDRESS_PORT]:
                dev_plugin_props["address"] = self.globals[CAMERAS][dev.id][IP_ADDRESS_PORT]
                updatePropsRequired = True
            if 'AllowOnStateChange' not in dev_plugin_props or dev_plugin_props["AllowOnStateChange"] is not True:
                dev_plugin_props["AllowOnStateChange"] = True
                updatePropsRequired = True
            if updatePropsRequired:
                self.logger.debug(f"Updating props and restarting device {indigo.devices[dev.id].name} ...")
                dev.replacePluginPropsOnServer(dev_plugin_props)
                return

            if COMMAND_TO_SEND in self.globals[QUEUES]:
                if dev.id in self.globals[QUEUES][COMMAND_TO_SEND]:
                    with self.globals[QUEUES][COMMAND_TO_SEND][dev.id].mutex:
                        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].queue.clear()  # clear existing COMMAND_TO_SEND queue for camera
                else:
                    self.globals[QUEUES][COMMAND_TO_SEND][dev.id] = queue.Queue()  # set-up COMMAND_TO_SEND queue for camera

            if RESPONSE_FROM_CAMERA in self.globals[QUEUES]:
                if dev.id in self.globals[QUEUES][RESPONSE_FROM_CAMERA]:
                    with self.globals[QUEUES][RESPONSE_FROM_CAMERA][dev.id].mutex:
                        self.globals[QUEUES][RESPONSE_FROM_CAMERA][dev.id].queue.clear()  # clear existing RESPONSE_FROM_CAMERA  queue for camera
                else:
                    self.globals[QUEUES][RESPONSE_FROM_CAMERA][dev.id] = queue.Queue()  # set-up RESPONSE_FROM_CAMERA queue for  camera

            if dev.id in self.globals[THREADS][SEND_COMMAND] and self.globals[THREADS][SEND_COMMAND][dev.id][THREAD_ACTIVE]:
                self.logger.debug("'sendCommand' BEING STOPPED")
                self.globals[THREADS][SEND_COMMAND][dev.id][EVENT].set()  # Stop the Thread
                self.globals[THREADS][SEND_COMMAND][dev.id][THREAD].join(7.0)  # wait for thread to end
                self.logger.debug("'sendCommand' NOW STOPPED")

            self.globals[THREADS][SEND_COMMAND][dev.id] = dict()
            self.globals[THREADS][SEND_COMMAND][dev.id][THREAD_ACTIVE] = False
            self.globals[THREADS][SEND_COMMAND][dev.id][EVENT] = threading.Event()
            self.globals[THREADS][SEND_COMMAND][dev.id][THREAD] = ThreadSendCommand(self.globals, dev.id, self.globals[THREADS][SEND_COMMAND][dev.id][EVENT])
            self.globals[THREADS][SEND_COMMAND][dev.id][THREAD].start()

            if dev.id in self.globals[THREADS][HANDLE_RESPONSE] and self.globals[THREADS][HANDLE_RESPONSE][dev.id][THREAD_ACTIVE]:
                self.logger.debug("'handleResponse' BEING STOPPED")
                self.globals[THREADS][HANDLE_RESPONSE][dev.id][EVENT].set()  # Stop the Thread
                self.globals[THREADS][HANDLE_RESPONSE][dev.id][THREAD].join(7.0)  # wait for thread to end
                self.logger.debug("'handleResponse' NOW STOPPED")

            self.globals[THREADS][HANDLE_RESPONSE][dev.id] = dict()
            self.globals[THREADS][HANDLE_RESPONSE][dev.id][THREAD_ACTIVE] = False
            self.globals[THREADS][HANDLE_RESPONSE][dev.id][EVENT] = threading.Event()
            self.globals[THREADS][HANDLE_RESPONSE][dev.id][THREAD] = ThreadResponseFromCamera(self.globals, dev.id, self.globals[THREADS][HANDLE_RESPONSE][dev.id][EVENT])
            self.globals[THREADS][HANDLE_RESPONSE][dev.id][THREAD].start()

            if dev.id in self.globals[THREADS][POLL_CAMERA] and self.globals[THREADS][POLL_CAMERA][dev.id][THREAD_ACTIVE]:
                self.logger.debug(f"{indigo.devices[dev.id].name} 'polling camera' BEING STOPPED")
                self.globals[THREADS][POLL_CAMERA][dev.id][EVENT].set()  # Stop the Thread
                self.globals[THREADS][POLL_CAMERA][dev.id][THREAD].join(7.0)  # wait for thread to end
                self.logger.debug(f"{indigo.devices[dev.id].name} 'polling camera' NOW STOPPED")

            if dev_plugin_props["statusPolling"]:
                self.globals[POLLING][dev.id] = dict()
                self.globals[POLLING][dev.id][STATUS] = True
                self.globals[POLLING][dev.id][SECONDS] = float(dev_plugin_props["pollingSeconds"])

                self.globals[THREADS][POLL_CAMERA][dev.id] = dict()
                self.globals[THREADS][POLL_CAMERA][dev.id][THREAD_ACTIVE] = False
                self.globals[THREADS][POLL_CAMERA][dev.id][EVENT] = threading.Event()
                self.globals[THREADS][POLL_CAMERA][dev.id][THREAD] = ThreadPolling(self.globals, dev.id, self.globals[THREADS][POLL_CAMERA][dev.id][EVENT])
                self.globals[THREADS][POLL_CAMERA][dev.id][THREAD].start()

            keyValueList = [
                dict(key="motionDetectionEnabled", value=False),
                dict(key="motionDetected", value=False),
                dict(key="onOffState", value=False)
            ]
            dev.updateStatesOnServer(keyValueList)
            dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            indigo.devices[dev.id].setErrorStateOnServer("no ack")  # default to "no ack" at device startup - will be corrected when communication established

            if self.globals[CAMERAS][dev.id][ENABLE_AUTO_TIME_SYNC]:
                params = dict()
                self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getSystemTime",), params])

            params = dict()
            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getProductModel",), params])

            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getProductModelName",), params])

            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getDevInfo",), params])

            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getDevState",), params])

            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig",), params])

            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getScheduleRecordConfig",), params])

            self.logger.debug(f"{indigo.devices[dev.id].name} Device Start Completed")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def getDeviceConfigUiValues(self, pluginProps, typeId, devId):

        # Set default values for Edit Device Settings... (ConfigUI)

        pluginProps["ftpProcessMode"] = pluginProps.get("ftpProcessMode", "0")

        pluginProps["ftpPort"] = pluginProps.get("ftpPort", "50021")

        pluginProps["ftpCameraFolder"] = pluginProps.get("ftpCameraFolder", '')
        if devId in self.globals[CAMERAS]:
            ftpCameraFolder = self.globals[CAMERAS][devId][FTP_CAMERA_FOLDER]
            if ftpCameraFolder != "":
                pluginProps["ftpCameraFolder"] = ftpCameraFolder

        pluginProps["rootFolder"] = pluginProps.get("rootFolder", "~/Documents")
        pluginProps["cameraFolder"] = pluginProps.get("cameraFolder", "")
        pluginProps["enableAutoTimeSync"] = pluginProps.get("enableAutoTimeSync", True)
        pluginProps["ShowPasswordButtonDisplayed"] = pluginProps.get("ShowPasswordButtonDisplayed", True)

        pluginProps["dynamicView"] = pluginProps.get("dynamicView", 0)

        if pluginProps["ShowPasswordButtonDisplayed"]:
            pluginProps["passwordInClearText"] = '*' * len(pluginProps.get("password", ""))
        else:
            pluginProps["passwordInClearText"] = pluginProps.get("password", "")

        pluginProps["cameraPlatform"] = pluginProps.get("cameraPlatform", 0)

        pluginProps["statusPolling"] = pluginProps.get("statusPolling", True)

        pluginProps["pollingSeconds"] = pluginProps.get("pollingSeconds", 5)

        pluginProps["motionDetectionInterval"] = pluginProps.get("motionDetectionInterval", 30)

        return super(Plugin, self).getDeviceConfigUiValues(pluginProps, typeId, devId)

    # noinspection PyMethodMayBeStatic
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):

        if typeId == "camera":
            # Validate 'motionDetectionInterval ' value
            motionDetectionIntervalIsValid = True
            motionDetectionInterval = valuesDict.get("motionDetectionInterval", "15")
            if motionDetectionInterval != "":
                try:
                    validateField = int(motionDetectionInterval)
                    if validateField < 15:
                        motionDetectionIntervalIsValid = False  # Not in valid range
                except ValueError:
                    motionDetectionIntervalIsValid = False  # Not numeric

                if not motionDetectionIntervalIsValid:
                    errorDict = indigo.Dict()
                    errorDict["motionDetectionInterval"] = "Default Detection Interval must be an integer and equal to or greater than 15."
                    errorDict["showAlertText"] = "You must enter a valid Detection Interval value for the camera. It must be an integer and equal to or greater than 15."
                    return False, valuesDict, errorDict
                else:
                    valuesDict["motionDetectionInterval"] = motionDetectionInterval
            else:
                valuesDict["motionDetectionInterval"] = '30'  # Default in seconds

            rootFolder = valuesDict.get("rootFolder", "")
            if rootFolder != "" and rootFolder[0:1] == "~":
                errorDict = indigo.Dict()
                errorDict["rootFolder"] = "If specified, 'Root Folder for FTP file save' cannot start with '~'. Specify full path to user folder instead of using '~'."
                errorDict["showAlertText"] = "If specified, 'Root Folder for FTP file save' cannot start with '~'. Specify full path to user folder instead of using '~'."
                return False, valuesDict, errorDict

        return True, valuesDict

    # noinspection PyMethodMayBeStatic
    def deviceShowPassword(self, valuesDict, typeId, devId):
        valuesDict["ShowPasswordButtonDisplayed"] = False
        valuesDict["passwordInClearText"] = valuesDict["password"]
        return valuesDict

    # noinspection PyMethodMayBeStatic
    def deviceHidePassword(self, valuesDict, typeId, devId):
        valuesDict["ShowPasswordButtonDisplayed"] = True
        valuesDict["passwordInClearText"] = '*' * len(valuesDict.get("password", ""))
        return valuesDict

    def deviceStopComm(self, dev):
        try:
            if dev.id in self.globals[THREADS][MOTION_TIMER]:
                self.globals[CAMERAS][dev.id][MOTION][TIMER_ACTIVE] = False
                self.globals[THREADS][MOTION_TIMER][dev.id].cancel()

            if dev.id in self.globals[THREADS][POLL_CAMERA] and self.globals[THREADS][POLL_CAMERA][dev.id][THREAD_ACTIVE]:
                # self.logger.debug(f"{indigo.devices[dev.id].name} 'polling camera' BEING STOPPED")
                self.logger.debug(f"Device Stop: {dev.name} 'polling camera' BEING STOPPED")
                self.globals[THREADS][POLL_CAMERA][dev.id][EVENT].set()  # Stop the Thread
                self.globals[THREADS][POLL_CAMERA][dev.id][THREAD].join(7.0)  # wait for thread to end
                # self.logger.debug(f"{indigo.devices[dev.id].name} 'polling camera' NOW STOPPED")
                self.logger.debug(f"Device Stop: {dev.name} 'polling camera' NOW STOPPED")
                self.globals[THREADS][POLL_CAMERA].pop(dev.id, None)  # Remove Thread

            if dev.id in self.globals[THREADS][SEND_COMMAND] and self.globals[THREADS][SEND_COMMAND][dev.id][THREAD_ACTIVE]:
                self.logger.debug("Device Stop: 'sendCommand' BEING STOPPED")
                self.globals[THREADS][SEND_COMMAND][dev.id][EVENT].set()  # Stop the Thread
                self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CameraResponse.STOP_THREAD])
                self.globals[THREADS][SEND_COMMAND][dev.id][THREAD].join(7.0)  # wait for thread to end
                self.logger.debug("Device Stop: 'sendCommand' NOW STOPPED")
                self.globals[THREADS][SEND_COMMAND].pop(dev.id, None)  # Remove Thread

            if dev.id in self.globals[THREADS][HANDLE_RESPONSE] and self.globals[THREADS][HANDLE_RESPONSE][dev.id][THREAD_ACTIVE]:
                self.logger.debug("Device Stop: 'handleResponse' BEING STOPPED")
                self.globals[THREADS][HANDLE_RESPONSE][dev.id][EVENT].set()  # Stop the Thread
                self.globals[QUEUES][RESPONSE_FROM_CAMERA][dev.id].put([CameraResponse.STOP_THREAD])
                self.globals[THREADS][HANDLE_RESPONSE][dev.id][THREAD].join(7.0)  # wait for thread to end
                self.logger.debug("Device Stop: 'handleResponse' NOW STOPPED")
                self.globals[THREADS][HANDLE_RESPONSE].pop(dev.id, None)  # Remove Thread

            if COMMAND_TO_SEND in self.globals[QUEUES]:
                self.globals[QUEUES][COMMAND_TO_SEND].pop(dev.id, None)  # Remove Queue

            if RESPONSE_FROM_CAMERA in self.globals[QUEUES]:
                self.globals[QUEUES][RESPONSE_FROM_CAMERA].pop(dev.id, None)  # Remove Queue

            self.globals[CAMERAS].pop(dev.id, None)  # Remove Camera plugin internal storage

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def checkCameraEnabled(self, dev, pluginActionName):
        try:
            if dev is None:
                callingAction = inspect.stack()[1][3]
                self.logger.error(f"Plugin Action '{pluginActionName}' [{callingAction}] ignored as no camera device defined.")
                return False
            elif not dev.enabled:
                callingAction = inspect.stack()[1][3]
                self.logger.error(f"Plugin Action '{pluginActionName}' [{callingAction}] ignored as Camera '{dev.name}' is not enabled.")
                return False

            return True

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def actionControlSensor(self, action, dev):
        try:
            self.logger.debug(f"actionControlSensor: Action = {action}")
            self.logger.debug(f"actionControlSensor: Dev = {dev}")

            if not self.checkCameraEnabled(dev, action.sensorAction):
                return

            # ##### TURN ON ######
            if action.sensorAction == indigo.kSensorAction.TurnOn:
                self.motionDetectionOn(action, dev)

            # ##### TURN OFF ######
            elif action.sensorAction == indigo.kSensorAction.TurnOff:
                self.motionDetectionOff(action, dev)

            # ##### REQUEST STATUS ######
            elif action.sensorAction == indigo.kSensorAction.RequestStatus:
                self.updateCameraStatus(action, dev)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def rebootCamera(self, pluginAction, dev):
        try:
            if not self.checkCameraEnabled(dev, pluginAction.description):
                return

            params = dict()
            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("rebootSystem",), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def refreshCamera(self, pluginAction, dev):
        try:
            if not self.checkCameraEnabled(dev, pluginAction.description):
                return

            params = dict()
            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([INTERNAL, ("refreshCamera",), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def infraredToggle(self, pluginAction, dev):
        try:
            if not self.checkCameraEnabled(dev, pluginAction.description):
                return

            infraLedState = int(dev.states["infraLedState"]) ^ 1
            if infraLedState == 0:
                infraLedAction = "closeInfraLed"
            else:
                infraLedAction = "openInfraLed"

            params = dict()
            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, (infraLedAction,), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def infraredOn(self, pluginAction, dev):
        try:
            if not self.checkCameraEnabled(dev, pluginAction.description):
                return

            params = dict()
            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("openInfraLed",), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def infraredOff(self, pluginAction, dev):
        try:
            if not self.checkCameraEnabled(dev, pluginAction.description):
                return

            params = dict()
            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("closeInfraLed",), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def motionDetectionToggle(self, pluginAction, dev):
        try:
            if not self.checkCameraEnabled(dev, pluginAction.description):
                return

            params = dict()
            self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", ENABLE_MOTION_DETECT, kToggle), params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def motionDetectionOn(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", ENABLE_MOTION_DETECT, kOn), params])

    def motionDetectionOff(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", ENABLE_MOTION_DETECT, kOff), params])

    def updateCameraStatus(self, pluginAction, dev):

        indigo.server.log(f"updateCameraStatus: pluginAction = {pluginAction}")

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getDevState",), params])
        self.logger.info(f"sent \"{dev.name}\" request status")

    def motionDetectionGet(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig",), params])

    def ringToggle(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", RING, kToggle), params])

    def ringON(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", RING, kOn), params])

    def ringOFF(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", RING, kOff), params])

    def snapToggle(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", SNAP_PICTURE, kToggle), params])

    def snapOn(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", SNAP_PICTURE, kOn), params])

    def snapOff(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", SNAP_PICTURE, kOff), params])

    def motionDetectionRecordToggle(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", MOTION_DETECTION_RECORD, kToggle), params])

    def motionDetectionRecordOn(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", MOTION_DETECTION_RECORD, kOn), params])

    def motionDetectionRecordOff(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getMotionDetectConfig", MOTION_DETECTION_RECORD, kOff), params])

    def scheduleRecordToggle(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getScheduleRecordConfig", SCHEDULE_RECORD, kToggle), params])

    def scheduleRecordOn(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getScheduleRecordConfig", SCHEDULE_RECORD, kOn), params])

    def scheduleRecordOff(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getScheduleRecordConfig", SCHEDULE_RECORD, kOff), params])

    def snap(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("snapPicture2",), params])

    def synchroniseCameraTime(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        self.globals[QUEUES][COMMAND_TO_SEND][dev.id].put([CAMERA, ("getSystemTime",), params])

    def experimental(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        pass

    def experimental1(self, pluginAction, dev):

        if not self.checkCameraEnabled(dev, pluginAction.description):
            return

        params = dict()
        pass

    def list_dynamic_view_devices(self, filter="", values_dict=None, type_id="", target_id=0):  # noqa [parameter value is not used]
        try:
            dynamic_view_devices_list = list()
            dynamic_view_devices_list.append((0, "None"))

            for dev in indigo.devices.iter("com.autologplugin.indigoplugin.dynamicviewcontroller.dynamicView"):
                dynamic_view_devices_list.append((dev.id, dev.name))

            return dynamic_view_devices_list

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
