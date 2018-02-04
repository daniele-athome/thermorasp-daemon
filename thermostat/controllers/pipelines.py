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
from ..models import Pipeline, Behavior


def serialize_pipeline_behavior(b: Behavior):
    return {
        'id': b.behavior_id,
        'order': b.behavior_order,
        'config': json_loads(b.config),
    }


def serialize_pipeline(p: Pipeline):
    return {
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'enabled': p.enabled > 0,
        'behaviors': [serialize_pipeline_behavior(b) for b in p.behaviors],
    }


# noinspection PyUnusedLocal
@app.get('/pipelines')
async def index(request: Request):
    """List all registered pipelines."""

    with scoped_session(app.database) as session:
        pipelines = [serialize_pipeline(p) for p in session.query(Pipeline).all()]
    return json(pipelines)


# noinspection PyUnusedLocal
@app.get('/pipelines/<pipeline_id>')
async def get(request: Request, pipeline_id: int):
    """Get the active pipeline."""

    with scoped_session(app.database) as session:
        try:
            pipeline = serialize_pipeline(session.query(Pipeline).filter(Pipeline.id == pipeline_id).one())
            return json(pipeline)
        except NoResultFound:
            raise errors.NotFoundError('Pipeline not found.')


# noinspection PyUnusedLocal
@app.get('/pipelines/active')
async def active(request: Request):
    """Get the active pipeline."""

    if app.backend.pipeline is None:
        raise errors.NotFoundError('Pipeline not found.')

    return json(app.backend.pipeline.pipeline)


# noinspection PyUnusedLocal
@app.get('/pipelines/active/target_temperature')
async def active(request: Request):
    """Get the active pipeline current target temperature."""

    if app.backend.pipeline is None:
        raise errors.NotFoundError('Pipeline not found.')
    return json({
        'pipeline_id': app.backend.pipeline.id,
        'target_temperature': app.backend.pipeline.get_target_temperature(),
    })


# noinspection PyUnusedLocal
@app.post('/pipelines')
async def create(request: Request):
    """Creates a pipeline."""

    data = request.json
    new_id = None
    new_enabled = False
    with scoped_session(app.database) as session:
        pip = Pipeline()
        pip.name = data['name']
        if 'description' in data:
            pip.description = data['description']
        if 'enabled' in data:
            pip.enabled = data['enabled']
        if 'behaviors' in data:
            pip.behaviors = []
            for data_behavior in data['behaviors']:
                beh = Behavior()
                beh.behavior_id = data_behavior['id']
                beh.behavior_order = data_behavior['order']
                beh.config = json_dumps(data_behavior['config'])
                pip.behaviors.append(beh)
        session.add(pip)
        session.flush()
        new_enabled = pip.enabled
        new_id = pip.id

    # enable immediately if requested
    if new_enabled:
        await app.backend.set_operating_pipeline(new_id)

    return json({'id': new_id}, 201)


# noinspection PyUnusedLocal
@app.delete('/pipelines/<pipeline_id:int>')
async def delete(request: Request, pipeline_id: int):
    """Deletes a pipeline."""

    if app.backend.pipeline is not None and app.backend.pipeline.id == pipeline_id:
        # deactivate if active
        await app.backend.set_operating_pipeline(None)

    with scoped_session(app.database) as session:
        try:
            session.query(Pipeline).filter(Pipeline.id == pipeline_id).delete()
            return no_content()
        except NoResultFound:
            raise errors.NotFoundError('Pipeline not found.')


# noinspection PyUnusedLocal
@app.put('/pipelines/<pipeline_id:int>')
async def update(request: Request, pipeline_id: int):
    """Updates a pipeline."""

    data = request.json
    new_enabled = False
    with scoped_session(app.database) as session:
        try:
            pip = session.query(Pipeline).filter(Pipeline.id == pipeline_id).one()

            if 'name' in data:
                pip.name = data['name']
            if 'description' in data:
                pip.description = data['description']
            if 'enabled' in data:
                pip.enabled = data['enabled']
                if pip.enabled:
                    new_enabled = True
                    # deactivate all other pipelines
                    session.query(Pipeline).filter(Pipeline.id != pipeline_id).update({'enabled': False})

            if 'behaviors' in data:
                # delete all behaviors first
                session.query(Behavior).filter(Behavior.pipeline_id == pipeline_id).delete()

                pip.behaviors = []
                for data_behavior in data['behaviors']:
                    beh = Behavior()
                    beh.behavior_id = data_behavior['id']
                    beh.config = json_dumps(data_behavior['config'])
                    pip.behaviors.append(beh)
            session.add(pip)

            return no_content()
        except NoResultFound:
            raise errors.NotFoundError('Pipeline not found.')

    # enable immediately if requested
    if new_enabled:
        await app.backend.set_operating_pipeline(pipeline_id)
