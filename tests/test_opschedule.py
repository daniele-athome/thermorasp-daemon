# -*- coding: utf-8 -*-

import asyncio
import unittest
import json

import datetime
from freezegun import freeze_time

from hbmqtt.mqtt.constants import QOS_0

from thermostat.opschedule import OperatingSchedule

from . import BaseTest


class DummyItem(object):
    def __init__(self, topic):
        self.topic = topic


class DummyManager(object):

    def __init__(self, items):
        self.items = items

    def __getitem__(self, item):
        return self.items[item]

    def values(self):
        return self.items.values()


class OperatingScheduleTest(BaseTest, unittest.TestCase):

    def testTimedSchedule(self):
        @asyncio.coroutine
        def test_coro():
            try:
                broker = yield from self.startBroker()

                sensors = DummyManager({'temp_core': DummyItem('homeassistant/thermorasp/sensor/temp_core')})
                devices = DummyManager({'home_boiler': DummyItem('homeassistant/thermorasp/device/home_boiler')})
                schedule = OperatingSchedule(sensors, devices, {
                    'id': 1,
                    'behaviors': [
                        {
                            'id': 1,
                            'name': 'generic.TargetTemperatureBehavior',
                            'order': 1,
                            'start_time': 0,
                            'end_time': 3400,
                            'config': {'target_temperature': 25},
                            'sensors': ['temp_core'],
                            'devices': ['home_boiler'],
                        }
                    ],
                })
                yield from schedule.startup()

                client = yield from self.startClient()
                yield from client.subscribe([(schedule.devices['home_boiler'].topic + '/+', QOS_0)])

                with freeze_time('2018-12-17T00:00:00.0000'):
                    yield from self._publishTemperature(schedule, 25)
                    yield from asyncio.sleep(0.5)
                    yield from schedule.timer()
                    yield from asyncio.sleep(0.5)
                    # twice because one from the sensor data and one from the timer
                    yield from self._testTargetTemperature(schedule, client, False)
                    yield from self._testTargetTemperature(schedule, client, False)

                with freeze_time('2018-12-17T16:12:03.5346'):
                    yield from self._publishTemperature(schedule, 23)
                    yield from asyncio.sleep(0.5)
                    yield from schedule.timer()
                    yield from asyncio.sleep(0.5)
                    # twice because one from the sensor data and one from the timer
                    yield from self._testTargetTemperature(schedule, client, True)
                    yield from self._testTargetTemperature(schedule, client, True)

                with freeze_time('2018-12-20T09:24:12'):
                    yield from schedule.timer()
                    self.assertIsNone(schedule.behavior)

                with freeze_time('2018-12-21T18:12:43.1203'):
                    yield from schedule.timer()
                    self.assertIsNone(schedule.behavior)

                yield from schedule.shutdown()

                yield from client.disconnect()
                yield from broker.shutdown()
                future.set_result(True)

            except Exception as e:
                future.set_exception(e)

        future = asyncio.Future(loop=self.loop)
        self._testCoro(future, test_coro)

    @asyncio.coroutine
    def _publishTemperature(self, schedule, temperature):
        # publish test sensor data
        client_pub = yield from self.startClient()
        for sensor in schedule.sensors.values():
            yield from client_pub.publish(sensor.topic + '/temperature', json.dumps({
                'value': temperature,
                'unit': 'celsius',
                'timestamp': datetime.datetime.now().isoformat()
            }).encode(), retain=True)
        yield from client_pub.disconnect()

    @asyncio.coroutine
    def _testTargetTemperature(self, schedule, client, enabled):
        # behavior should have sent control command
        message = yield from client.deliver_message()
        self.assertEqual(message.topic, schedule.devices['home_boiler'].topic + '/control')
        payload = json.loads(message.data.decode())
        self.assertEqual(payload['enabled'], enabled)
