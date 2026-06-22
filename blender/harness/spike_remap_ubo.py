"""De-risk remap: a NAMED std140 UBO with an array member (`vec4 data[N]`) bound ALONGSIDE
push constants. Blender emulates push constants as a UBO on Metal, so the explicit uniform_buf
might collide with the push-constant block. Test: build push_constant + uniform_buf(array),
pack known values, read several slots back, verify.

Usage: blender --factory-startup --python blender/harness/spike_remap_ubo.py
"""
import os
import sys
import struct
import traceback

import bpy
import gpu
import numpy as np
from gpu.types import GPUShaderCreateInfo, GPUUniformBuf, Buffer

W = H = 4
N = 8  # data[N]


def run():
    info = GPUShaderCreateInfo()
    info.push_constant('VEC2', "foo")                      # a push constant alongside the UBO
    info.typedef_source("struct Blk { vec4 data[%d]; };" % N)
    info.uniform_buf(0, "Blk", "nm_ub")
    info.fragment_out(0, 'VEC4', "fragColor")
    info.vertex_in(0, 'VEC2', "pos")
    info.vertex_source("void main(){ gl_Position = vec4(pos,0.0,1.0); }")
    # read data[2].x, data[5].z, data[7].w, and foo.x
    info.fragment_source(
        "void main(){ fragColor = vec4(nm_ub.data[2].x, nm_ub.data[5].z, nm_ub.data[7].w, foo.x); }")
    try:
        shader = gpu.shader.create_from_info(info)
    except Exception as e:
        print("SPIKE FAIL compile:", str(e).splitlines()[0])
        return

    # pack data[N] as std140 (each vec4 = 16 bytes); known distinctive values
    buf = bytearray(N * 16)
    struct.pack_into("<f", buf, 2 * 16 + 0, 0.11)          # data[2].x
    struct.pack_into("<f", buf, 5 * 16 + 8, 0.55)          # data[5].z
    struct.pack_into("<f", buf, 7 * 16 + 12, 0.77)         # data[7].w
    packed = np.frombuffer(bytes(buf), dtype=np.float32).copy()
    ubo = GPUUniformBuf(Buffer('FLOAT', len(packed), packed))

    off = gpu.types.GPUOffScreen(W, H, format='RGBA16F')
    from gpu_extras.batch import batch_for_shader
    batch = batch_for_shader(shader, 'TRIS', {"pos": [(-1, -1), (3, -1), (-1, 3)]})
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0, 0, 0, 0))
        shader.bind()
        shader.uniform_block("nm_ub", ubo)
        shader.uniform_float("foo", (0.33, 0.0))
        batch.draw(shader)
        rb = fb.read_color(0, 0, W, H, 4, 0, 'FLOAT')
    rb.dimensions = W * H * 4
    px = np.array(rb, dtype=np.float32).reshape(H, W, 4)[H // 2, W // 2]
    exp = [0.11, 0.55, 0.77, 0.33]
    print("SPIKE got     =", [round(float(v), 3) for v in px])
    print("SPIKE expected=", exp)
    err = max(abs(float(px[i]) - exp[i]) for i in range(4))
    print("SPIKE max-abs-err=%.4f -> %s" % (
        err, "PASS (array UBO + push constant coexist)" if err < 1e-2 else "FAIL"))
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
