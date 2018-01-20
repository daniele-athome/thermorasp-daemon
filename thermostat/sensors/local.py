# -*- coding: utf-8 -*-
"""Protocols for local sensors (e.g. GPIO)."""

from random import randint

from . import BaseSensorHandler
from .. import errors


class RandomSensorHandler(BaseSensorHandler):
    """A sensor handler that returns random values for various sensor types."""

    def __init__(self, address):
        BaseSensorHandler.__init__(self, address)

    def read(self, sensor_type):
        if sensor_type == 'temperature':
            return {
                'value': randint(-10, 40),
                'unit': 'celsius'
            }
        else:
            raise errors.NotSupportedError('Only temperature is supported')


class GPIOSensorHandler(BaseSensorHandler):
    """Raspberry sensor handler that reads from GPIO."""

    def __init__(self, address):
        BaseSensorHandler.__init__(self, address)

    # TODO


schemes = {
    'GPIO': GPIOSensorHandler,
    'RND': RandomSensorHandler,
}
