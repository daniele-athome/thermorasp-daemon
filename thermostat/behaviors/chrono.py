# -*- coding: utf-8 -*-
"""Time-based behaviors."""

from . import BaseBehavior


class TimeBasedBehavior(BaseBehavior):
    """Base interface for time-based behaviors."""

    def __init__(self, behavior_id, behavior_type, config=None):
        BaseBehavior.__init__(behavior_id, behavior_type, config)

    def get_config_schema(self):
        """Must be implemented by child classes."""
        raise NotImplementedError()

    def execute(self, context):
        # TODO
        pass

    def trigger(self, context):
        """Overridden by child classes to implement actual behavior."""
        raise NotImplementedError()
