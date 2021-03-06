# -*- coding: utf-8 -*-
"""Smart automation behaviors."""

import json
import statistics
import importlib
import pkgutil
import hbmqtt.client as mqtt_client

from .. import util


class SelfDestructError(Exception):
    """Raise this in any callback method from a behavior to let the OperatingSchedule know to destroy it."""
    pass


class BaseBehavior(object):
    """Base interface for behaviors."""

    def __init__(self, behavior_id: int, name: str, sensors: list, devices: list, broker: mqtt_client.MQTTClient):
        """
        :param sensors: list of topics of the sensors assigned to the behavior
        :param devices: list of topics of the devices assigned to the behavior
        """
        self.id = behavior_id
        self.name = name
        self.sensors = sensors
        self.devices = devices
        self.broker = broker
        self.last_sensor_data = {}

    @classmethod
    def get_config_schema(cls):
        """Returns the configuration schema for this behavior."""
        raise NotImplementedError()

    async def startup(self, config):
        """Called when the behavior is started."""
        raise NotImplementedError()

    async def shutdown(self):
        """Called when the behavior is stopped."""
        raise NotImplementedError()

    async def update(self, config):
        """Called when the behavior configuration changes."""
        raise NotImplementedError()

    async def sensor_data(self, topic: str, data: dict):
        """Called when a sensor has new data."""
        if not topic.endswith('/control'):
            self.last_sensor_data[topic] = data

    async def device_state(self, device_topic: str, data: dict):
        """Called when a device changes its state."""
        pass

    async def timer(self):
        """Called when the timer ticks."""
        pass

    async def control_device(self, topic, data):
        await self.broker.publish(topic + '/control', json.dumps(data).encode(), retain=False)

    def last_reading_avg(self, unit):
        if self.last_sensor_data:
            values = [data['value'] for data in self.last_sensor_data.values()
                      if data['unit'] == unit and ('validity' not in data or not util.is_past_then(data['timestamp'],
                                                                                                   data['validity']))]
            if values:
                return statistics.mean(values)
        else:
            return None

    def find_device_topic(self, topic: str):
        return next((device for device in self.devices if topic.startswith(device)), None)

    def find_sensor_topic(self, topic: str):
        return next((sensor for sensor in self.sensors if topic.startswith(sensor)), None)


def get_behaviors():
    """Return a list of all behavior IDs (i.e. name of classes extending BaseBehavior)."""
    behaviors = []
    package = importlib.import_module('.', package=__name__)
    prefix = package.__name__ + "."
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__, prefix):
        module = __import__(modname, fromlist=["*"])
        for member in dir(module):
            cls = getattr(module, member)
            try:
                if cls != BaseBehavior and issubclass(cls, BaseBehavior):
                    behaviors.append(modname[len(prefix):] + '.' + member)
            except TypeError:
                pass
    return behaviors


def get_behavior_handler_class(behavior_id: str):
    """Returns an appropriate behavior handler class object for the given behavior id."""
    b_module, b_class = behavior_id.split('.', 1)
    module = importlib.import_module('.'+b_module, __name__)
    if module:
        return getattr(module, b_class)


def get_behavior_handler(behavior_id: int, name: str, sensors, devices, broker: mqtt_client.MQTTClient) -> BaseBehavior:
    """Returns an appropriate behavior handler instance for the given behavior id."""
    handler_class = get_behavior_handler_class(name)
    if handler_class:
        return handler_class(behavior_id, name, sensors, devices, broker)
