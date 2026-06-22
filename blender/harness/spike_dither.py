"""De-risk the dither fix: (A) const-array global passed to an array function param, and
(B) a function prototype + later definition ("class member cannot be redeclared").

For each variant, build a minimal fragment shader via create_from_info and report whether it
compiles on Metal. Confirms the two transforms before wiring them into the transpiler.

Usage: blender --factory-startup --python blender/harness/spike_dither.py
"""
import os
import sys
import traceback

import bpy
import gpu
from gpu.types import GPUShaderCreateInfo

PAL = ("const vec3 PAL[4] = vec3[4](vec3(0.0), vec3(0.3), vec3(0.6), vec3(1.0));\n")
FIND = ("vec3 findClosest4(vec3 color, %s vec3 pal[4]) {\n"
        "  vec3 best = pal[0];\n"
        "  float md = dot(color-pal[0], color-pal[0]);\n"
        "  for (int i=1;i<4;i++){ vec3 d=color-pal[i]; float e=dot(d,d); if(e<md){md=e;best=pal[i];} }\n"
        "  return best;\n}\n")
MAIN_FIND = "void main(){ fragColor = vec4(findClosest4(vec3(0.5), PAL), 1.0); }\n"

# (B) prototype + definition
PROTO = "vec3 ident(vec3 c);\n"
DEF = "vec3 ident(vec3 c){ return c; }\n"
MAIN_ID = "void main(){ fragColor = vec4(ident(vec3(0.5)), 1.0); }\n"

VARIANTS = [
    ("A0 array-param, no const (REPRO)", PAL + FIND % "" + MAIN_FIND),
    ("A1 array-param, const param (FIX)", PAL + FIND % "const" + MAIN_FIND),
    ("B0 prototype + definition (REPRO)", PROTO + DEF + MAIN_ID),
    ("B1 definition only (FIX)", DEF + MAIN_ID),
]


def compiles(frag):
    info = GPUShaderCreateInfo()
    info.fragment_out(0, 'VEC4', "fragColor")
    info.vertex_in(0, 'VEC2', "pos")
    info.vertex_source("void main(){ gl_Position = vec4(pos,0.0,1.0); }")
    info.fragment_source(frag)
    try:
        gpu.shader.create_from_info(info)
        return True, ""
    except Exception as e:
        return False, str(e).splitlines()[0]


def run():
    for name, frag in VARIANTS:
        ok, err = compiles(frag)
        print("SPIKE %-38s -> %s %s" % (name, "OK   " if ok else "FAIL ", "" if ok else err))
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
