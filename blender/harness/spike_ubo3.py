"""Decide the UBO body-reference strategy. The blunt `#define name nm_ub.name` breaks when a
uniform name is reused as a function parameter/local (e.g. noise's multires(int octaves,...)):
the preprocessor rewrites the *declaration* too. The reference uses an ANONYMOUS std140 block
so members sit at global scope and a local param naturally shadows them (no body rewrite).

Test, in order, whether Blender's create_from_info can express that:
  A) anonymous block: uniform_buf(0, "NmU", "")  -> members global, local param shadows
  B) named block with a deliberate shadowing param (control: confirms the failure mode)

Usage: blender --factory-startup --python blender/harness/spike_ubo3.py
"""
import sys
import traceback

import bpy
import gpu
from gpu.types import GPUShaderCreateInfo, GPUUniformBuf, Buffer

STRUCT = "struct NmU { int octaves; float xScale; };\n"
# A helper with a parameter named `octaves` (shadows the uniform) — the exact noise pattern.
# Global use of octaves (uniform) in main; local use in helper (param).
BODY_GLOBAL = (
    "float helper(int octaves){ float a = 0.0; for(int i=0;i<octaves;i++) a+=1.0; return a; }\n"
    "void main(){ fragColor = vec4(helper(2) + float(octaves)*0.0 + xScale, 0.0, 0.0, 1.0); }\n")


def try_variant(label, make_info):
    try:
        info = make_info()
        info.fragment_out(0, 'VEC4', "fragColor")
        info.vertex_in(0, 'VEC2', "pos")
        info.vertex_source("void main(){ gl_Position = vec4(pos,0.0,1.0); }")
        sh = gpu.shader.create_from_info(info)
        print("SPIKE %-22s COMPILE OK" % label)
        return True
    except Exception as e:
        print("SPIKE %-22s FAIL: %s" % (label, str(e).splitlines()[0][:80]))
        return False


def variantA():
    info = GPUShaderCreateInfo()
    info.typedef_source(STRUCT)
    info.uniform_buf(0, "NmU", "")          # anonymous instance?
    info.fragment_source(BODY_GLOBAL)
    return info


def variantA2():
    info = GPUShaderCreateInfo()
    info.typedef_source(STRUCT)
    info.uniform_buf(0, "NmU", "_")         # minimal name, members still need _.x ? (control)
    info.fragment_source(BODY_GLOBAL.replace("octaves)*0.0 + xScale",
                                             "octaves)*0.0 + _.xScale").replace(
                                             "float(octaves)", "float(_.octaves)"))
    return info


def run():
    print("=== A: anonymous block (empty instance name), body uses bare globals ===")
    okA = try_variant("anon-empty-name", variantA)
    print("=== A2: named '_' instance (control, refs via _.) ===")
    try_variant("named-underscore", variantA2)
    print()
    print("SPIKE VERDICT:", "ANON WORKS — use anonymous block, no body rewrite" if okA
          else "ANON UNSUPPORTED — need scope-aware rewrite or local-rename")
    sys.stdout.flush()


if bpy.app.background:
    print("SPIKE FAIL: GPU needs GUI mode; run without -b")
else:
    def _t():
        try:
            run()
        except Exception:
            traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None
    bpy.app.timers.register(_t, first_interval=0.5)
