# -*- coding: utf-8 -*-
"""Devices communication protocols."""

import json
import asyncio
import logging
import importlib
import hbmqtt.client as mqtt_client

from .. import app
from ..errors import NotSupportedError

# TEST loggers
log = logging.getLogger("root")


class BaseDeviceHandler(object):
    """Base interface for device handlers."""

    # subclasses must define SUPPORTED_TYPES with the list of supported device types
    SUPPORTED_TYPES = ()

    def __init__(self, device_id, device_type, protocol, address, name):
        if device_type not in self.SUPPORTED_TYPES:
            raise NotSupportedError('Device type not supported.')

        self.id = device_id
        self.type = device_type
        self.protocol = protocol
        self.address = address.split(':', 1)
        self.name = name
        self.is_running = False
        self.broker = mqtt_client.MQTTClient()
        self.topic = app.new_topic('device/' + device_id)

    async def _connect(self):
        await self.broker.connect(app.broker_url)
        log.debug("Device " + self.id + " connected to broker")
        await self.connected()
        await self.broker.subscribe([(self.topic + '/control', mqtt_client.QOS_2)])
        while self.is_running:
            message = await self.broker.deliver_message()
            log.debug(self.id + " DEVICE topic={}, payload={}".format(message.topic, message.data))
            await self.control(json.loads(message.data.decode()))

    async def _disconnect(self):
        await self.broker.disconnect()
        await self.disconnected()

    def startup(self):
        """Called on startup/registration."""
        self.is_running = True
        # connect to broker
        asyncio.ensure_future(self._connect())

    def shutdown(self):
        """Called on shutdown/unregistration."""
        self.is_running = False
        asyncio.ensure_future(self._disconnect())

    async def connected(self):
        """Called when we are connected to the broker."""
        pass

    async def disconnected(self):
        """Called when we disconnect from the broker."""
        pass

    async def control(self, data):
        """Generic control interface. Implementation-dependent."""
        raise NotImplementedError()

    async def publish_state(self, data):
        self.broker.publish(self.topic + '/state', json.dumps(data).encode())

    def is_supported(self, device_type):
        return device_type in self.SUPPORTED_TYPES

    def get_name(self):
        return 'device:' + self.id


def get_device_handler(device_id: str, device_type: str, protocol: str, address: str, name: str) -> BaseDeviceHandler:
    """Returns an appropriate device handler for the given protocol and address."""
    module = importlib.import_module('.'+protocol, __name__)
    if module:
        schemes = getattr(module, 'schemes')
        if schemes:
            scheme_part, address_part = address.split(':', 1)
            if scheme_part in schemes:
                handler_class = schemes[scheme_part]
                return handler_class(device_id, device_type, protocol, address, name)
