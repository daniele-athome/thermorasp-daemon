# -*- coding: utf-8 -*-
"""Behaviors API."""

from sanic.request import Request
from sanic.response import json

from .. import app, errors
from ..behaviors import get_behavior_handler_class

BEHAVIOR_ID_PREFIX = 'thermostat.behaviors.'


def extract_behavior_id(bcls):
    module_name = bcls.__module__
    if module_name.startswith(BEHAVIOR_ID_PREFIX):
        return module_name[len(BEHAVIOR_ID_PREFIX):] + '.' + bcls.__name__
    raise Exception('Invalid behavior class: ' + str(bcls))


def serialize_behavior(bcls):
    return {
        'id': extract_behavior_id(bcls),
        'config': bcls.get_config_schema(),
    }


# noinspection PyUnusedLocal
@app.get('/behaviors')
async def index(request: Request):
    """List all available behaviors."""
    # TODO
    raise errors.NotSupportedError('Not implemented.')


# noinspection PyUnusedLocal
@app.get('/behaviors/<behavior_id>')
async def get(request: Request, behavior_id: str):
    """Get a single behavior."""
    handler_class = get_behavior_handler_class(behavior_id)
    if not handler_class:
        raise errors.NotFoundError('Behavior not found.')
    return json(serialize_behavior(handler_class))
