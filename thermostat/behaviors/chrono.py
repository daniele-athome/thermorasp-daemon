# -*- coding: utf-8 -*-
"""Time-based behaviors."""

import calendar
import datetime

from . import BaseBehavior
from .generic import TemperatureBaseBehavior, ForceTemperatureBehavior, thermostat_control


class CronBehavior(BaseBehavior):
    """Base interface for cron-based behaviors."""

    def __init__(self, behavior_id, config=None):
        BaseBehavior.__init__(self, behavior_id, config)
        self.crons = []

    def get_config_schema(self):
        """Must be implemented by child classes."""
        raise NotImplementedError()

    def add_cron(self, expression, data=None):
        """Adds a trigger that will execute if the given cron expression is activated."""
        self.crons.append({
            'expression': expression,
            'data': data
        })

    def execute(self, context):
        # TODO
        pass

    def trigger(self, context):
        """Overridden by child classes to implement actual behavior."""
        raise NotImplementedError()


class WeeklyProgramBehavior(BaseBehavior):
    """Classic weekly program behavior."""

    def __init__(self, behavior_id, config=None):
        BaseBehavior.__init__(self, behavior_id, config)
        self.target_device_id = config['target_device_id']
        self.cooling = config['mode'] == 'cooling'
        self.time_slices = []
        for k, v in config.items():
            if k.startswith('day'):
                weekday = int(k[3:])

                for jobspec in v:
                    time_start = datetime.datetime.strptime(jobspec['time_start'], '%H:%M')
                    time_start_sec = self.get_time_seconds(weekday, time_start.hour, time_start.minute)
                    self.time_slices.append({'stamp': time_start_sec, 'target': jobspec['target_temperature']})

        self.time_slices.sort(key=lambda sl: sl['stamp'], reverse=True)

    @staticmethod
    def get_time_seconds(weekday, hour, minute, second=0):
        return (weekday * 24 * 60 * 60) + \
               (hour * 60 * 60) + \
               (minute * 60) + \
               second

    def get_config_schema(self):
        schema = {
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
        }

        for i in range(0, len(calendar.day_name)):
            weekday = calendar.day_name[i]
            schema['day%d' % i] = {
                'label': weekday,
                'description': 'Program to use on {}'.format(weekday),
                'type': 'object_array',
                'items': {
                    'time_start': {
                        'label': 'Start time',
                        'description': 'At what time set this temperature.',
                        'type': 'time:%H:%M',
                        'form_type': 'time',
                    },
                    'target_temperature': {
                        'label': 'Target temperature',
                        'description': 'The temperature to maintain in the environment.',
                        'type': 'float:1',
                        'form_type': 'power_handle',
                    },
                }
            }

        return schema

    def execute(self, context):
        now = datetime.datetime.now()
        now_sec = self.get_time_seconds(now.weekday(), now.hour, now.minute, now.second)

        selected_slice = self.time_slices[0]
        for sli in self.time_slices:
            if sli['stamp'] <= now_sec:
                selected_slice = sli
                break

        target_temperature = selected_slice['target']
        thermostat_control(self.id, context, self.target_device_id, target_temperature, self.cooling)
        # the chain stops here
        return False


class ForceTemperatureUntilBehavior(ForceTemperatureBehavior):
    """A behavior to keep the temperature at a certain level until some time in the same day."""

    def __init__(self, behavior_id, config=None):
        ForceTemperatureBehavior.__init__(self, behavior_id, config)
        self.time = datetime.datetime.strptime(config['time'], '%H:%M')

    def get_config_schema(self):
        cfg = ForceTemperatureBehavior.get_config_schema(self)
        cfg['time'] = {
            'label': 'End time',
            'description': 'Until what time set this temperature.',
            'type': 'time:%H:%M',
            'form_type': 'time',
        }
        return cfg

    def execute(self, context):
        now = datetime.datetime.now()
        until = datetime.datetime(now.year, now.month, now.day, self.time.hour, self.time.minute)

        if now.timestamp() >= until.timestamp():
            context.delete_self()
            # go ahead with the next behavior since we are removing ourselves
            return True
        else:
            return ForceTemperatureBehavior.execute(self, context)
