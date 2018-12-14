# -*- coding: utf-8 -*-
"""General purpose behaviors."""

import hbmqtt.client as mqtt_client

from sanic.log import logger

from . import BaseBehavior
from .. import app
from ..models import eventlog


class TargetTemperatureBehavior(BaseBehavior):
    """A base behavior for setting a target temperature."""

    def __init__(self, behavior_id: int, name: str, sensors: list, devices: list, broker: mqtt_client.MQTTClient):
        BaseBehavior.__init__(self, behavior_id, name, sensors, devices, broker)
        self.cooling = None
        self.target_temperature = None

    def _init(self, config):
        self.cooling = 'mode' in config and config['mode'] == 'cooling'
        self.target_temperature = config['target_temperature']

    @classmethod
    def get_config_schema(cls):
        return {
            'mode': {
                'label': 'Heating/Cooling',
                'description': 'Heating or cooling?',
                'type': 'str',
                'form_type': 'values_single',
                'values': ['healing', 'cooling'],
            },
            'target_temperature': {
                'label': 'Target temperature',
                'description': 'The temperature to maintain in the environment.',
                'type': 'float:1',
                'form_type': 'power_handle',
            },
        }

    async def startup(self, config):
        self._init(config)

    async def shutdown(self):
        pass

    async def update(self, config):
        self._init(config)

    async def timer(self):
        logger.debug("TARGET got timer")
        await self._logic()

    async def sensor_data(self, topic: str, data: dict):
        await BaseBehavior.sensor_data(self, topic, data)
        logger.debug("TARGET got sensor data from {}: {}".format(topic, data))
        logger.debug("TARGET devices: {}".format(self.devices))
        await self._logic()

    async def device_state(self, topic: str, data: dict):
        await BaseBehavior.device_state(self, topic, data)
        logger.debug("TARGET got device state from {}: {}".format(topic, data))

    async def _logic(self):
        avg_temp = self.last_reading_avg('celsius')
        if avg_temp is None:
            logger.warning("TARGET no average temperature")
            app.eventlog.event(eventlog.LEVEL_WARNING, self.name, 'action', 'last reading: (none), unable to proceed')
            return

        logger.debug("TARGET average temperature: {}".format(avg_temp))

        last_reading = round(avg_temp, 1)
        target_temperature = round(self.target_temperature, 1)
        if self.cooling:
            enabled = last_reading > target_temperature
        else:
            enabled = last_reading < target_temperature
        app.eventlog.event(eventlog.LEVEL_INFO, self.name, 'behavior:action',
                           'last reading: {}, target: {}, enabled: {}'
                           .format(last_reading, target_temperature, enabled))
        for device in self.devices:
            await self.control_device(device, {'enabled': enabled})
