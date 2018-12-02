# -*- coding: utf-8 -*-
"""Protocols for remote sensors (mainly TCP/IP)."""

import requests

from . import BaseSensorHandler
from .. import errors


# FIXME must be ported to the new API
class HTTPSensorHandler(BaseSensorHandler):
    """A sensor handler that requests data to a HTTP endpoint."""

    def __init__(self, sensor_id: str, address: str):
        BaseSensorHandler.__init__(self, sensor_id, address)

    def read(self, sensor_type):
        if sensor_type == 'temperature':
            r = requests.get(self.address)
            data = r.json()
            try:
                return {
                    'value': float(data['value']),
                    'unit': data['unit']
                }
            except KeyError:
                raise ValueError('Invalid sensor data')
        else:
            raise errors.NotSupportedError('Only temperature is supported')


schemes = {
    'HTTP': HTTPSensorHandler,
}
