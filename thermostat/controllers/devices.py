# -*- coding: utf-8 -*-
"""Managed devices API."""

from sanic.request import Request
from sanic.response import json

from sqlalchemy.orm.exc import NoResultFound

from .. import app, errors, devices
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
        devs = [serialize_device(d) for d in session.execute(stmt)]
    return json(devs)


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
        device = session.merge(device)
        devices.register_device(device.id, device.protocol, device.address)
        return json(serialize_device(device))


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
            devices.unregister_device(device.id)
            return json({
                'id': device.id,
            })
        except NoResultFound:
            raise errors.NotFoundError('Device not found.')


@app.get('/devices/status/<device_id>')
async def status(request: Request, device_id: str):
    """
    Request the status of a device.
    """

    if 'type' in request.args and len(request.args['type']) == 1 and request.args['type'][0]:
        device_type = request.args['type'][0]
    else:
        device_type = None

    instance = devices.get_device(device_id)
    if instance:
        return json({
            'id': instance.device_id,
            'status': instance.status(device_type),
        })
    else:
        raise errors.NotFoundError('Device not found.')


@app.post('/devices/control/<device_id>')
async def control(request: Request, device_id: str):
    """
    Request a control operation for a device.
    """

    if 'type' in request.args and len(request.args['type']) == 1 and request.args['type'][0]:
        device_type = request.args['type'][0]
    else:
        device_type = None

    instance = devices.get_device(device_id)
    if instance:
        return json({
            'id': instance.device_id,
            'control': instance.control(device_type, **request.json),
            'status': instance.status(device_type),
        })
    else:
        raise errors.NotFoundError('Device not found.')
