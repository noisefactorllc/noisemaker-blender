"""NOISEMAKER_OT_bake — the integration seam.

DSL source  ->  compile_graph (in-addon Python compiler, no external reference)
            ->  GpuBackend render (gpu module)
            ->  Image datablock  (the compositor consumes it via a stock Image node)

The operator is self-contained and scriptable: every input is an operator property, so a
script or a node can drive it directly, e.g.

    bpy.ops.noisemaker.bake(dsl="noise().write(o0)\\nrender(o0)", image_name="X", size=256)

When a property is left at its sentinel default the operator falls back to the scene
settings (``context.scene.noisemaker``), which is what the N-panels populate.
"""
import os

import bpy

# Pure-Python imports are safe at module top (the gates never import this module, but the
# heavy gpu-dependent backend is imported lazily in execute() to keep import side-effect free).
from ..compiler import compile_graph, CompilationError, ExpansionError
from ..runtime import graph_loader, pipeline

# .../noisemaker_blender/ops/bake.py -> .../noisemaker_blender/shaders/effects
_ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHADERS_ROOT = os.path.join(_ADDON, "shaders", "effects")


def _read_source(op, scene_settings):
    """Resolve DSL text from (in priority) explicit op.dsl, a named/scene Text datablock,
    or a file path. Returns (source_str, None) or (None, error_message)."""
    if op.dsl:
        return op.dsl, None

    st = scene_settings
    # Text datablock: explicit op.text_name wins, else the scene pointer.
    text_db = None
    if op.text_name:
        text_db = bpy.data.texts.get(op.text_name)
        if text_db is None:
            return None, "Text block %r not found" % op.text_name
    elif st and st.source_mode == 'TEXT' and st.text:
        text_db = st.text
    if text_db is not None:
        return text_db.as_string(), None

    # File path: explicit op.filepath, else scene filepath (when in FILE mode).
    path = op.filepath or (st.filepath if (st and st.source_mode == 'FILE') else "")
    if path:
        path = bpy.path.abspath(path)
        if not os.path.exists(path):
            return None, "DSL file not found: %s" % path
        with open(path) as fh:
            return fh.read(), None

    return None, "No DSL source set (pick a Text block or a .dsl file)"


def _write_image(name, arr):
    """Write a top-down uint8 HxWx4 array into a float Image datablock (created if needed),
    bottom-up and Non-Color so the stored values are the exact rendered values."""
    import numpy as np
    h, w = arr.shape[:2]
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.new(name, width=w, height=h, alpha=True, float_buffer=True)
    elif tuple(img.size) != (w, h):
        img.scale(w, h)
    # Don't let an unused datablock get purged between bakes.
    img.use_fake_user = True
    # Raw values, no view transform — matches the linear golden capture. MUST be set
    # BEFORE writing pixels: changing colorspace on a generated image regenerates (and
    # clobbers) the pixel buffer, which would leave the bake black.
    try:
        img.colorspace_settings.name = 'Non-Color'
    except Exception:
        pass
    # GPU/golden order is top-down; Image datablocks are bottom-up -> flip back.
    flat = np.ascontiguousarray(arr[::-1], dtype=np.float32).reshape(-1) / 255.0
    img.pixels.foreach_set(flat)
    img.update()
    return img


class NOISEMAKER_OT_bake(bpy.types.Operator):
    """Compile the Noisemaker DSL and bake it into an Image datablock"""
    bl_idname = "noisemaker.bake"
    bl_label = "Bake Noisemaker"
    bl_options = {'REGISTER'}

    # All inputs are operator properties (scriptable). SKIP_SAVE + sentinel defaults mean
    # "unset -> fall back to scene settings".
    dsl: bpy.props.StringProperty(name="DSL", default="", options={'SKIP_SAVE'})
    text_name: bpy.props.StringProperty(name="Text Block", default="", options={'SKIP_SAVE'})
    filepath: bpy.props.StringProperty(name="DSL File", default="", subtype='FILE_PATH',
                                       options={'SKIP_SAVE'})
    image_name: bpy.props.StringProperty(name="Image", default="", options={'SKIP_SAVE'})
    size: bpy.props.IntProperty(name="Size", default=0, options={'SKIP_SAVE'})
    time: bpy.props.FloatProperty(name="Time", default=-1.0, options={'SKIP_SAVE'})
    frames: bpy.props.IntProperty(name="Frames", default=0, options={'SKIP_SAVE'})
    timestep: bpy.props.FloatProperty(name="Timestep", default=-1.0, options={'SKIP_SAVE'})

    def execute(self, context):
        st = getattr(context.scene, "noisemaker", None)

        src, err = _read_source(self, st)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        # Resolve params: explicit op value (non-sentinel) wins, else scene, else default.
        size = self.size if self.size > 0 else (st.size if st else 256)
        time = self.time if self.time >= 0.0 else (st.time if st else 0.25)
        frames = self.frames if self.frames > 0 else (st.frames if st else 1)
        timestep = self.timestep if self.timestep >= 0.0 else (st.timestep if st else 0.0)
        name = self.image_name or (st.image_name if st else "") or "Noisemaker"

        # 1) DSL -> normalized render graph (in-addon compiler).
        try:
            graph = graph_loader.Graph(compile_graph(src))
        except (CompilationError, ExpansionError) as e:
            self.report({'ERROR'}, "DSL compile failed: %s" % e)
            return {'CANCELLED'}
        except Exception as e:                                       # lex/parse/validate errors
            self.report({'ERROR'}, "DSL error: %s" % e)
            return {'CANCELLED'}

        # 2) render via the gpu backend (imported lazily — needs a live GPU context).
        try:
            from ..backend.gpu_backend import GpuBackend
            be = GpuBackend(_SHADERS_ROOT, size)
            try:
                arr = pipeline.render(be, graph, time=time, frames=frames, timestep=timestep)
            finally:
                be.free()
        except Exception as e:
            self.report({'ERROR'}, "Render failed: %s" % e)
            return {'CANCELLED'}

        # 3) bake into the Image datablock.
        img = _write_image(name, arr)
        self.report({'INFO'}, "Baked '%s' (%dx%d, %d frame%s)"
                    % (img.name, img.size[0], img.size[1], frames, "" if frames == 1 else "s"))
        return {'FINISHED'}


def register():
    bpy.utils.register_class(NOISEMAKER_OT_bake)


def unregister():
    bpy.utils.unregister_class(NOISEMAKER_OT_bake)
