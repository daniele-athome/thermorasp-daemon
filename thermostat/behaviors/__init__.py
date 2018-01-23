# -*- coding: utf-8 -*-
"""Smart automation behaviors."""


class BehaviorContext:
    """
    Objects passed to BaseBehavior.execute will be instances of this class.
    This class contains the current state of the system for behaviors to operate,
    such as instances of sensors (to get readings) and devices (to control them).
    """

    def __init__(self, sensors, devices):
        self.sensors = sensors
        self.devices = devices


class BaseBehavior:
    """Base interface for behaviors."""

    def __init__(self, behavior_id, behavior_type, config=None):
        self.id = behavior_id
        self.type = behavior_type
        self.config = config
        if not self.config:
            self.config = {}

    def get_config_schema(self):
        """Returns the configuration schema for this behavior."""
        raise NotImplementedError()

    def execute(self, context):
        """
        This is the behavior main execution function.
        :param context an instance of BehaviorContext
        :return True to go on with the chain, False to block processing
        """
        raise NotImplementedError()
