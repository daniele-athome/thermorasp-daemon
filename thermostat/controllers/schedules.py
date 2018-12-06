# -*- coding: utf-8 -*-
"""Pipelines API."""

from json import loads as json_loads
from json import dumps as json_dumps

from sqlalchemy.orm.exc import NoResultFound

from sanic.request import Request
from sanic.response import json

from . import no_content
from .. import app, errors
from ..database import scoped_session
from ..models import Schedule, Behavior


# noinspection PyTypeChecker
def serialize_schedule_behavior(b: Behavior):
    return {
        'id': b.id,
        'name': b.behavior_name,
        'order': b.behavior_order,
        'start': b.start_time,
        'end': b.end_time,
        'config': json_loads(b.config),
        'sensors': [s.sensor_id for s in b.sensors],
        'devices': [d.device_id for d in b.devices],
    }


# noinspection PyTypeChecker
def serialize_schedule(s: Schedule):
    return {
        'id': s.id,
        'name': s.name,
        'description': s.description,
        'enabled': s.enabled > 0,
        'behaviors': [serialize_schedule_behavior(b) for b in s.behaviors],
    }


# noinspection PyUnusedLocal
@app.get('/schedules')
async def index(request: Request):
    """List all registered schedules."""

    with scoped_session(app.database) as session:
        schedules = [serialize_schedule(s) for s in session.query(Schedule).all()]
    return json(schedules)


# noinspection PyUnusedLocal
@app.get('/schedules/<schedule_id>')
async def get(request: Request, schedule_id: int):
    """Get the requested schedule."""

    with scoped_session(app.database) as session:
        try:
            return json(serialize_schedule(session.query(Schedule).filter(Schedule.id == schedule_id).one()))
        except NoResultFound:
            raise errors.NotFoundError('Pipeline not found.')
