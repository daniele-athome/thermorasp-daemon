# -*- coding: utf-8 -*-
"""Sensors API."""

import datetime

from sanic.request import Request
from sanic.response import json

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import desc

from .. import app, errors
from ..database import scoped_session
from ..models.sensors import Sensor, Reading, get_last_readings, is_active_sensor

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


def serialize_sensor_reading(mreading):
    return {
        'sensor_id': mreading.sensor_id,
        'type': mreading.sensor_type,
        'timestamp': mreading.timestamp.isoformat(),
        'unit': mreading.unit,
        'value': mreading.value,
    }


# noinspection PyUnusedLocal
@app.get('/sensors')
async def index(request: Request):
    """List all registered sensors."""

    with scoped_session(app.database) as session:
        stmt = Sensor.__table__.select()
        sensors = [serialize_sensor(s) for s in session.execute(stmt)]
    return json(sensors)


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
        sensor.data_mode = SENSOR_DATA_MODE_MAP.index(in_data['data_mode'])
        sensor.protocol = in_data['protocol']
        sensor.address = in_data['address']
        sensor.status = Sensor.STATUS_UNKNOWN
        sensor = session.merge(sensor)
        return json(serialize_sensor(sensor), 201)


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


# noinspection PyUnusedLocal
@app.get('/sensors/reading')
async def reading(request: Request):
    """Reads the latest sensor reading for all sensors from the database."""

    if 'sensor_type' not in request.args:
        raise errors.NotFoundError('You must provide a sensor_type parameter')

    with scoped_session(app.database) as session:
        sensor_type = request.args['sensor_type'][0]
        return json([serialize_sensor_reading(latest) for latest in get_last_readings(session, sensor_type=sensor_type)])


# noinspection PyUnusedLocal
@app.get('/sensors/reading/<sensor_id>')
async def reading(request: Request, sensor_id: str):
    """Reads the latest sensor reading from the database."""

    with scoped_session(app.database) as session:
        latest = session.query(Reading).filter(Reading.sensor_id == sensor_id)\
            .order_by(desc(Reading.timestamp)).limit(1).one()
        return json(serialize_sensor_reading(latest))


@app.post('/sensors/reading')
async def reading(request: Request):
    """Adds a sensor reading to the database. Used by sensors to send data."""

    in_data = request.json
    with scoped_session(app.database) as session:
        if is_active_sensor(session, in_data['sensor_id']):
            mreading = Reading()
            mreading.sensor_id = in_data['sensor_id']
            mreading.sensor_type = in_data['type']
            mreading.unit = in_data['unit']
            mreading.value = in_data['value']
            if 'timestamp' in in_data:
                mreading.timestamp = in_data['timestamp']
            else:
                mreading.timestamp = datetime.datetime.now()
            session.add(mreading)
            return json(serialize_sensor_reading(mreading))
        else:
            raise errors.NotFoundError('Sensor not found.')
