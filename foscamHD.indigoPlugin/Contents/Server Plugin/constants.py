#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Foscam HD Controller © Autolog 2019-2023
# Requires Indigo 2022.1+
#

import logging

# ============================== Custom Imports ===============================
try:
    import indigo  # noqa
except ImportError:
    pass

number = -1

debug_show_constants = False
debug_use_labels = False


def constant_id(constant_label) -> int:  # Auto increment constant id
    global number
    if debug_show_constants and number == -1:
        indigo.server.log("Foscam HD Plugin internal Constant Name mapping ...", level=logging.DEBUG)
    number += 1
    if debug_show_constants:
        indigo.server.log(f"{number}: {constant_label}", level=logging.DEBUG)
    if debug_use_labels:
        return constant_label
    else:
        return number

# plugin Constants


# noinspection Duplicates
ADDRESS = constant_id("ADDRESS")
API_VERSION = constant_id("API_VERSION")
CAMERA = constant_id("CAMERA")
CAMERAS = constant_id("CAMERAS")
CAMERA_FILTERS = constant_id("CAMERA_FILTERS")
CAMERA_FOLDER = constant_id("CAMERA_FOLDER")
CAMERA_PLATFORM = constant_id("CAMERA_PLATFORM")
COMMAND_TO_SEND = constant_id("COMMAND_TO_SEND")
DATETIME_STARTED = constant_id("DATETIME_STARTED")
DAYS = constant_id("DAYS")
DETECTION_ENABLED = constant_id("DETECTION_ENABLED")
DETECTION_INTERVAL = constant_id("DETECTION_INTERVAL")
DYNAMIC_VIEW = constant_id("DYNAMIC_VIEW")
ENABLE_AUTO_TIME_SYNC = constant_id("ENABLE_AUTO_TIME_SYNC")
EVENT = constant_id("EVENT")
FTP_CAMERA_FOLDER = constant_id("FTP_CAMERA_FOLDER")
FTP_PORT = constant_id("FTP_PORT")
FTP_PROCESS_MODE = constant_id("FTP_PROCESS_MODE")
HANDLE_RESPONSE = constant_id("HANDLE_RESPONSE")
IMAGES = constant_id("IMAGES")
IMAGE_FILE = constant_id("IMAGE_FILE")
IMAGE_FILE_PREVIOUS = constant_id("IMAGE_FILE_PREVIOUS")
IMAGE_FOLDER = constant_id("IMAGE_FOLDER")
IMAGE_FOLDER_LIST = constant_id("IMAGE_FOLDER_LIST")
IMAGE_FOLDER_PREVIOUS = constant_id("IMAGE_FOLDER_PREVIOUS")
IMAGE_NUMBER = constant_id("IMAGE_NUMBER")
INTERNAL = constant_id("INTERNAL")
IP_ADDRESS = constant_id("IP_ADDRESS")
IP_ADDRESS_PORT = constant_id("IP_ADDRESS_PORT")
IP_ADDRESS_PORT_NAME = constant_id("IP_ADDRESS_PORT_NAME")
KEEP_THREAD_ALIVE = constant_id("KEEP_THREAD_ALIVE")
LAST_ALERT_FILE_TIME = constant_id("LAST_ALERT_FILE_TIME")
LAST_DISPLAYED_IMAGE_DAY = constant_id("LAST_DISPLAYED_IMAGE_DAY")
LAST_DISPLAYED_IMAGE_HALF_HOUR = constant_id("LAST_DISPLAYED_IMAGE_HALF_HOUR")
LAST_DISPLAYED_IMAGE_SELECTED = constant_id("LAST_DISPLAYED_IMAGE_SELECTED")
MOTION = constant_id("MOTION")
MOTION_TIMER = constant_id("MOTION_TIMER")
PASSWORD = constant_id("PASSWORD")
PATH = constant_id("PATH")
PLUGIN_DISPLAY_NAME = constant_id("PLUGIN_DISPLAY_NAME")
PLUGIN_ID = constant_id("PLUGIN_ID")
PLUGIN_INFO = constant_id("PLUGIN_INFO")
PLUGIN_VERSION = constant_id("PLUGIN_VERSION")
POLLING = constant_id("POLLING")
POLL_CAMERA = constant_id("POLL_CAMERA")
PORT = constant_id("PORT")
PREVIOUSLY_DETECTED = constant_id("PREVIOUSLY_DETECTED")
QUEUES = constant_id("QUEUES")
RESPONSE_FROM_CAMERA = constant_id("RESPONSE_FROM_CAMERA")
RING_ENABLED = constant_id("RING_ENABLED")
ROOT_FOLDER = constant_id("ROOT_FOLDER")
SECONDS = constant_id("SECONDS")
SEND_COMMAND = constant_id("SEND_COMMAND")
SET_MOTION_DETECT_CONFIG_FUNCTION = constant_id("SET_MOTION_DETECT_CONFIG_FUNCTION")
SET_MOTION_DETECT_CONFIG_OPTION = constant_id("SET_MOTION_DETECT_CONFIG_OPTION")
SNAP_ENABLED = constant_id("SNAP_ENABLED")
STATUS = constant_id("STATUS")
# STOP_THREAD = constant_id("STOPTHREAD")
TEST_SYM_LINK = constant_id("TEST_SYM_LINK")
THREAD = constant_id("THREAD")
THREADS = constant_id("THREADS")
THREAD_ACTIVE = constant_id("THREAD_ACTIVE")
TIMER_ACTIVE = constant_id("TIMER_ACTIVE")
USERNAME = constant_id("USERNAME")

