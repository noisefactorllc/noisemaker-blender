"""The CUSTOM Noisemaker node editor."""
from . import tree


def register():
    tree.register()


def unregister():
    tree.unregister()
