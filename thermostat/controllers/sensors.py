# -*- coding: utf-8 -*-
"""Sensors API."""

from sanic.request import Request
from sanic.response import json

from sqlalchemy.orm.exc import NoResultFound

from .. import app, errors
from ..database import scoped_session
from ..models import Sensor

SENSOR_STATUS_MAP = (
    'unknown',
    'registered',
    'active',
    'inactive',
)

SENSOR_DATA_MODE_MAP = (
    'active',
    'passive',
)


def serialize_sensor(sensor):
    return {
        'id': sensor.id,
        'type': sensor.sensor_type,
        'data_mode': SENSOR_DATA_MODE_MAP[sensor.data_mode],
        'protocol': sensor.protocol,
        'address': sensor.address,
        'status': SENSOR_STATUS_MAP[sensor.status]
    }


# noinspection PyUnusedLocal
@app.get('/sensors')
async def index(request: Request):
    """List all registered sensors."""

    with scoped_session(app.database) as session:
        stmt = Sensor.__table__.select()
        sensors = [serialize_sensor(s) for s in session.execute(stmt)]
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
        return json(serialize_sensor(sensor))


# noinspection PyUnusedLocal
@app.post('/sensors/unregister')
async def unregister(request: Request):
    """
    Request unregistration for a sensor. Either used by the sensor itself to unregister or by clients to remove sensors.
    """

    in_data = request.json
    with scoped_session(app.database) as session:
        try:
            sensor = session.query(Sensor).filter(Sensor.id == in_data['id']).one()
            session.delete(sensor)
            return json({
                'id': sensor.id,
                'status': 'unregistered',
            })
        except NoResultFound:
            raise errors.NotFoundError('Sensor not found.')
