"""Spike P-A: de-risk the points/agents platform capabilities on Blender/Metal.

Three isolated probes — each prints PASS/FAIL independently:
  1. MRT  — GPUFrameBuffer(color_slots=[t0,t1,t2]) + 3x fragment_out, readback all 3.
  2. POINTS — attribute-less drawArrays(POINTS,count): VS uses gl_VertexID to fetch
     per-point xy from a state texture, sets gl_PointSize, FS writes color. Verify hits.
  3. ADDITIVE — points drawn with blend ONE,ONE onto a pre-filled target accumulate >1.0.

Run: blender --factory-startup --python blender/harness/spike_points.py
"""
import sys
import traceback

import bpy
import gpu
from gpu.types import (GPUShaderCreateInfo, GPUTexture, GPUFrameBuffer,
                       GPUVertFormat, GPUVertBuf, GPUBatch, Buffer)
import numpy as np


def tex_to_np(tex, w, h):
    buf = tex.read()
    try:
        buf.dimensions = w * h * 4
    except Exception:
        pass
    return np.array(buf, dtype=np.float32).reshape(h, w, 4)


# ---- Probe 1: MRT ----------------------------------------------------------
def probe_mrt():
    W = H = 4
    info = GPUShaderCreateInfo()
    info.vertex_in(0, 'VEC2', "pos")
    info.fragment_out(0, 'VEC4', "out0")
    info.fragment_out(1, 'VEC4', "out1")
    info.fragment_out(2, 'VEC4', "out2")
    info.vertex_source("void main(){ gl_Position = vec4(pos, 0.0, 1.0); }")
    info.fragment_source("void main(){ out0=vec4(0.1,0,0,1); out1=vec4(0,0.5,0,1); out2=vec4(0,0,0.9,1); }")
    sh = gpu.shader.create_from_info(info)
    t0 = GPUTexture((W, H), format='RGBA16F')
    t1 = GPUTexture((W, H), format='RGBA16F')
    t2 = GPUTexture((W, H), format='RGBA16F')
    fb = GPUFrameBuffer(color_slots=(t0, t1, t2))
    batch = _fs_tri(sh)
    with fb.bind():
        sh.bind()
        batch.draw(sh)
    a0, a1, a2 = (tex_to_np(t, W, H) for t in (t0, t1, t2))
    r0, g1, b2 = a0[0, 0, 0], a1[0, 0, 1], a2[0, 0, 2]
    ok = abs(r0 - 0.1) < 0.01 and abs(g1 - 0.5) < 0.01 and abs(b2 - 0.9) < 0.01
    print("MRT: out0.r=%.3f out1.g=%.3f out2.b=%.3f -> %s"
          % (r0, g1, b2, "PASS (3 attachments distinct)" if ok else "FAIL"))
    return ok


def _fs_tri(sh):
    from gpu_extras.batch import batch_for_shader
    return batch_for_shader(sh, 'TRIS', {"pos": [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]})


# ---- Probe 2 & 3: POINTS draw ---------------------------------------------
def _points_shader(point_size_in_vs):
    info = GPUShaderCreateInfo()
    info.sampler(0, 'FLOAT_2D', "xyzTex")
    info.sampler(1, 'FLOAT_2D', "rgbaTex")
    info.push_constant('INT', "stateSize")
    info.vertex_in(0, 'FLOAT', "dummy")          # attribute present only to set vert count
    info.vertex_out(_vout())
    info.fragment_out(0, 'VEC4', "fragColor")
    ps = "gl_PointSize = 1.0;" if point_size_in_vs else ""
    info.vertex_source(
        "void main(){"
        "  int sx = gl_VertexID % stateSize;"
        "  int sy = gl_VertexID / stateSize;"
        "  vec4 p = texelFetch(xyzTex, ivec2(sx, sy), 0);"
        "  vec4 c = texelFetch(rgbaTex, ivec2(sx, sy), 0);"
        "  if (p.w < 0.5) { gl_Position = vec4(2.0,2.0,0.0,1.0); vColor = vec4(0.0); " + ps + " return; }"
        "  gl_Position = vec4(p.xy * 2.0 - 1.0, 0.0, 1.0);"
        "  " + ps +
        "  vColor = c + dummy * 0.0;"
        "}")
    info.fragment_source("void main(){ fragColor = vColor; }")
    return gpu.shader.create_from_info(info)


