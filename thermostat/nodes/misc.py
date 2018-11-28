# -*- coding: utf-8 -*-
"""Nodes without a specific purpose in the IoT world."""

import asyncio
import homie


class TimerNode(object):
    """A simple timer node. Sends timing pings for the system to use."""

    def __init__(self, device: homie.Device, node_id, node_name, seconds):
        self.node = device.addNode(node_id, node_name, 'timer')
        self.device = device
        self._timer = None
        self.topic = "/".join([
            device.baseTopic,
            device.deviceId,
            '_internal'])
        self._prop_seconds = self.node.addProperty('seconds', 'Seconds', 's', 'integer', '1:86400')
        self._prop_seconds.settable(self._set_seconds)
        self._set_timer(seconds)

    def _set_seconds(self, key, value):
        if self._timer:
            self._timer.cancel()
        self._set_timer(value)

    def _set_timer(self, seconds):
        self._timer = asyncio.ensure_future(self._loop(seconds))

    async def _loop(self, seconds):
        await asyncio.sleep(seconds)
        self.device.publish(self.topic, 'timer')
        self._set_timer(seconds)
