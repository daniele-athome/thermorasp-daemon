# -*- coding: utf-8 -*-
"""Nodes without a specific purpose in the IoT world."""

import asyncio
import hbmqtt.client as mqtt_client


class TimerNode(object):
    """A simple timer node. Sends timing pings for the system to use."""

    def __init__(self, app, base_topic, device_id, node_id, seconds):
        self.seconds = seconds
        self.app = app
        self.topic = "/".join([
            base_topic,
            device_id,
            node_id,
            '_internal'])

        self.broker = mqtt_client.MQTTClient(device_id + '-' + node_id)
        self.app.add_task(self._connect())

    async def _connect(self):
        await self.broker.connect(self.app.broker_url)
        await asyncio.ensure_future(self._loop())

    async def _loop(self):
        while self.app.is_running:
            await asyncio.sleep(self.seconds)
            await self.broker.publish(self.topic, b'timer', retain=False)