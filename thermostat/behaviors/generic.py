# -*- coding: utf-8 -*-
"""General purpose behaviors."""

from . import BaseBehavior


class ForceTemperatureBehavior(BaseBehavior):
    """A behavior to always keep the temperature at a certain level."""

    def __init__(self, behavior_id, behavior_type, config=None):
        BaseBehavior.__init__(behavior_id, behavior_type, config)
        self.target_device_id = config['target_device_id']
        self.target_device_type = config['target_device_type']
        self.target_temperature = config['target_temperature']

    def get_config_schema(self):
        return {
            'target_device_id': {
                'label': 'Target device id',
                'description': 'The device to control.',
                'type': 'str',
                'form_type': 'device_single',
            },
            'target_device_type': {
                'label': 'Target device type',
                'description': 'The device type to control.',
                'type': 'str',
                'form_type': 'device_type_single',
            },
            'target_temperature': {
                'label': 'Target temperature',
                'description': 'The temperature to maintain in the environment.',
                'type': 'float',
                'form_type': 'power_handle',
            },
        }

    def execute(self, context):
        target_device = context.devices[self.target_device_id]

        last_reading = context.last_reading['_avg']
        enabled = last_reading < self.target_temperature
        target_device.control(self.target_device_type, {'enabled': enabled})

        # don't proceed with the chain
        return False
