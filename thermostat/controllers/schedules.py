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
        'start_time': b.start_time,
        'end_time': b.end_time,
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
@app.get('/schedules/active/behavior')
async def active(request: Request):
    """Get the active behavior."""

    if app.backend.schedule is None:
        raise errors.NotFoundError('No active schedule.')
    if app.backend.schedule.behavior_def is None:
        raise errors.NotFoundError('No active behavior.')

    return json(app.backend.schedule.behavior_def)


# noinspection PyUnusedLocal
@app.put('/schedules/active')
async def update_active(request: Request):
    """Alter the active schedule without persisting anything to the database."""

    if app.backend.schedule is None:
        raise errors.NotFoundError('No active schedule.')

    data = request.json
    if 'behaviors' in data:
        await app.backend.update_operating_schedule(data)

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
@app.post('/schedules/active/volatile')
async def set_active_volatile(request: Request):
    """
    Activate a new volatile behavior that overrides the current one.
    The behavior will be discarded when it goes out of time range.
    """

    data = request.json
    await app.backend.set_volatile_behavior(data)

    return no_content()


# noinspection PyUnusedLocal
@app.put('/schedules/active/rollback')
async def rollback_active(request: Request):
    """Rollback any modification to the active schedule."""

    if app.backend.schedule is None:
        raise errors.NotFoundError('No active schedule.')

    # reload the same
    await app.backend.set_operating_schedule(app.backend.schedule.schedule['id'])

    return no_content()


# noinspection PyUnusedLocal
@app.post('/schedules')
async def create(request: Request):
    """Creates a schedule."""

    data = request.json
    new_id = None
    new_enabled = False
    with scoped_session(app.database) as session:
        sched = Schedule()
        sched.name = data['name']
        if 'description' in data:
            sched.description = data['description']
        if 'enabled' in data:
            sched.enabled = data['enabled']
        if 'behaviors' in data:
            sched.behaviors = []
            for data_behavior in data['behaviors']:
                beh = Behavior()
                beh.behavior_name = data_behavior['name']
                beh.behavior_order = data_behavior['order']
                beh.start_time = data_behavior['start_time']
                beh.end_time = data_behavior['end_time']
                beh.config = json_dumps(data_behavior['config'])
                if 'sensors' in data_behavior:
                    beh.sensors = data_behavior['sensors']
                if 'devices' in data_behavior:
                    beh.devices = data_behavior['devices']
                sched.behaviors.append(beh)
        session.add(sched)
        session.flush()
        new_enabled = sched.enabled
        new_id = sched.id

        if new_enabled:
            # deactivate all other schedules
            session.query(Schedule).filter(Schedule.id != new_id).update({'enabled': False})

    # enable immediately if requested
    if new_enabled:
        await app.backend.set_operating_schedule(new_id)

    return json({'id': new_id}, 201)


# noinspection PyUnusedLocal
@app.delete('/schedules/<schedule_id:int>')
async def delete(request: Request, schedule_id: int):
    """Deletes a schedule."""

    if app.backend.schedule and app.backend.schedule.schedule['id'] == schedule_id:
        # deactivate if active
        await app.backend.set_operating_schedule(None)

    with scoped_session(app.database) as session:
        try:
            session.query(Schedule).filter(Schedule.id == schedule_id).delete()
            return no_content()
        except NoResultFound:
            raise errors.NotFoundError('Schedule not found.')


# noinspection PyUnusedLocal
@app.put('/schedules/<schedule_id:int>')
async def update(request: Request, schedule_id: int):
    """Updates a schedule."""

    data = request.json
    new_enabled = False
    with scoped_session(app.database) as session:
        try:
            sched = session.query(Schedule).filter(Schedule.id == schedule_id).one()
            if app.backend.schedule and app.backend.schedule.schedule['id'] == schedule_id:
                new_enabled = sched.enabled

            if 'name' in data:
                sched.name = data['name']
            if 'description' in data:
                sched.description = data['description']
            if 'enabled' in data:
                sched.enabled = data['enabled']
                if sched.enabled:
                    new_enabled = True

            if 'behaviors' in data:
                # delete all behaviors first
                session.query(Behavior).filter(Behavior.schedule_id == schedule_id).delete()

                sched.behaviors = []
                for data_behavior in data['behaviors']:
                    beh = Behavior()
                    beh.behavior_name = data_behavior['name']
                    beh.behavior_order = data_behavior['order']
                    beh.start_time = data_behavior['start_time']
                    beh.end_time = data_behavior['end_time']
                    beh.config = json_dumps(data_behavior['config'])
                    sched.behaviors.append(beh)
            session.add(sched)

            if new_enabled:
                # deactivate all other pipelines
                session.query(Schedule).filter(Schedule.id != schedule_id).update({'enabled': False})

        except NoResultFound:
            raise errors.NotFoundError('Schedule not found.')

    # enable immediately if requested
    if new_enabled:
        await app.backend.set_operating_schedule(schedule_id)
    elif app.backend.pipeline and app.backend.schedule.schedule['id'] == schedule_id:
        await app.backend.set_operating_schedule(None)

    return no_content()
