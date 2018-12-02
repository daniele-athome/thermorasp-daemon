# -*- coding: utf-8 -*-
"""Managed devices API."""

from sanic.request import Request
from sanic.response import json

from .. import app, errors


DEVICE_STATUS_MAP = (
    'unknown',
    'active',
    'inactive',
)


def serialize_device(device):
    return {
        'id': device.id,
        'name': device.name,
        'protocol': device.protocol,
        'address': ':'.join(device.address),
        'type': device.type,
    }


# noinspection PyUnusedLocal
@app.get('/devices')
async def index(request: Request):
    """List all registered devices."""

    device_type = request.args['type'][0] if 'type' in request.args else None
    return json([serialize_device(d) for d in app.backend.devices.values() if not device_type or device_type == d.type])


@app.post('/devices/register')
async def register(request: Request):
    """Request registration for a device."""

    in_data = request.json
    app.backend.devices.register(in_data['id'], in_data['protocol'], in_data['address'], in_data['type'], in_data['name'])
    return json({'id': in_data['id']}, 201)


@app.post('/devices/unregister')
async def unregister(request: Request):
    """
    Request unregistration for a device.
    """

    in_data = request.json
    if app.backend.devices.unregister(in_data['id']):
        return json({'id': in_data['id']})
    else:
        raise errors.NotFoundError('Device not found.')


# noinspection PyUnusedLocal
@app.get('/devices/status/<device_id>')
async def status(request: Request, device_id: str):
    """
    Request the status of a device.
    """

    try:
        instance = app.backend.devices[device_id]
    except KeyError:
        raise errors.NotFoundError('Device not found.')

    return json({
        'id': instance.id,
        'status': instance.status(),
    })


@app.post('/devices/control/<device_id>')
async def control(request: Request, device_id: str):
    """
    Request a control operation for a device.
    """

    try:
        instance = app.backend.devices[device_id]
    except KeyError:
        raise errors.NotFoundError('Device not found.')

    return json({
        'id': instance.id,
        'control': instance.control(**request.json),
        'status': instance.status(),
    })
