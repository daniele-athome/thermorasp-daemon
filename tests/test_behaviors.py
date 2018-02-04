# -*- coding: utf-8 -*-

import unittest

from freezegun import freeze_time

from thermostat.models import eventlog
from thermostat.devices import get_device_handler
from thermostat.behaviors import BehaviorContext
from thermostat.behaviors.chrono import *


class WeeklyHeatingBehaviorTest(unittest.TestCase):

    @staticmethod
    def dummy_event_log(level, source, name, description=None):
        print("EVENT: {}/{}: {} - {}".format(level, source, name, description))

    def setUp(self):
        eventlog.event = self.dummy_event_log

        self.context = BehaviorContext({
            'home_boiler': get_device_handler('home_boiler', 'boiler_on_off', 'local', 'MEMSW:', 'Test Boiler')
        }, {
            'temperature': {
                '_avg': {
                    'unit': 'celsius',
                    'value': 18,
                },
            },
        })
        self.behavior = WeeklyProgramBehavior(1, {
            'target_device_id': 'home_boiler',
            'mode': 'heating',
            'day0': [
                {
                    'time_start': '06:00',
                    'target_temperature': 23,
                },
                {
                    'time_start': '08:00',
                    'target_temperature': 10,
                },
                {
                    'time_start': '18:00',
                    'target_temperature': 23,
                },
                {
                    'time_start': '23:00',
                    'target_temperature': 20,
                },
            ],
            'day1': [
                {
                    'time_start': '05:00',
                    'target_temperature': 25,
                },
                {
                    'time_start': '09:00',
                    'target_temperature': 5,
                },
                {
                    'time_start': '17:00',
                    'target_temperature': 27,
                },
                {
                    'time_start': '18:00',
                    'target_temperature': 34,
                },
            ],
            'day2': [
                {
                    'time_start': '06:00',
                    'target_temperature': 23,
                },
                {
                    'time_start': '08:00',
                    'target_temperature': 10,
                },
                {
                    'time_start': '18:00',
                    'target_temperature': 23,
                },
                {
                    'time_start': '23:00',
                    'target_temperature': 20,
                },
            ],
            'day3': [
                {
                    'time_start': '06:00',
                    'target_temperature': 23,
                },
                {
                    'time_start': '08:00',
                    'target_temperature': 10,
                },
                {
                    'time_start': '18:00',
                    'target_temperature': 23,
                },
                {
                    'time_start': '23:00',
                    'target_temperature': 20,
                },
            ],
            'day4': [
                {
                    'time_start': '03:00',
                    'target_temperature': 28,
                },
                {
                    'time_start': '08:00',
                    'target_temperature': 10,
                },
                {
                    'time_start': '23:00',
                    'target_temperature': 21,
                },
                {
                    'time_start': '23:30',
                    'target_temperature': 17,
                },
            ],
            'day5': [
                {
                    'time_start': '06:00',
                    'target_temperature': 23,
                },
                {
                    'time_start': '08:00',
                    'target_temperature': 10,
                },
                {
                    'time_start': '18:00',
                    'target_temperature': 23,
                },
                {
                    'time_start': '23:00',
                    'target_temperature': 20,
                },
            ],
            'day6': [
                {
                    'time_start': '00:00',
                    'target_temperature': 11,
                },
            ],
        })

    def assertDeviceOn(self):
        status = self.context.devices['home_boiler'].status()
        self.assertTrue(status['enabled'])

    def assertDeviceOff(self):
        status = self.context.devices['home_boiler'].status()
        self.assertFalse(status['enabled'])

    def testMonday(self):
        with freeze_time('2018-02-05 00:10:30'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-05 06:30:45'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-05 12:15:32'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-05 17:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-05 18:00:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-05 18:40:43'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-05 20:35:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-05 22:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-05 23:05:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()

    def testTuesday(self):
        with freeze_time('2018-02-06 00:10:30'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-06 06:30:45'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-06 12:15:32'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-06 17:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-06 18:00:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-06 18:40:43'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-06 20:35:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-06 22:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-06 23:05:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()

    def testWednesday(self):
        with freeze_time('2018-02-07 00:10:30'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-07 06:30:45'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-07 12:15:32'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-07 17:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-07 18:00:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-07 18:40:43'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-07 20:35:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-07 22:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-07 23:05:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()

    def testThursday(self):
        with freeze_time('2018-02-08 00:10:30'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-08 06:30:45'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-08 12:15:32'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-08 17:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-08 18:00:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-08 18:40:43'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-08 20:35:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-08 22:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-08 23:05:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()

    def testFriday(self):
        with freeze_time('2018-02-09 00:10:30'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-09 06:30:45'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-09 12:15:32'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-09 17:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-09 18:00:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-09 18:40:43'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-09 20:35:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-09 22:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-09 23:05:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-09 23:59:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()

    def testSaturday(self):
        with freeze_time('2018-02-10 00:10:30'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-10 06:30:45'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-10 12:15:32'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-10 17:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-10 18:00:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-10 18:40:43'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-10 20:35:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-10 22:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-10 23:05:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()
        with freeze_time('2018-02-10 23:59:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOn()

    def testSunday(self):
        with freeze_time('2018-02-11 00:10:30'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 06:30:45'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 12:15:32'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 17:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 18:00:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 18:40:43'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 20:35:00'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 22:59:59'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 23:05:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
        with freeze_time('2018-02-11 23:59:23'):
            self.behavior.execute(self.context)
            self.assertDeviceOff()
