# -*- coding: utf-8 -*-
"""The backend process."""

import sys
import logging
import asyncio
import datetime

from .database import scoped_session
from . import app, devices
from .models import Sensor
from .models.sensors import store_reading
from .models import eventlog
from .sensors import get_sensor_handler


# TEST loggers
log = logging.getLogger("root")


def get_passive_sensors():
    with scoped_session(app.database) as session:
        stmt = Sensor.__table__.select().where(Sensor.data_mode == Sensor.DATA_MODE_PASSIVE)
        return [dict(s) for s in session.execute(stmt)]


def read_passive_sensors(sensor_type):
    pasv_sensors = get_passive_sensors()
    for sensor_info in pasv_sensors:
        handler = get_sensor_handler(sensor_info['protocol'], sensor_info['address'])
        reading = handler.read(sensor_type)
        log.debug("%s: %s", sensor_info['id'], reading)
        # store reading in database
        store_reading(sensor_info['id'], sensor_type, datetime.datetime.now(), reading['unit'], reading['value'])


def backend_ops():
    """All backend cycle operations are here."""
    # read from passive temperature sensors
    read_passive_sensors('temperature')

    # TODO handle programs


# noinspection PyBroadException
async def backend():
    while app.is_running:
        log.debug("BACKEND RUNNING")

        try:
            backend_ops()
        except:
            log.error('Unexpected error:', exc_info=sys.exc_info())
            eventlog.event_exc(eventlog.LEVEL_ERROR, 'backend', 'exception')

        await asyncio.sleep(app.config['BACKEND_INTERVAL'])


# noinspection PyUnusedLocal
@app.listener('before_server_start')
async def init_backend(sanic, loop):
    devices.init()
    asyncio.ensure_future(backend(), loop=loop)
