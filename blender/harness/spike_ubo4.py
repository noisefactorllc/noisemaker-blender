"""Decisive test: does Blender's std140 layout match ours for the REAL 24-field noise struct?
The 5-field spike passed but cnd_noise/cnd_shapes render wrong via UBO. Pack known values into
noise's exact field list and read back fields spread across the struct (early/mid/late/last).
A mismatch anywhere => large-struct layout divergence (the UBO bug); all match => UBO is fine
and the render gap is shader-logic/recipe, not the block.

Usage: blender --factory-startup --python blender/harness/spike_ubo4.py
"""
import json
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
CI = os.path.join(ADDON, "shaders", "effects", "classicNoisedeck", "noise", "noise.createinfo.json")


def run():
    fields = json.load(open(CI))["pushConstants"]
    print("SPIKE noise fields=%d" % len(fields))
    # Known values: distinctive per field so a misread is obvious.
    vals = {}
    for i, (ct, n) in enumerate(fields):
        if ct == "FLOAT":
            vals[n] = round(0.01 * (i + 1), 3)
        elif ct == "INT":
            vals[n] = i + 1
        elif ct == "BOOL":
            vals[n] = True
        elif ct == "VEC2":
            vals[n] = (0.01 * (i + 1), 0.5)
        elif ct == "VEC3":
            vals[n] = (0.01 * (i + 1), 0.5, 0.25)
    entries, nfloats = std140.layout(fields)
    packed = std140.pack(fields, vals)

    # Probe four fields spread through the struct.
    probes = [fields[0][1], fields[7][1], fields[17][1], fields[-1][1]]  # time, octaves, palettePhase, wrap
    print("SPIKE probing:", probes)
    info = GPUShaderCreateInfo()
    info.typedef_source(std140.struct_source(fields))
    info.uniform_buf(0, std140.STRUCT_NAME, std140.INSTANCE)
    info.fragment_out(0, 'VEC4', "fragColor")
    info.vertex_in(0, 'VEC2', "pos")
    info.vertex_source("void main(){ gl_Position = vec4(pos,0.0,1.0); }")
    # build expression reading each probe as a float
    def rd(name):
        ct = dict((n, c) for c, n in fields)[name]
        ref = "%s.%s" % (std140.INSTANCE, name)
        if ct == "FLOAT":
            return ref
        if ct == "INT":
            return "float(%s)" % ref
        if ct == "BOOL":
            return "((%s != 0) ? 1.0 : 0.0)" % ref
        if ct in ("VEC2", "VEC3"):
            return "%s.x" % ref
        return "0.0"
    expr = ", ".join(rd(p) for p in probes)
    info.fragment_source("void main(){ fragColor = vec4(%s); }" % expr)
    shader = gpu.shader.create_from_info(info)
    ubo = GPUUniformBuf(Buffer('FLOAT', nfloats, packed))

    off = gpu.types.GPUOffScreen(W, H, format='RGBA16F')
    from gpu_extras.batch import batch_for_shader
    batch = batch_for_shader(shader, 'TRIS', {"pos": [(-1, -1), (3, -1), (-1, 3)]})
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0, 0, 0, 0))
        shader.bind()
        shader.uniform_block(std140.INSTANCE, ubo)
        batch.draw(shader)
        rb = fb.read_color(0, 0, W, H, 4, 0, 'FLOAT')
    rb.dimensions = W * H * 4
    px = np.array(rb, dtype=np.float32).reshape(H, W, 4)[H // 2, W // 2]

    def expected(name):
        ct = dict((n, c) for c, n in fields)[name]
        v = vals[name]
        if ct == "FLOAT":
            return v
        if ct == "INT":
            return float(v)
        if ct == "BOOL":
            return 1.0
        return v[0]
    exp = [expected(p) for p in probes]
    print("SPIKE got     =", [round(float(v), 4) for v in px])
    print("SPIKE expected=", [round(float(v), 4) for v in exp])
    err = max(abs(float(px[i]) - exp[i]) for i in range(4))
    print("SPIKE max-abs-err=%.5f -> %s" % (err, "PASS (large struct OK)" if err < 1e-2
                                            else "FAIL (large-struct layout mismatch = the UBO bug)"))
    off.free()
    sys.stdout.flush()


if bpy.app.background:
    print("SPIKE FAIL: GPU needs GUI")
else:
    def _t():
        try:
            run()
        except Exception:
            traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None
    bpy.app.timers.register(_t, first_interval=0.5)
