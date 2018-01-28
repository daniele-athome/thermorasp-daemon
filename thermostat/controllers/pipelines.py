# -*- coding: utf-8 -*-
"""Pipelines API."""

from json import loads as json_loads

from sanic.request import Request
from sanic.response import json

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
@app.get('/pipelines/active')
async def active(request: Request):
    """Get the active pipeline."""

    with scoped_session(app.database) as session:
        pipeline = serialize_pipeline(session.query(Pipeline).filter(Pipeline.enabled > 0).one())
    return json(pipeline)


# noinspection PyUnusedLocal
@app.post('/pipelines')
async def create(request: Request):
    """Creates a pipeline."""

    # TODO
    return json({})


# noinspection PyUnusedLocal
@app.delete('/pipelines/<pipeline_id>')
async def delete(request: Request, pipeline_id: int):
    """Deletes a pipeline."""

    # TODO
    return json({})


# noinspection PyUnusedLocal
@app.put('/pipelines/<pipeline_id>')
async def update(request: Request, pipeline_id: int):
    """Updates a pipeline."""

    # TODO
    return json({})


# noinspection PyUnusedLocal
@app.put('/pipelines/active')
async def activate(request: Request):
    """Activates a pipelines."""

    # TODO
    return json({})


# noinspection PyUnusedLocal
@app.put('/pipelines/inactive')
async def inactivate(request: Request):
    """Inactivates a pipelines."""

    # TODO
    return json({})
