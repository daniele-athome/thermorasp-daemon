# -*- coding: utf-8 -*-
"""Protocols for local sensors (e.g. GPIO)."""

import datetime
import asyncio
import os
import logging
from random import randint
import urllib.parse as urllib_parse

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


# TEST loggers
log = logging.getLogger("root")


class RandomSensorHandler(BaseSensorHandler):
    """A sensor handler that returns random values for various sensor types."""

    DEFAULT_INTERVAL = 60

    def __init__(self, sensor_id: str, address: str):
        BaseSensorHandler.__init__(self, sensor_id, address)
        params = urllib_parse.parse_qs(address)
        self.last_temperature = None
        if params and 'interval' in params:
            self.interval = int(params['interval'][0])
        else:
            self.interval = self.DEFAULT_INTERVAL

    def startup(self):
        BaseSensorHandler.startup(self)

    async def connected(self):
        await self.timeout()
        self.start_timer(self.interval)

    async def timeout(self):
        temp = randint(-10, 40)
        if self.last_temperature is None or self.last_temperature != temp:
            self.last_temperature = temp
            await self.publish({
                'value': self.last_temperature,
                'unit': 'celsius',
                'timestamp': datetime.datetime.now().isoformat(),
            }, '/temperature', retain=True)
            await self.publish({
                'value': randint(5, 98),
                'unit': 'percent',
                'timestamp': datetime.datetime.now().isoformat(),
            }, '/battery', retain=True)


class GPIOW1SensorHandler(BaseSensorHandler):
    """Raspberry sensor handler that reads from GPIO using 1-Wire protocol."""

    DEFAULT_INTERVAL = 60

    def __init__(self, sensor_id: str, address: str):
        BaseSensorHandler.__init__(self, sensor_id, address)
        params = urllib_parse.parse_qs(address)
        self.last_temperature = None
        if params and 'interval' in params:
            self.interval = int(params['interval'][0])
        else:
            self.interval = self.DEFAULT_INTERVAL

    def startup(self):
        BaseSensorHandler.startup(self)

    async def connected(self):
        await self.timeout()
        self.start_timer(self.interval)

    async def timeout(self):
        temp = await asyncio.get_event_loop().run_in_executor(None, self._read)
        if self.last_temperature is None or self.last_temperature != temp:
            self.last_temperature = temp
            await self.publish({
                'value': self.last_temperature,
                'unit': 'celsius',
                'timestamp': datetime.datetime.now().isoformat(),
            }, '/temperature', retain=True)

    def _read(self):
        if fakeSensors:
            # random temperature :D
            temp = randint(-10, 40)
        else:
            sensor = W1ThermSensor(sensor_id=self.address)
            temp = sensor.get_temperature(unit=W1ThermSensor.DEGREES_C)

        # round it up to the nearest half since it's all we are interested in
        return round(temp * 2) / 2


schemes = {
    'GPIOW1': GPIOW1SensorHandler,
    'RND': RandomSensorHandler,
}
