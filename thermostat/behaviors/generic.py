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
        self.current_state = {}

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
        if self.device_state_received():
            await self._logic()
        else:
            logger.debug("TARGET device state not received yet")

    def device_state_received(self):
        for device in self.devices:
            if device not in self.current_state:
                return False
        return True

    async def device_state(self, topic: str, data: dict):
        await BaseBehavior.device_state(self, topic, data)
        logger.debug("TARGET got device state from {}: {}".format(topic, data))
        device = self.find_device_topic(topic)
        if device and topic[len(device):] == '/state':
            self.current_state[self.find_device_topic(topic)] = data
            if self.device_state_received():
                await self._logic()

    async def _logic(self):
        avg_temp = self.last_reading_avg('celsius')
        if avg_temp is None:
            logger.warning("TARGET no average temperature")
            app.eventlog.event(eventlog.LEVEL_WARNING, self.name, 'action', 'last reading: (none), unable to proceed')
            return

        logger.debug("TARGET average temperature: {}".format(avg_temp))

        last_reading = round(avg_temp * 2) / 2
        target_temperature = self.target_temperature
        for device in self.devices:
            if self.cooling:
                enabled = last_reading > target_temperature
            else:
                logger.debug("TARGET current device state: {}".format(self.current_state))
                offset = 0
                if device in self.current_state and self.current_state[device]['enabled']:
                    offset = 0.5
                enabled = last_reading < (target_temperature + offset)
                logger.debug("TARGET target: {}, current: {}, offset: {}".format(target_temperature, last_reading, offset))

            if device not in self.current_state or self.current_state[device]['enabled'] != enabled:
                app.eventlog.event(eventlog.LEVEL_INFO, self.name, 'behavior:action',
                                   'last reading: {}, target: {}, enabled: {}'
                                   .format(last_reading, target_temperature, enabled))
                await self.control_device(device, {'enabled': enabled})
