# -*- coding: utf-8 -*-

import asyncio

from sanic import Sanic


app = Sanic(__name__)


async def backend():
    while app.is_running:
        await asyncio.sleep(5)
        print("BACKEND RUNNING")


@app.listener('before_server_start')
async def init_backend(sanic, loop):
    asyncio.ensure_future(backend(), loop=loop)


from . import controllers
