# -*- coding: utf-8 -*-
"""Views and routes of the API."""

from sanic.request import Request
from sanic.response import json
from sanic.response import text
from sanic.response import html

from thermostat import app


# noinspection PyUnusedLocal
@app.route('/')
async def index(request: Request):
    """Root page with greeting text."""
    return html('<!DOCTYPE html><html><head><title>Smart Thermostat</title></head>'
                '<body><h1>This is the thermostat speaking!</h1></body></html>')


# noinspection PyUnusedLocal
@app.exception(Exception)
async def on_exception(request: Request, exception: Exception):
    error = {'error': exception.__class__.__name__, 'message': str(exception)}
    return json(error, getattr(exception, 'status_code', 500))
