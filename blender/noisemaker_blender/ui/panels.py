"""Sidebar panels that drive a scene-wide bake (the no-node workflow).

Shown in the Compositor and the Image Editor under a "Noisemaker" tab — the two places a
user wires up / inspects the baked Image. They read and write ``scene.noisemaker`` and
invoke ``noisemaker.bake`` with no operator overrides (so it uses those scene settings).
"""
import bpy


def _draw(layout, st):
    layout.prop(st, "source_mode", text="")
    if st.source_mode == 'TEXT':
        layout.prop(st, "text", text="")
    else:
        layout.prop(st, "filepath", text="")
    col = layout.column(align=True)
    col.prop(st, "size")
    col.prop(st, "time")
    col.prop(st, "frames")
    col.prop(st, "timestep")
    layout.prop(st, "image_name", text="Image")
    layout.operator("noisemaker.bake", text="Bake", icon='RENDER_STILL')


class _NoisemakerPanel:
    bl_region_type = 'UI'
    bl_category = "Noisemaker"
    bl_label = "Bake"

    def draw(self, context):
        st = getattr(context.scene, "noisemaker", None)
        if st is None:
            self.layout.label(text="Noisemaker not registered")
            return
        _draw(self.layout, st)


class NOISEMAKER_PT_compositor(_NoisemakerPanel, bpy.types.Panel):
    bl_idname = "NOISEMAKER_PT_compositor"
    bl_space_type = 'NODE_EDITOR'

    @classmethod
    def poll(cls, context):
        sd = context.space_data
        return getattr(sd, "tree_type", "") == 'CompositorNodeTree'


class NOISEMAKER_PT_image_editor(_NoisemakerPanel, bpy.types.Panel):
    bl_idname = "NOISEMAKER_PT_image_editor"
    bl_space_type = 'IMAGE_EDITOR'


_CLASSES = (NOISEMAKER_PT_compositor, NOISEMAKER_PT_image_editor)


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)