# Foscam HD Camera Platform Constants
CAMERA_PLATFORM_ORIGINAL = 0
CAMERA_PLATFORM_AMBA = 1

# Thread Starting Delays
DELAY_START_RESPONSE_FROM_CAMERA = 2  # In seconds
DELAY_START_SEND_COMMAND = 3  # In seconds
DELAY_START_POLLING = 4  # In seconds

# setMotionDetectConfig / setMotionDetectConfig1: Functions and options

NOT_SET = 0
ENABLE_MOTION_DETECT = 1
RING = 2
SNAP_PICTURE = 3
MOTION_DETECTION_RECORD = 4
SCHEDULE_RECORD = 5

kOn = 1
kOff = 2
kToggle = 3

kFunction = ('', 'EnableMotionDetect_', 'Ring_', 'SnapPicture_')
kOption = ('', 'On', 'Off', 'Toggle')

LOG_LEVEL_NOT_SET = 0
LOG_LEVEL_DEBUGGING = 10
LOG_LEVEL_CAMERA = 15
LOG_LEVEL_INFO = 20
LOG_LEVEL_WARNING = 30
LOG_LEVEL_ERROR = 40
LOG_LEVEL_CRITICAL = 50

LOG_LEVEL_TRANSLATION = dict()
LOG_LEVEL_TRANSLATION[LOG_LEVEL_NOT_SET] = "Not Set"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_DEBUGGING] = "Debugging"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_CAMERA] = "Camera Communication Logging"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_INFO] = "Info"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_WARNING] = "Warning"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_ERROR] = "Error"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_CRITICAL] = "Critical"


class DynamicProcess:
    # See https://stackoverflow.com/questions/67525257/capture-makes-remaining-patterns-unreachable
    INITIALISE_DYNAMIC_STATE = 0
    UPDATE_DYNAMIC_STATE = 1
    SKIP = 2


class CameraResponse:
    CLOSE_INFRA_LED = "closeInfraLed"
    GET_DEV_INFO = "getDevInfo"
    GET_DEV_NAME = "getDevName"
    GET_DEV_STATE = 'getDevState'
    GET_MOTION_DETECT_CONFIG = "getMotionDetectConfig"
    GET_MOTION_DETECT_CONFIG1 = "getMotionDetectConfig1"
    GET_PRODUCT_MODEL = "getProductModel"
    GET_PRODUCT_MODEL_NAME = "getProductModelName"
    GET_RECORD_LIST = "getRecordList"
    GET_RECORD_LIST1 = "getRecordList1"
    GET_SCHEDULE_RECORD_CONFIG = "getScheduleRecordConfig"
    GET_SYSTEM_TIME = "getSystemTime"
    OPEN_INFRA_LED = "openInfraLed"
    REBOOT_SYSTEM = "rebootSystem"
    REFRESH = "refreshCamera"
    SET_MOTION_DETECT_CONFIG = "setMotionDetectConfig"
    SET_SCHEDULE_RECORD_CONFIG = "setScheduleRecordConfig"
    SET_SYSTEM_TIME = "setSystemTime"
    SNAP_PICTURE2 = "snapPicture2"
    START_RECORD = "startRecord"
    STOP_RECORD = "stopRecord"
    STOP_THREAD = "stopThread"
