# -*- coding: utf-8 -*-
"""General purpose behaviors."""

from . import BaseBehavior
from ..models import eventlog


class TargetTemperatureBehavior(BaseBehavior):
    """
    A behavior to alter the target temperature in the chain to a certain level.
    Behaviors will need to read target_temperature from the context parameters.
    """

    def __init__(self, behavior_id, config=None):
        BaseBehavior.__init__(self, behavior_id, config)
        self.target_temperature = config['target_temperature']

    def get_config_schema(self):
        return {
            'target_temperature': {
                'label': 'Target temperature',
                'description': 'The temperature to maintain in the environment.',
                'type': 'float:1',
                'form_type': 'power_handle',
            },
        }

    def execute(self, context):
        # behaviors supporting this parameter will use it
        context.params['target_temperature'] = self.target_temperature
        return True


class ForceTemperatureBehavior(BaseBehavior):
    """A behavior to always keep the temperature at a certain level."""

    def __init__(self, behavior_id, config=None):
        BaseBehavior.__init__(self, behavior_id, config)
        self.target_device_id = config['target_device_id']
        self.cooling = config['mode'] == 'cooling'
        self.target_temperature = config['target_temperature']

    def get_config_schema(self):
        return {
            'target_device_id': {
                'label': 'Target device id',
                'description': 'The device to control.',
                'type': 'str',
                'form_type': 'device_single',
            },
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

    def execute(self, context):
        thermostat_control(self.id, context, self.target_device_id, self.target_temperature, self.cooling)
        # don't proceed with the chain
        return False


def thermostat_control(log_source, context, device_id, target_temperature, cooling=True):
    """A simple thermostat function to decide wether to activate a device or not."""

    # immediately set the target temperature to show
    context.params['target_temperature'] = target_temperature

    if 'temperature' not in context.last_reading:
        eventlog.event(eventlog.LEVEL_WARNING, log_source, 'action', 'last reading: (none), unable to proceed')
        return False

    target_device = context.devices[device_id]
    last_reading = context.last_reading['temperature']['_avg']['value']
    if cooling:
        enabled = last_reading > target_temperature
    else:
        enabled = last_reading < target_temperature
    eventlog.event(eventlog.LEVEL_INFO, log_source, 'behavior:action', 'last reading: {}, target: {}, enabled: {}'
                   .format(last_reading, target_temperature, enabled))
    target_device.control(enabled=enabled)
    return True
