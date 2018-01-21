# -*- coding: utf-8 -*-
"""Managed devices API."""

from sanic.request import Request
from sanic.response import json

from sqlalchemy.orm.exc import NoResultFound

from .. import app, errors
from ..database import scoped_session
from ..models.devices import Device

DEVICE_STATUS_MAP = (
    'unknown',
    'active',
    'inactive',
)


def serialize_device(device):
    return {
        'id': device.id,
        'protocol': device.protocol,
        'address': device.address,
        'type': device.device_type,
    }


# noinspection PyUnusedLocal
@app.get('/devices')
async def index(request: Request):
    """List all registered devices."""

    with scoped_session(app.database) as session:
        stmt = Device.__table__.select()
        sensors = [serialize_device(s) for s in session.execute(stmt)]
    return json(sensors)


@app.post('/devices/register')
async def register(request: Request):
    """Request registration for a device."""

    in_data = request.json
    with scoped_session(app.database) as session:
        device = Device()
        device.id = in_data['id']
        device.protocol = in_data['protocol']
        device.address = in_data['address']
        device.device_type = in_data['type']
        sensor = session.merge(device)
        return json(serialize_device(sensor))


@app.post('/devices/unregister')
async def unregister(request: Request):
    """
    Request unregistration for a device.
    """

    in_data = request.json
    with scoped_session(app.database) as session:
        try:
            device = session.query(Device).filter(Device.id == in_data['id']).one()
            session.delete(device)
            return json({
                'id': device.id,
            })
        except NoResultFound:
            raise errors.NotFoundError('Device not found.')
