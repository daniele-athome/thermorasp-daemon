# -*- coding: utf-8 -*-
"""Smart automation behaviors."""

import importlib


class BehaviorContext(object):
    """
    Objects passed to BaseBehavior.execute will be instances of this class.
    This class contains the current state of the system for behaviors to operate,
    such as instances of sensors (to get readings) and devices (to control them).
    """

    def __init__(self, devices, last_reading=None):
        """
        :param devices: a dictionary of all registered devices related to the active pipeline
        :type devices: dict
        :param last_reading: a dictionary of the last reading from each sensor type. '_avg' will have an average of all.
        :type last_reading: dict
        """
        self.devices = devices
        self.last_reading = last_reading
        # this will be passed among all behaviors in the chain
        self.params = {}


class BaseBehavior(object):
    """Base interface for behaviors."""

    def __init__(self, behavior_id, config=None):
        self.id = behavior_id
        self.config = config
        if not self.config:
            self.config = {}
        # TODO check config based on schema

    def get_config_schema(self):
        """Returns the configuration schema for this behavior."""
        raise NotImplementedError()

    def execute(self, context):
        """
        This is the behavior main execution function.
        :param context: an instance of BehaviorContext
        :type context: BehaviorContext
        :return True to go on with the chain, False to block processing
        """
        raise NotImplementedError()


def get_behavior_handler(behavior_id: str, config: dict) -> BaseBehavior:
    """Returns an appropriate behavior handler for the given behavior id."""
    b_module, b_class = behavior_id.split('.', 1)
    module = importlib.import_module('.'+b_module, __name__)
    if module:
        handler_class = getattr(module, b_class)
        return handler_class(behavior_id, config)
