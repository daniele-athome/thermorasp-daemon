# -*- coding: utf-8 -*-
"""General purpose behaviors."""

import logging

from . import BaseBehavior

# TEST loggers
log = logging.getLogger("root")


class ForceTemperatureBehavior(BaseBehavior):
    """A behavior to always keep the temperature at a certain level."""

    def __init__(self, behavior_id, config=None):
        BaseBehavior.__init__(self, behavior_id, config)
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

        last_reading = context.last_reading['temperature']['_avg']['value']
        enabled = last_reading < self.target_temperature
        log.debug('ForceThermostat enabled: {}'.format(enabled))
        target_device.control(self.target_device_type, {'enabled': enabled})

        # don't proceed with the chain
        return False
