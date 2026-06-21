"""Operators for the Noisemaker integration surface."""
from . import bake


def register():
    bake.register()


def unregister():
    bake.unregister()
