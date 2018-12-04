# -*- coding: utf-8 -*-
"""General purpose behaviors."""

import logging
import hbmqtt.client as mqtt_client

from . import BaseBehavior
from ..models import eventlog


# TEST loggers
log = logging.getLogger("root")


class TargetTemperatureBehavior(BaseBehavior):
    """A base behavior for setting a target temperature."""

    def __init__(self, behavior_id: int, name: str, broker: mqtt_client.MQTTClient):
        BaseBehavior.__init__(self, behavior_id, name, broker)
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

    async def sensor_data(self, topic: str, data: dict):
        log.debug("TARGET got sensor data from {}: {}".format(topic, data))

    async def device_state(self, topic: str, data: dict):
        log.debug("TARGET got device state from {}: {}".format(topic, data))


def thermostat_control(log_source, context, device_id, target_temperature, cooling=True):
    """A simple thermostat function to decide wether to activate a device or not."""

    # immediately set the target temperature and device to show
    context.params['target_temperature'] = target_temperature
    context.params['target_device'] = device_id

    if 'temperature' not in context.last_reading:
        context.event_logger.event(eventlog.LEVEL_WARNING, log_source, 'action', 'last reading: (none), unable to proceed')
        return False

    target_device = context.devices[device_id]
    last_reading = round(context.last_reading['temperature']['_avg']['value'], 1)
    target_temperature = round(target_temperature, 1)
    if cooling:
        enabled = last_reading > target_temperature
    else:
        enabled = last_reading < target_temperature
    context.event_logger.event(eventlog.LEVEL_INFO, log_source, 'behavior:action',
                               'last reading: {}, target: {}, enabled: {}'
                               .format(last_reading, target_temperature, enabled))
    target_device.control(enabled=enabled)
    return True
