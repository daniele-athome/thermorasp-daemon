# -*- coding: utf-8 -*-
"""The backend process."""

import asyncio

from . import app


async def backend():
    while app.is_running:
        print("BACKEND RUNNING")
        from thermostat.sensors import get_sensor_handler
        handler = get_sensor_handler('local', 'RND:')
        reading = handler.read('temperature')
        print(reading)
        await asyncio.sleep(5)


# noinspection PyUnusedLocal
@app.listener('before_server_start')
async def init_backend(sanic, loop):
    asyncio.ensure_future(backend(), loop=loop)
