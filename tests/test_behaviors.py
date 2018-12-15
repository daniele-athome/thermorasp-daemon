# -*- coding: utf-8 -*-

import asyncio
import unittest
import json

from datetime import datetime

from hbmqtt.mqtt.constants import QOS_0

from thermostat.behaviors.generic import TargetTemperatureBehavior

from . import BaseTest


class TargetTemperatureBehaviorTest(BaseTest, unittest.TestCase):

    sensors = [
        'home-assistant/thermorasp/sensor/temp_core'
    ]
    devices = [
        'home-assistant/thermorasp/device/home_boiler'
    ]

    def testHeating(self):
        @asyncio.coroutine
        def test_coro():
            try:
                broker = yield from self.startBroker()
                client = yield from self.startClient()

                behavior = TargetTemperatureBehavior(0, 'generic.TargetTemperature', self.sensors, self.devices, client)

                # subscribe for the behavior
                yield from client.subscribe([(topic + '/+', QOS_0) for topic in self.sensors + self.devices])
                yield from behavior.startup({'target_temperature': 25, 'mode': 'heating'})

                yield from self._testTargetTemperature(behavior, client, 20, True)
                yield from self._testTargetTemperature(behavior, client, 10, True)
                yield from self._testTargetTemperature(behavior, client, 30, False)
                yield from self._testTargetTemperature(behavior, client, 18, True)
                yield from self._testTargetTemperature(behavior, client, 25.5, False)
                yield from self._testTargetTemperature(behavior, client, 25, False)

                yield from client.disconnect()
                yield from broker.shutdown()
                future.set_result(True)

            except Exception as e:
                future.set_exception(e)

        future = asyncio.Future(loop=self.loop)
        self._testCoro(future, test_coro)

    def testCooling(self):
        @asyncio.coroutine
        def test_coro():
            try:
                broker = yield from self.startBroker()
                client = yield from self.startClient()

                behavior = TargetTemperatureBehavior(0, 'generic.TargetTemperature', self.sensors, self.devices, client)

                # subscribe for the behavior
                yield from client.subscribe([(topic + '/+', QOS_0) for topic in self.sensors + self.devices])
                yield from behavior.startup({'target_temperature': 18, 'mode': 'cooling'})

                yield from self._testTargetTemperature(behavior, client, 20, True)
                yield from self._testTargetTemperature(behavior, client, 10, False)
                yield from self._testTargetTemperature(behavior, client, 30, True)
                yield from self._testTargetTemperature(behavior, client, 18, False)
                yield from self._testTargetTemperature(behavior, client, 25.5, True)
                yield from self._testTargetTemperature(behavior, client, 25, True)

                yield from behavior.shutdown()

                yield from client.disconnect()
                yield from broker.shutdown()
                future.set_result(True)

            except Exception as e:
                import traceback
                traceback.print_exc()
                future.set_exception(e)

        future = asyncio.Future(loop=self.loop)
        self._testCoro(future, test_coro)

    @asyncio.coroutine
    def _testTargetTemperature(self, behavior, client, temperature, enabled):
        # publish test sensor data
        client_pub = yield from self.startClient()
        for topic in self.sensors:
            yield from client_pub.publish(topic + '/temperature', json.dumps({
                'value': temperature,
                'unit': 'celsius',
                'timestamp': datetime.now().isoformat()
            }).encode(), retain=True)
        yield from client_pub.disconnect()

        message = yield from client.deliver_message()
        if any(message.topic.startswith(topic) for topic in self.sensors):
            yield from behavior.sensor_data(message.topic, json.loads(message.data))
        elif any(message.topic.startswith(topic) for topic in self.devices):
            yield from behavior.device_state(message.topic, json.loads(message.data))
        else:
            self.fail('No sensor or device data received.')

        # behavior should have sent control command
        message = yield from client.deliver_message()
        self.assertEqual(message.topic, self.devices[0] + '/control')
        payload = json.loads(message.data)
        self.assertEqual(payload['enabled'], enabled)
