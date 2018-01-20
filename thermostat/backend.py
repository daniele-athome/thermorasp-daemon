# -*- coding: utf-8 -*-
"""The backend process."""

import logging
import asyncio
import datetime

from .database import scoped_session
from . import app
from .models import Sensor
from .models.sensors import store_reading
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
        log.debug("{}: {}".format(sensor_info['id'], reading))
        # store reading in database
        store_reading(sensor_info['id'], sensor_type, datetime.datetime.now(), reading['unit'], reading['value'])


async def backend():
    while app.is_running:
        print("BACKEND RUNNING")

        # read from passive temperature sensors
        read_passive_sensors('temperature')

        # TODO handle programs

        await asyncio.sleep(10)


# noinspection PyUnusedLocal
@app.listener('before_server_start')
async def init_backend(sanic, loop):
    asyncio.ensure_future(backend(), loop=loop)
