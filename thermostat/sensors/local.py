# -*- coding: utf-8 -*-
"""Protocols for local sensors (e.g. GPIO)."""

import os
from random import randint

import importlib.util
try:
    importlib.util.find_spec('RPi.GPIO')
    import RPi.GPIO as GPIO
    fakeSensors = False
except ImportError:
    from fake_rpi.RPi import GPIO as GPIO
    fakeSensors = True

# will skip W1ThermSensor modprobe call
os.environ['W1THERMSENSOR_NO_KERNEL_MODULE'] = '1'
from w1thermsensor import W1ThermSensor

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


class GPIOW1SensorHandler(BaseSensorHandler):
    """Raspberry sensor handler that reads from GPIO using 1-Wire protocol."""

    def __init__(self, address):
        BaseSensorHandler.__init__(self, address)

    def read(self, sensor_type):
        if sensor_type == 'temperature':
            if fakeSensors:
                # random temperature :D
                temp = 23
            else:
                sensor = W1ThermSensor(sensor_id=self.address)
                temp = sensor.get_temperature(unit=W1ThermSensor.DEGREES_C)

            # round it up to the nearest half since it's all we are interested in
            temp = round(temp * 2) / 2
            return {
                'value': temp,
                'unit': 'celsius'
            }
        else:
            raise errors.NotSupportedError('Only temperature is supported')


schemes = {
    'GPIOW1': GPIOW1SensorHandler,
    'RND': RandomSensorHandler,
}
