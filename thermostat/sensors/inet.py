# -*- coding: utf-8 -*-
"""Protocols for remote sensors (mainly TCP/IP)."""

import asyncio
import requests
import datetime
import urllib.parse as urllib_parse

from . import BaseSensorHandler
from .. import app
from ..models import eventlog


class HTTPSensorHandler(BaseSensorHandler):
    """A sensor handler that requests data to a HTTP endpoint."""

    protocol = 'HTTP'
    DEFAULT_INTERVAL = 60

    def __init__(self, sensor_id: str, address: str, sensor_type: str):
        BaseSensorHandler.__init__(self, sensor_id, address, sensor_type)
        params = urllib_parse.parse_qs(address)
        self.last_temperature = None
        if params and 'interval' in params:
            self.interval = int(params['interval'][0])
        else:
            self.interval = self.DEFAULT_INTERVAL

    async def connected(self):
        await self.timeout()
        self.start_timer(self.interval)

    async def timeout(self):
        if self.type == 'temperature':
            try:
                temp, unit = await asyncio.get_event_loop().run_in_executor(None, self._read)
            except ValueError:
                app.eventlog.event_exc(eventlog.LEVEL_WARNING, self.id, 'exception')
                return

            if self.last_temperature is None or self.last_temperature != temp:
                self.last_temperature = temp
                await self.publish({
                    'value': self.last_temperature,
                    'unit': unit,
                    'timestamp': datetime.datetime.now().isoformat(),
                }, '/temperature', retain=True)

    def _read(self):
        try:
            r = requests.get(self.address)
            data = r.json()
            return float(data['value']), data['unit']
        except requests.RequestException as e:
            raise ValueError('Connection error') from e
        except KeyError as e:
            raise ValueError('Invalid sensor data') from e


schemes = {
    HTTPSensorHandler.protocol: HTTPSensorHandler,
}
