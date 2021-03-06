# -*- coding: utf-8 -*-
"""Sensors API."""

import datetime

from sanic.request import Request
from sanic.response import json

from .. import app, errors
from ..database import scoped_session
from ..models.sensors import Reading


SENSOR_STATUS_MAP = (
    'unknown',
    'registered',
    'active',
    'inactive',
)


def serialize_sensor(sensor):
    return {
        'id': sensor.id,
        'type': sensor.type,
        'protocol': sensor.protocol,
        'address': sensor.address,
        'icon': sensor.icon,
        'topic': sensor.topic,
    }


def serialize_sensor_reading(sensor_id, mreading):
    return {
        'sensor_id': sensor_id,
        'type': mreading['type'],
        'timestamp': mreading['timestamp'].isoformat(),
        'unit': mreading['unit'],
        'value': mreading['value'],
    }


def serialize_sensor_reading_db(mreading: Reading):
    return {
        'sensor_id': mreading.sensor_id,
        'type': mreading.sensor_type,
        'timestamp': mreading.timestamp.isoformat(),
        'unit': mreading.unit,
        'value': float(mreading.value),
    }


# noinspection PyUnusedLocal
@app.get('/sensors')
async def index(request: Request):
    """List all registered sensors."""

    return json([serialize_sensor(d) for d in app.backend.sensors.values()])


# noinspection PyUnusedLocal
@app.get('/sensors/topic/<sensor_id>')
async def topic(request: Request, sensor_id: str):
    """Get the base topic for a given sensor."""

    return json(app.backend.sensors[sensor_id].topic)


@app.post('/sensors/register')
async def register(request: Request):
    """
    Request registration for a sensor. Either used by the sensor itself to register or by clients to add sensors.
    """

    in_data = request.json
    app.backend.sensors.register(in_data['id'], in_data['protocol'], in_data['address'], in_data['type'], in_data['icon'])
    return json({'id': in_data['id']}, 201)


@app.post('/sensors/unregister')
async def unregister(request: Request):
    """
    Request unregistration for a sensor. Either used by the sensor itself to unregister or by clients to remove sensors.
    """

    in_data = request.json
    if app.backend.sensors.unregister(in_data['id']):
        return json({'id': in_data['id']})
    else:
        raise errors.NotFoundError('Sensor not found.')


# noinspection PyUnusedLocal
@app.get('/sensors/reading')
async def reading(request: Request):
    """Reads the latest sensor reading for all sensors from the database."""

    if 'sensor_type' in request.args:
        sensor_type = request.args['sensor_type'][0]
    else:
        sensor_type = None

    readings = app.backend.sensors.get_last_readings(sensor_type=sensor_type)
    return json([serialize_sensor_reading(sensor_id, latest) for sensor_id, latest in readings.items()])


# noinspection PyUnusedLocal
@app.get('/sensors/reading/<sensor_id>')
async def reading(request: Request, sensor_id: str):
    """Reads the latest sensor reading from the database."""

    r = app.backend.sensors.get_last_reading(sensor_id)
    if r:
        return json(serialize_sensor_reading(sensor_id, r))
    else:
        return json({})


@app.get('/sensors/readings')
async def reading_list(request: Request):
    """Reads sensor readings from the database."""

    if 'sensor_type' in request.args:
        sensor_type = request.args['sensor_type'][0]
    else:
        sensor_type = None

    date_from = datetime.datetime.strptime(request.args['from'][0], '%Y-%m-%dT%H:%M:%S')
    date_to = datetime.datetime.strptime(request.args['to'][0], '%Y-%m-%dT%H:%M:%S')

    with scoped_session(app.database) as session:
        query = session.query(Reading)
        if sensor_type:
            query = query.filter(Reading.sensor_type == sensor_type)

        readings = query.filter(Reading.timestamp.between(date_from, date_to)) \
                        .order_by(Reading.timestamp) \
                        .all()

        return json([serialize_sensor_reading_db(r) for r in readings])
