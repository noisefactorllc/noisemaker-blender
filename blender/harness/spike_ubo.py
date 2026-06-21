"""De-risk the std140 UBO path on Blender/Metal with a KNOWN-ANSWER test.

The UBO-overflow effects (>128B of push constants) need a uniform block instead. This spike
proves the whole chain before wiring it into the transpiler/backend:
  - GPUShaderCreateInfo.typedef_source(struct) + .uniform_buf(slot, type, name)
  - gpu.types.GPUUniformBuf(Buffer) created from a std140-packed byte buffer
  - GPUShader.uniform_block(name, ubo) binding
  - and — critically — that MY std140 offset math matches Blender's struct layout.

The struct deliberately hits the std140 alignment traps:
    float a;   // 0
    vec3  b;   // 16   (vec3 aligns to 16 -> a's 4 bytes padded to 16)
    vec2  c;   // 32   (vec3 occupies 12 -> next free 28, vec2 aligns to 8 -> 32)
    float d;   // 40
  size -> 48 (rounded up to a multiple of 16)
The fragment writes (a, b.x, c.x, d); we pack (0.1, 0.2, 0.3, 0.4) at those offsets and read
the pixel back. A wrong offset (e.g. vec3 not aligned to 16) yields the wrong colour.

Usage: blender --factory-startup --python blender/harness/spike_ubo.py
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
EXPECT = (0.1, 0.2, 0.3, 0.4)


def run():
    info = GPUShaderCreateInfo()
    info.typedef_source("struct NmTest { float a; vec3 b; vec2 c; float d; };\n")
    info.uniform_buf(0, "NmTest", "nm_ub")
    info.fragment_out(0, 'VEC4', "fragColor")
    info.vertex_in(0, 'VEC2', "pos")
    info.vertex_source("void main(){ gl_Position = vec4(pos, 0.0, 1.0); }")
    info.fragment_source(
        "void main(){ fragColor = vec4(nm_ub.a, nm_ub.b.x, nm_ub.c.x, nm_ub.d); }")
    shader = gpu.shader.create_from_info(info)
    print("SPIKE compile OK")

    # std140-packed buffer: 48 bytes = 12 floats.
    floats = [0.0] * 12
    floats[0] = 0.1     # a   @ 0
    floats[4] = 0.2     # b.x @ 16
    floats[8] = 0.3     # c.x @ 32
    floats[10] = 0.4    # d   @ 40
    buf = Buffer('FLOAT', 12, floats)
    ubo = GPUUniformBuf(buf)
    print("SPIKE GPUUniformBuf OK (%d bytes)" % (12 * 4))

    off = gpu.types.GPUOffScreen(W, H, format='RGBA16F')
    from gpu_extras.batch import batch_for_shader
    batch = batch_for_shader(shader, 'TRIS', {"pos": [(-1, -1), (3, -1), (-1, 3)]})
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0.0, 0.0, 0.0, 0.0))
        shader.bind()
        shader.uniform_block("nm_ub", ubo)
        batch.draw(shader)
        rb = fb.read_color(0, 0, W, H, 4, 0, 'FLOAT')
    rb.dimensions = W * H * 4
    arr = np.array(rb, dtype=np.float32).reshape(H, W, 4)
    px = arr[H // 2, W // 2]
    print("SPIKE pixel   =", [round(float(v), 4) for v in px])
    print("SPIKE expected=", list(EXPECT))
    err = max(abs(float(px[i]) - EXPECT[i]) for i in range(4))
    print("SPIKE max-abs-err = %.5f" % err)
    print("SPIKE RESULT:", "PASS — std140 offsets match Blender layout" if err < 1e-3
          else "FAIL — offset/layout mismatch")
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
