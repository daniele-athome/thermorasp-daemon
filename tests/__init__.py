# -*- coding: utf-8 -*-

import sys
import asyncio
import logging.config

from sanic.log import logger, LOGGING_CONFIG_DEFAULTS

from hbmqtt.client import MQTTClient
from hbmqtt.broker import Broker

from thermostat import app


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


class BaseTest(object):

    def setUp(self):
        formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
        #logging.basicConfig(level=logging.DEBUG, format=formatter)
        logging.config.dictConfig(LOGGING_CONFIG_DEFAULTS)
        logger.setLevel(logging.DEBUG)

        app.broker_url = 'mqtt://127.0.0.1:9883/'
        app.eventlog = DummyEventLogger()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.stop()
        self.loop.close()

    @asyncio.coroutine
    def startBroker(self):
        broker = Broker(broker_config, plugin_namespace='thermostat')
        yield from broker.start()
        return broker

    @asyncio.coroutine
    def startClient(self):
        client = MQTTClient(config={'auto_reconnect': False})
        yield from client.connect(app.broker_url)
        return client

    def _testCoro(self, future, coro):
        self.loop.run_until_complete(coro())
        try:
            self.loop.run_until_complete(asyncio.gather(*asyncio.Task.all_tasks()))
        except:
            pass
        if future.exception():
            raise future.exception()
