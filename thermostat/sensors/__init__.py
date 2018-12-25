# -*- coding: utf-8 -*-
"""Sensors communication protocols."""

import asyncio
import json
import importlib
import hbmqtt.client as mqtt_client

from sanic.log import logger

from .. import app


class BaseSensorHandler(object):
    """Base interface for sensor handlers."""

    def __init__(self, sensor_id: str, address: str, sensor_type: str, icon: str):
        self.id = sensor_id
        self.address = address
        self.type = sensor_type
        self.icon = icon
        self.broker = mqtt_client.MQTTClient(config={'auto_reconnect': False})
        self.is_running = False
        self.timer = None
        self.topic = app.new_topic('sensor/' + sensor_id)

    async def _connect(self):
        await self.broker.connect(app.broker_url)
        logger.info("Sensor " + self.id + " connected to broker")
        await self.connected()
        # TODO what do we control here?
        await self.broker.subscribe([(self.topic + '/control', mqtt_client.QOS_0)])
        while self.is_running:
            message = await self.broker.deliver_message()
            logger.debug(self.id + " SENSOR topic={}, payload={}".format(message.topic, message.data))
            await self.message(message.data.decode())

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
        await self.broker.publish(self.topic + append_topic, json.dumps(payload).encode(), retain=retain)

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

    # TODO since we subscribed to topic "control", "message" might be confusing
    async def message(self, payload):
        pass

    def get_name(self):
        return 'sensor:' + self.id


def get_sensor_handler(sensor_id: str, protocol: str, address: str, sensor_type: str, icon: str) -> BaseSensorHandler:
    """Returns an appropriate sensor handler for the given protocol and address."""
    module = importlib.import_module('.'+protocol, __name__)
    if module:
        schemes = getattr(module, 'schemes')
        if schemes:
            scheme_part, address_part = address.split(':', 1)
            if scheme_part in schemes:
                handler_class = schemes[scheme_part]
                return handler_class(sensor_id, address_part, sensor_type, icon)
