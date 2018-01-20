# -*- coding: utf-8 -*-
"""Sensors API."""

from sanic.request import Request
from sanic.response import json

from thermostat import app
from thermostat.database import scoped_session
from thermostat.models import Sensor


# noinspection PyUnusedLocal
@app.get('/sensors')
async def index(request: Request):
    """List all registered sensors."""

    with scoped_session(app.database) as session:
        stmt = Sensor.__table__.select()
        sensors = [dict(u) for u in session.execute(stmt)]
    return json(sensors)


# noinspection PyUnusedLocal
@app.post('/sensors/register')
async def register(request: Request):
    """
    Request registration for a sensor. Either used by the sensor itself to register or by clients to add sensors.
    """

    in_data = request.json
    with scoped_session(app.database) as session:
        sensor = Sensor()
        sensor.id = in_data['id']
        sensor.sensor_type = in_data['type']
        sensor.data_mode = in_data['data_mode']
        sensor.protocol = in_data['protocol']
        sensor.address = in_data['address']
        sensor.status = Sensor.STATUS_UNKNOWN
        sensor = session.merge(sensor)
        return json({
            'id': sensor.id,
            'type': sensor.sensor_type,
            'data_mode': sensor.data_mode,
            'protocol': sensor.protocol,
            'address': sensor.address
        })


# noinspection PyUnusedLocal
@app.route('/sensors/unregister')
async def unregister(request: Request):
    """
    Request unregistration for a sensor. Either used by the sensor itself to unregister or by clients to remove sensors.
    """
    # TODO
    raise NotImplementedError()
