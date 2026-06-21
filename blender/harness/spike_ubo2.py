"""Validate backend/std140.py end-to-end: int + bool bit-cast through the float Buffer, and
the bare-name #define injection — the two risks the first spike (float/vec/vec) didn't cover.

Mimics exactly what shader_build/gpu_backend will do: struct_source + field_defines from the
helper, bare uniform names in the body, pack() -> GPUUniformBuf. Known-answer.

Usage: blender --factory-startup --python blender/harness/spike_ubo2.py
"""
import os
import sys
import traceback

import bpy
import gpu
import numpy as np
from gpu.types import GPUShaderCreateInfo, GPUUniformBuf, Buffer

HARNESS = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(os.path.dirname(HARNESS), "noisemaker_blender")
sys.path.insert(0, os.path.dirname(ADDON))
from noisemaker_blender.backend import std140  # noqa: E402

W = H = 4
# order chosen to exercise alignment with int/bool interleaved
FIELDS = [("FLOAT", "aa"), ("INT", "ee"), ("BOOL", "gg"), ("VEC2", "cc"), ("VEC3", "bb")]
VALUES = {"aa": 0.5, "ee": 2, "gg": True, "cc": (0.4, 9.0), "bb": (0.7, 9.0, 9.0)}
# fragment writes (aa, float(ee)*0.1, gg?0.3:0.0, bb.x) -> expect (0.5, 0.2, 0.3, 0.7)
EXPECT = (0.5, 0.2, 0.3, 0.7)


def run():
    entries, nfloats = std140.layout(FIELDS)
    print("SPIKE layout nfloats=%d entries=%s" % (nfloats, [(t, n, o) for t, n, o in entries]))

    info = GPUShaderCreateInfo()
    info.typedef_source(std140.struct_source(FIELDS))
    info.uniform_buf(0, std140.STRUCT_NAME, std140.INSTANCE)
    info.fragment_out(0, 'VEC4', "fragColor")
    info.vertex_in(0, 'VEC2', "pos")
    info.vertex_source("void main(){ gl_Position = vec4(pos, 0.0, 1.0); }")
    # bare names in the body, resolved by the injected #defines (exactly the real pipeline)
    header = "\n".join(std140.field_defines(FIELDS)) + "\n"
    body = "void main(){ fragColor = vec4(aa, float(ee)*0.1, gg ? 0.3 : 0.0, bb.x); }"
    info.fragment_source(header + body)
    shader = gpu.shader.create_from_info(info)
    print("SPIKE compile OK")

    packed = std140.pack(FIELDS, VALUES)
    assert len(packed) == nfloats, (len(packed), nfloats)
    ubo = GPUUniformBuf(Buffer('FLOAT', nfloats, packed))
    print("SPIKE pack+GPUUniformBuf OK (%d floats)" % nfloats)

    off = gpu.types.GPUOffScreen(W, H, format='RGBA16F')
    from gpu_extras.batch import batch_for_shader
    batch = batch_for_shader(shader, 'TRIS', {"pos": [(-1, -1), (3, -1), (-1, 3)]})
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0.0, 0.0, 0.0, 0.0))
        shader.bind()
        shader.uniform_block(std140.INSTANCE, ubo)
        batch.draw(shader)
        rb = fb.read_color(0, 0, W, H, 4, 0, 'FLOAT')
    rb.dimensions = W * H * 4
    px = np.array(rb, dtype=np.float32).reshape(H, W, 4)[H // 2, W // 2]
    print("SPIKE pixel   =", [round(float(v), 4) for v in px])
    print("SPIKE expected=", list(EXPECT))
    err = max(abs(float(px[i]) - EXPECT[i]) for i in range(4))
    print("SPIKE max-abs-err = %.5f" % err)
    print("SPIKE RESULT:", "PASS — int+bool+vec std140 pack/define all correct" if err < 1e-3
          else "FAIL — pack/define mismatch")
    off.free()
    sys.stdout.flush()


if bpy.app.background:
    print("SPIKE FAIL: GPU needs GUI mode; run without -b")
else:
    def _t():
        try:
            run()
        except Exception:
            print("SPIKE FAIL (exception):")
            traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None
    bpy.app.timers.register(_t, first_interval=0.5)
