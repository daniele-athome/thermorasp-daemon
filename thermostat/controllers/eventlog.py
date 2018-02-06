# -*- coding: utf-8 -*-
"""Event Log API."""

from sanic.request import Request
from sanic.response import json

from sqlalchemy.sql.expression import desc

from .. import app
from ..database import scoped_session
from ..models.eventlog import EventLog


def serialize_event(event: EventLog):
    return {
        'id': event.id,
        'timestamp': event.timestamp.isoformat(),
        'level': event.level,
        'source': event.source,
        'name': event.name,
        'description': event.description,
    }


# noinspection PyUnusedLocal
@app.get('/eventlog/next')
async def index_next(request: Request):
    """List all events."""

    # actually it's more of an end_id, but whatever :)
    if 'start_id' in request.args:
        start_id = int(request.args['start_id'][0])
    else:
        start_id = 0

    if 'page_size' in request.args:
        page_size = int(request.args['page_size'][0])
    else:
        page_size = 20

    with scoped_session(app.database) as session:
        query = session.query(EventLog)
        if start_id > 0:
            query = query.filter(EventLog.id < start_id)

        events = query.order_by(desc(EventLog.id)) \
            .limit(page_size) \
            .all()

        return json([serialize_event(e) for e in events])


# noinspection PyUnusedLocal
@app.get('/eventlog/prev')
async def index_prev(request: Request):
    """List all events."""

    if 'start_id' in request.args:
        start_id = int(request.args['start_id'][0])
    else:
        start_id = 0

    if 'page_size' in request.args:
        page_size = int(request.args['page_size'][0])
    else:
        page_size = 20

    with scoped_session(app.database) as session:
        query = session.query(EventLog)
        if start_id > 0:
            query = query.filter(EventLog.id <= (start_id + page_size))

        events = query.order_by(desc(EventLog.id)) \
            .limit(page_size) \
            .all()

        return json([serialize_event(e) for e in events])
