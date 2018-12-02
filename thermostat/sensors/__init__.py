# -*- coding: utf-8 -*-
"""Sensors communication protocols."""

import asyncio
import logging
import json
import importlib
import hbmqtt.client as mqtt_client

from .. import app

# TEST loggers
log = logging.getLogger("root")


class BaseSensorHandler(object):
    """Base interface for sensor handlers."""

    def __init__(self, sensor_id: str, address: str):
        self.id = sensor_id
        self.address = address
        self.broker = mqtt_client.MQTTClient()
        self.is_running = False
        self.timer = None
        self.topic = app.new_topic('sensor/' + sensor_id)

    async def _connect(self):
        await self.broker.connect(app.broker_url)
        log.debug("Sensor " + self.id + " connected to broker")
        await self.connected()
        await self.broker.subscribe([(self.topic, mqtt_client.QOS_0)])
        while self.is_running:
            message = await self.broker.deliver_message()
            log.debug(self.id + " SENSOR topic={}, payload={}".format(message.topic, message.data))
            await self.message(message.data.decode('utf-8'))

    async def _disconnect(self):
        await self.broker.disconnect()
        await self.disconnected()

    def start_timer(self, seconds):
        self.timer = asyncio.ensure_future(self._timer(seconds))

    async def _timer(self, seconds):
        while app.is_running:
            await asyncio.sleep(seconds)
            await self.timeout()

    async def publish(self, payload, append_topic='', retain=None):
        await self.broker.publish(self.topic + append_topic, json.dumps(payload).encode('utf-8'), retain=retain)

    def startup(self):
        self.is_running = True
        # connect to broker
        asyncio.ensure_future(self._connect())

    def shutdown(self):
        self.is_running = False
        if self.timer:
            self.timer.cancel()
        asyncio.ensure_future(self._disconnect())

    async def timeout(self):
        pass

    async def connected(self):
        pass

    async def disconnected(self):
        pass

    async def message(self, payload):
        pass


def get_sensor_handler(sensor_id: str, protocol: str, address: str) -> BaseSensorHandler:
    """Returns an appropriate sensor handler for the given protocol and address."""
    module = importlib.import_module('.'+protocol, __name__)
    if module:
        schemes = getattr(module, 'schemes')
        if schemes:
            scheme_part, address_part = address.split(':', 1)
            if scheme_part in schemes:
                handler_class = schemes[scheme_part]
                return handler_class(sensor_id, address_part)
