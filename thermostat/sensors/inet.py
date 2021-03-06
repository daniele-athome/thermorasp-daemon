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

    def __init__(self, sensor_id: str, address: str, sensor_type: str, icon: str):
        BaseSensorHandler.__init__(self, sensor_id, address, sensor_type, icon)
        params = urllib_parse.parse_qs(address)
        self.last_temperature = None
        if params and 'interval' in params:
            self.interval = int(params['interval'][0])
        else:
            self.interval = self.DEFAULT_INTERVAL
        self.url = params['url'][0]

    async def connected(self):
        await self.timeout()
        self.start_timer(self.interval)

    async def timeout(self):
        if self.type == 'temperature':
            try:
                temp, unit = await asyncio.get_event_loop().run_in_executor(None, self._read)
            except ValueError:
                app.eventlog.event_exc(eventlog.LEVEL_WARNING, self.get_name(), 'exception')
                return

            if self.last_temperature is None or self.last_temperature != temp:
                self.last_temperature = temp
                await self.publish({
                    'value': self.last_temperature,
                    'unit': unit,
                    'timestamp': datetime.datetime.now().isoformat(),
                }, '/temperature', retain=True)

    def parse(self, data: dict):
        """Subclasses can override this for service specific response."""
        return float(data['value']), data['unit']

    def _read(self):
        try:
            r = requests.get(self.url)
            return self.parse(r.json())
        except requests.RequestException as e:
            raise ValueError('Connection error') from e
        except KeyError as e:
            raise ValueError('Invalid sensor data') from e


class OpenWeatherMapSensorHandler(HTTPSensorHandler):
    """OpenWeatherMap HTTP sensor handler. Use your own API key."""

    protocol = 'HTTP-OWM'
    DEFAULT_INTERVAL = 1800
    URL_TEMPLATE = 'https://api.openweathermap.org/data/2.5/weather?APPID={}&id={}&units=metric'

    def __init__(self, sensor_id: str, address: str, sensor_type: str, icon: str):
        try:
            HTTPSensorHandler.__init__(self, sensor_id, address, sensor_type, icon)
        except KeyError:
            # url parameter is optional
            pass
        params = urllib_parse.parse_qs(address)
        self.url = self.URL_TEMPLATE.format(params['api_key'][0], params['city_id'][0])

    def parse(self, data: dict):
        try:
            return float(data['main']['temp']), 'celsius'
        except KeyError as e:
            raise ValueError('Invalid sensor data') from e


schemes = {
    HTTPSensorHandler.protocol: HTTPSensorHandler,
    OpenWeatherMapSensorHandler.protocol: OpenWeatherMapSensorHandler,
}
