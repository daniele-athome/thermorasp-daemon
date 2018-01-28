# -*- coding: utf-8 -*-
"""General purpose behaviors."""

from . import BaseBehavior
from ..models import eventlog


class ForceTemperatureBehavior(BaseBehavior):
    """A behavior to always keep the temperature at a certain level."""

    def __init__(self, behavior_id, config=None):
        BaseBehavior.__init__(self, behavior_id, config)
        self.target_device_id = config['target_device_id']
        self.target_temperature = config['target_temperature']

    def get_config_schema(self):
        return {
            'target_device_id': {
                'label': 'Target device id',
                'description': 'The device to control.',
                'type': 'str',
                'form_type': 'device_single',
            },
            'target_temperature': {
                'label': 'Target temperature',
                'description': 'The temperature to maintain in the environment.',
                'type': 'float',
                'form_type': 'power_handle',
            },
        }

    def execute(self, context):
        if 'temperature' not in context.last_reading:
            eventlog.event(eventlog.LEVEL_WARNING, self.id, 'action', 'last reading: (none), unable to proceed')
            return False

        target_device = context.devices[self.target_device_id]

        last_reading = context.last_reading['temperature']['_avg']['value']
        enabled = last_reading < self.target_temperature
        eventlog.event(eventlog.LEVEL_INFO, self.id, 'action', 'last reading: {}, target: {}, enabled: {}'
                       .format(last_reading, self.target_temperature, enabled))
        target_device.control(enabled=enabled)

        # don't proceed with the chain
        return False
