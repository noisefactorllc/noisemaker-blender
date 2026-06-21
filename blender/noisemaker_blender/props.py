"""Scene-level bake settings shared by the N-panels and the bake operator.

Exposed at ``context.scene.noisemaker``. The CUSTOM node (nodes/tree.py) keeps its own
copy of these on the node datablock so each node bakes independently; the panels drive
this scene-wide group for the no-node workflow.
"""
import bpy


# Used by both the scene group and the node so the two stay in lockstep.
def _size(default=256):
    return bpy.props.IntProperty(
        name="Size", default=default, min=8, max=4096, subtype='PIXEL',
        description="Square render resolution (the backend renders square)")


def _time(default=0.25):
    return bpy.props.FloatProperty(
        name="Time", default=default, min=0.0, max=1.0,
        description="Normalized animation time fed to the graph")


def _frames(default=1):
    return bpy.props.IntProperty(
        name="Frames", default=default, min=1, max=20000,
        description="Settle frames. 1 for single-pass effects; stateful sims "
                    "(navierStokes, agents, CAs) need many more")


def _timestep(default=0.0):
    return bpy.props.FloatProperty(
        name="Timestep", default=default, min=0.0, precision=5,
        description="0 = fixed-time deterministic render; >0 evolves continuous "
                    "solvers / agent sims to steady state (e.g. 0.00167 ~ 1/600)")


def _image_name(default="Noisemaker"):
    return bpy.props.StringProperty(
        name="Image", default=default,
        description="Target Image datablock (created if missing). Feed it into the "
                    "compositor via a stock Image node")


SOURCE_ITEMS = [
    ('TEXT', "Text Block", "DSL from a Blender Text datablock (edit it in the Text Editor)"),
    ('FILE', "File", "DSL from an external .dsl file on disk"),
]


class NoisemakerSettings(bpy.types.PropertyGroup):
    source_mode: bpy.props.EnumProperty(name="Source", items=SOURCE_ITEMS, default='TEXT')
    text: bpy.props.PointerProperty(name="DSL Text", type=bpy.types.Text)
    filepath: bpy.props.StringProperty(name="DSL File", subtype='FILE_PATH')
    size: _size()
    time: _time()
    frames: _frames()
    timestep: _timestep()
    image_name: _image_name()


def register():
    bpy.utils.register_class(NoisemakerSettings)
    bpy.types.Scene.noisemaker = bpy.props.PointerProperty(type=NoisemakerSettings)


def unregister():
    del bpy.types.Scene.noisemaker
    bpy.utils.unregister_class(NoisemakerSettings)
