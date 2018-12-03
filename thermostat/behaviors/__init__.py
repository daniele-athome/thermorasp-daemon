# -*- coding: utf-8 -*-
"""Smart automation behaviors."""

import logging
import importlib

# TEST loggers
log = logging.getLogger("root")


class BehaviorContext(object):
    """
    Objects passed to BaseBehavior.execute will be instances of this class.
    This class contains the current state of the system for behaviors to operate,
    such as instances of sensors (to get readings) and devices (to control them).
    """

    def __init__(self, event_logger, devices, last_reading=None):
        """
        :param event_logger: the event logger instance
        :type event_logger: EventLogger
        :param devices: a dictionary of all registered devices related to the active pipeline
        :type devices: dict
        :param last_reading: a dictionary of the last reading from each sensor type. '_avg' will have an average of all.
        :type last_reading: dict
        """
        self.event_logger = event_logger
        self.devices = devices
        self.last_reading = last_reading
        self.delete = False
        # this will be passed among all behaviors in the chain
        self.params = {}

    def delete_self(self):
        """Behaviors will call this if they wants to be removed from the active pipeline."""
        self.delete = True


class BaseBehavior(object):
    """Base interface for behaviors."""

    def __init__(self, behavior_id, config=None):
        self.id = behavior_id
        self.config = config
        if not self.config:
            self.config = {}
        # TODO check config based on schema

    @classmethod
    def get_config_schema(cls):
        """Returns the configuration schema for this behavior."""
        raise NotImplementedError()

    def startup(self):
        """Called when the behavior is started."""
        raise NotImplementedError()

    def shutdown(self):
        """Called when the behavior is stopped."""
        raise NotImplementedError()

    def sensor_data(self, todo):  # TODO
        """Called when a sensor has new data."""
        pass

    def device_state(self, todo):  # TODO
        """Called when a device changes its state."""
        pass

    def timer(self):
        """Called when the timer ticks."""
        pass


def get_behavior_handler_class(behavior_id: str):
    """Returns an appropriate behavior handler class object for the given behavior id."""
    b_module, b_class = behavior_id.split('.', 1)
    module = importlib.import_module('.'+b_module, __name__)
    if module:
        return getattr(module, b_class)


def get_behavior_handler(behavior_id: str, config: dict) -> BaseBehavior:
    """Returns an appropriate behavior handler instance for the given behavior id."""
    handler_class = get_behavior_handler_class(behavior_id)
    if handler_class:
        return handler_class(behavior_id, config)
