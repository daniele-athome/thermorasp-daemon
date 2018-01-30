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

    with scoped_session(app.database) as session:
        try:
            pipeline = serialize_pipeline(session.query(Pipeline).filter(Pipeline.enabled > 0).one())
            return json(pipeline)
        except NoResultFound:
            raise errors.NotFoundError('Pipeline not found.')


# noinspection PyUnusedLocal
@app.post('/pipelines')
async def create(request: Request):
    """Creates a pipeline."""

    data = request.json
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
                beh.config = json_dumps(data_behavior['config'])
                pip.behaviors.append(beh)
        session.add(pip)
        session.flush()
        return json({'id': pip.id}, 201)


# noinspection PyUnusedLocal
@app.delete('/pipelines/<pipeline_id:int>')
async def delete(request: Request, pipeline_id: int):
    """Deletes a pipeline."""

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
    with scoped_session(app.database) as session:
        try:
            pip = session.query(Pipeline).filter(Pipeline.id == pipeline_id).one()

            if 'name' in data:
                pip.name = data['name']
            if 'description' in data:
                pip.description = data['description']
            if 'enabled' in data:
                pip.enabled = data['enabled']
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
