# -*- coding: utf-8 -*-
"""Schedules API."""

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
            raise errors.NotFoundError('Schedule not found.')


# noinspection PyUnusedLocal
@app.get('/schedules/active')
async def active(request: Request):
    """Get the active schedule."""

    if app.backend.schedule is None:
        raise errors.NotFoundError('No active schedule.')

    return json(app.backend.schedule.schedule)


# noinspection PyUnusedLocal
@app.put('/schedules/active')
async def update_active(request: Request):
    """Alter the active schedule without persisting anything to the database."""

    if app.backend.schedule is None:
        raise errors.NotFoundError('No active schedule.')

    data = request.json
    if 'behaviors' in data:
        await app.backend.update_operating_schedule(data['behaviors'])

    return no_content()


# noinspection PyUnusedLocal
@app.put('/schedules/active/<behavior_id:int>')
async def update_config_active(request: Request, behavior_id: int):
    """Alter a single behavior in the active schedule without persisting anything to the database."""

    if app.backend.schedule is None:
        raise errors.NotFoundError('No active schedule.')

    data = request.json
    await app.backend.update_operating_behavior(behavior_id, data)

    return no_content()


# noinspection PyUnusedLocal
@app.put('/schedules/active/rollback')
async def rollback_active(request: Request):
    """Rollback any modification to the active schedule."""

    if app.backend.schedule is None:
        raise errors.NotFoundError('No active schedule.')

    # reload the same
    await app.backend.set_operating_schedule(app.backend.schedule.id)

    return no_content()


# noinspection PyUnusedLocal
@app.put('/schedules/active/commit')
async def commit_active(request: Request):
    """Persist the active schedule to the database."""

    # TODO might be implemented using create
    raise errors.NotSupportedError('Not implemented yet.')
