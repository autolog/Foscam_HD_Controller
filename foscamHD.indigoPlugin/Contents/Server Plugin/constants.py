#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2019
# Requires Indigo 7
#

# plugin Constants

# Foscam HD Camera Platform Constants
kOriginal = 0
kAmba = 1

# Thread Starting Delays
kDelayStartResponseFromcamera = 2
kDelayStartSendCommand = 3
kDelayStartPolling = 4

# setMotionDetectConfig / setMotionDetectConfig1: Functions and options

kNotSet = 0

kEnableMotionDetect = 1
kRing = 2
kSnapPicture = 3
kMotionDetectionRecord = 4
kScheduleRecord = 5

kOn = 1
kOff = 2
kToggle = 3

kFunction = ('','EnableMotionDetect_','Ring_','SnapPicture_')
kOption = ('','On','Off', 'Toggle')