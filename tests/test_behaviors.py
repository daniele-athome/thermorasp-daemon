# -*- coding: utf-8 -*-

import sys
import logging.config
import asyncio
import unittest
import json

from datetime import datetime

from hbmqtt.broker import Broker
from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_0

from sanic.log import logger
from sanic.log import LOGGING_CONFIG_DEFAULTS

from thermostat import app
from thermostat.behaviors.generic import TargetTemperatureBehavior

broker_config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '127.0.0.1:9883',
            'max_connections': 10
        },
    },
    'sys_interval': 0,
    'auth': {
        'allow-anonymous': True,
    },
    'topic-check': {
        'enabled': False,
    },
}


class DummyEventLogger(object):
    def __init__(self):
        pass

    def event(self, level: str, source: str, name: str, description: str = None):
        print("EVENT: {}/{}: {} - {}".format(level, source, name, description))

    def event_exc(self, level: str, source: str, name: str):
        import traceback
        e_type, e_value, e_tb = sys.exc_info()
        strerr1 = traceback.format_exception_only(e_type, e_value)[0][:-1]
        strerr = ''.join(traceback.format_exception(e_type, e_value, e_tb))
        self.event(level, source, name, strerr1 + "\n" + strerr)


class TargetTemperatureBehaviorTest(unittest.TestCase):

    sensors = [
        'home-assistant/thermorasp/sensor/temp_core'
    ]
    devices = [
        'home-assistant/thermorasp/device/home_boiler'
    ]

    def setUp(self):
        formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
        #logging.basicConfig(level=logging.DEBUG, format=formatter)
        logging.config.dictConfig(LOGGING_CONFIG_DEFAULTS)
        logger.setLevel(logging.DEBUG)

        app.eventlog = DummyEventLogger()
        app.default_sensors_validity = 300
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @asyncio.coroutine
    def startBroker(self):
        broker = Broker(broker_config, plugin_namespace='thermostat')
        yield from broker.start()
        return broker

    @asyncio.coroutine
    def startClient(self):
        client = MQTTClient(config={'auto_reconnect': False, 'keep_alive': 1})
        yield from client.connect('mqtt://127.0.0.1:9883/')
        self.assertIsNotNone(client.session)
        return client

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

                yield from client.disconnect()
                yield from broker.shutdown()
                future.set_result(True)

            except Exception as e:
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

    def _testCoro(self, future, coro):
        self.loop.run_until_complete(coro())
        try:
            self.loop.run_until_complete(asyncio.gather(*asyncio.Task.all_tasks()))
        except asyncio.CancelledError:
            pass
        if future.exception():
            raise future.exception()


if __name__ == '__main__':
    test = TargetTemperatureBehaviorTest()
    test.setUp()
    test.testHeating()
    test.tearDown()
