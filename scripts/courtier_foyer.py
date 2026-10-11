#!/usr/bin/env python3
"""Compatibility entry: Courtier compiles the actual approved ROOM template.

The implementation is room_template_foyer.py. It never constructs a second
newspaper-derived HTML skin. Kept as an import facade for existing callers.
"""
from room_template_foyer import IMAGES, ROOM, build, scene_for, transform

__all__ = ["IMAGES", "ROOM", "build", "scene_for", "transform"]
