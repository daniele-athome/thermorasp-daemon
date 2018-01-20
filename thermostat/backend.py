# -*- coding: utf-8 -*-
"""The backend process."""

import asyncio

from .database import scoped_session
from . import app
from .models import Sensor
from .sensors import get_sensor_handler


def get_passive_sensors():
    with scoped_session(app.database) as session:
        stmt = Sensor.__table__.select().where(Sensor.data_mode == Sensor.DATA_MODE_PASSIVE)
        return [dict(s) for s in session.execute(stmt)]


def read_passive_sensors():
    pasv_sensors = get_passive_sensors()
    for sensor_info in pasv_sensors:
        handler = get_sensor_handler(sensor_info['protocol'], sensor_info['address'])
        reading = handler.read('temperature')
        print("{}: {}".format(sensor_info['id'], reading))


async def backend():
    while app.is_running:
        print("BACKEND RUNNING")

        # read from passive sensors
        read_passive_sensors()

        # TODO handle programs

        await asyncio.sleep(10)


# noinspection PyUnusedLocal
@app.listener('before_server_start')
async def init_backend(sanic, loop):
    asyncio.ensure_future(backend(), loop=loop)