def _vout():
    iface = gpu.types.GPUStageInterfaceInfo("vpts")
    iface.smooth('VEC4', "vColor")
    return iface


def _state_textures():
    # 2x2 = 4 agents at the 4 quadrant centers, all alive, white.
    S = 2
    xyz = [0.3, 0.3, 0.0, 1.0,   0.7, 0.3, 0.0, 1.0,
           0.3, 0.7, 0.0, 1.0,   0.7, 0.7, 0.0, 1.0]
    rgba = [1.0, 1.0, 1.0, 1.0] * 4
    xt = GPUTexture((S, S), format='RGBA16F', data=Buffer('FLOAT', len(xyz), xyz))
    ct = GPUTexture((S, S), format='RGBA16F', data=Buffer('FLOAT', len(rgba), rgba))
    return S, xt, ct


def _points_batch(sh, count):
    fmt = GPUVertFormat()
    fmt.attr_add(id="dummy", comp_type='F32', len=1, fetch_mode='FLOAT')
    vbo = GPUVertBuf(len=count, format=fmt)
    vbo.attr_fill(id="dummy", data=[0.0] * count)
    batch = GPUBatch(type='POINTS', buf=vbo)
    batch.program_set(sh)
    return batch


def probe_points(additive):
    W = H = 8
    S, xt, ct = _state_textures()
    count = S * S
    target = GPUTexture((W, H), format='RGBA16F')
    fb = GPUFrameBuffer(color_slots=(target,))
    try:
        sh = _points_shader(point_size_in_vs=True)
        ps_in_vs = True
    except Exception as e:
        print("   (gl_PointSize in VS rejected: %r -> using state point_size)" % e)
        sh = _points_shader(point_size_in_vs=False)
        ps_in_vs = False
    batch = _points_batch(sh, count)
    with fb.bind():
        gpu.state.active_framebuffer_get().clear(color=(0.25, 0.0, 0.0, 0.0) if additive else (0.0, 0.0, 0.0, 0.0))
        if additive:
            gpu.state.blend_set('ADDITIVE_PREMULT')   # ONE,ONE
        else:
            gpu.state.blend_set('NONE')
        if not ps_in_vs:
            gpu.state.point_size_set(1.0)
        sh.bind()
        sh.uniform_int("stateSize", S)
        sh.uniform_sampler("xyzTex", xt)
        sh.uniform_sampler("rgbaTex", ct)
        batch.draw(sh)
        gpu.state.blend_set('NONE')
    a = tex_to_np(target, W, H)
    lit = int((a[:, :, 1] > 0.5).sum())  # green channel = deposited white
    if additive:
        rmax = float(a[:, :, 0].max())
        ok = lit >= 1 and rmax > 1.0
        print("ADDITIVE: lit=%d maxR=%.3f -> %s" % (lit, rmax, "PASS (>1.0 accumulation)" if ok else "FAIL"))
    else:
        ok = lit == count
        print("POINTS: lit=%d (expect %d) ps_in_vs=%s -> %s"
              % (lit, count, ps_in_vs, "PASS" if ok else ("PARTIAL" if lit > 0 else "FAIL")))
    return ok


def run():
    print("=== SPIKE POINTS (MRT / POINTS / ADDITIVE) ===")
    for name, fn in (("MRT", probe_mrt),
                     ("POINTS", lambda: probe_points(False)),
                     ("ADDITIVE", lambda: probe_points(True))):
        try:
            fn()
        except Exception as e:
            print("%s: EXC %r" % (name, e))
            traceback.print_exc()
    print("NMSPIKE DONE")
    sys.stdout.flush()


if bpy.app.background:
    run()
else:
    def _t():
        try:
            run()
        except Exception:
            traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None
    bpy.app.timers.register(_t, first_interval=0.5)
