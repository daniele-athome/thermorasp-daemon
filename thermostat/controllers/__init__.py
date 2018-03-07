# -*- coding: utf-8 -*-
"""Views and routes of the API."""

from sanic.request import Request
from sanic.response import json, html, HTTPResponse

from .. import app, errors


# noinspection PyUnusedLocal
@app.route('/')
async def index(request: Request):
    """Root page with greeting text."""
    return html('<!DOCTYPE html><html><head><title>Smart Thermostat</title></head>'
                '<body><h1>This is the thermostat speaking!</h1></body></html>')


# noinspection PyUnusedLocal
@app.exception(errors.NotFoundError)
async def on_exception(request: Request, exception: errors.NotFoundError):
    error = {'error': 'not-found', 'message': str(exception)}
    return json(error, getattr(exception, 'status_code', 404))


# noinspection PyUnusedLocal
@app.exception(Exception)
async def on_exception(request: Request, exception: Exception):
    error = {'error': exception.__class__.__name__, 'message': str(exception)}
    return json(error, getattr(exception, 'status_code', 500))


def no_content(status=204, headers=None):
    return HTTPResponse(status=status, headers=headers)


# import other controllers
from . import sensors, devices, pipelines, behaviors, eventlog
