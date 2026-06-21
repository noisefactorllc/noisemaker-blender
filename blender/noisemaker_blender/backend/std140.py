"""std140 uniform-block layout + packing for the UBO path (PUSH_OVER_128 effects).

Effects whose push-constant block exceeds Metal's 128-byte limit are compiled with a std140
uniform buffer instead of push constants (see docs/BLENDER-PLATFORM-NOTES.md). This module is
the single source of truth for the block layout, shared by:
  - shader_build  — generates the GLSL struct typedef + the bare-name #defines, and
  - gpu_backend   — packs the uniform values into the matching std140 byte buffer.

Verified against Blender's actual struct layout by blender/harness/spike_ubo*.py (the std140
alignment traps — vec3 to 16, vec2 to 8 after a vec3 — land exactly where this computes them).
"""
import struct as _struct

import numpy as np

# std140 alignment/size in bytes. BOOL is declared as `int` in the block: std140 bool is a
# 4-byte uint but MSL bool is 1 byte, so declaring int avoids the cross-compiler ambiguity;
# the bare-name #define then expands a bool field to `(nm_ub.x != 0)` (a real bool expr).
_ALIGN = {"FLOAT": 4, "INT": 4, "BOOL": 4, "VEC2": 8, "VEC3": 16, "VEC4": 16,
          "IVEC2": 8, "IVEC3": 16, "IVEC4": 16}
# SIZE: a vec3 occupies 16 bytes here, NOT std140's 12. Blender's GLSL->MSL maps vec3 -> Metal
# `float3`, which is 16 bytes — so a scalar following a vec3 lands at +16, not +12. Using 12
# (textbook std140) silently shifts every field after the first vec3->scalar boundary (verified
# the hard way: noise's `wrap`/palette params read from the wrong offset — spike_ubo4.py).
_SIZE = {"FLOAT": 4, "INT": 4, "BOOL": 4, "VEC2": 8, "VEC3": 16, "VEC4": 16,
         "IVEC2": 8, "IVEC3": 16, "IVEC4": 16}
_GLSL = {"FLOAT": "float", "INT": "int", "BOOL": "int", "VEC2": "vec2", "VEC3": "vec3",
         "VEC4": "vec4", "IVEC2": "ivec2", "IVEC3": "ivec3", "IVEC4": "ivec4"}

STRUCT_NAME = "NmUniforms"
INSTANCE = "nm_ub"


def layout(fields):
    """fields: [(ctype, name)] in declaration order. Returns (entries, nfloats) where
    entries = [(ctype, name, byte_offset)] and nfloats = block size in floats (the block size
    is rounded up to a multiple of 16 bytes per std140)."""
    off = 0
    entries = []
    for ctype, name in fields:
        a = _ALIGN[ctype]
        off = (off + a - 1) // a * a
        entries.append((ctype, name, off))
        off += _SIZE[ctype]
    size = (off + 15) // 16 * 16
    return entries, size // 4


def struct_source(fields):
    """The GLSL struct typedef for these fields (declaration order)."""
    body = "".join("  %s %s;\n" % (_GLSL[t], n) for t, n in fields)
    return "struct %s {\n%s};\n" % (STRUCT_NAME, body)


# GLSL type keywords — a uniform name immediately preceded by one is a *declaration*
# (a local/param that shadows the uniform), not a reference to rewrite.
_TYPE_KW = frozenset((
    "float", "int", "bool", "uint", "double", "void",
    "vec2", "vec3", "vec4", "ivec2", "ivec3", "ivec4",
    "uvec2", "uvec3", "uvec4", "bvec2", "bvec3", "bvec4",
    "mat2", "mat3", "mat4", "mat2x2", "mat3x3", "mat4x4",
    "sampler2D", "sampler3D", "samplerCube", "isampler2D", "usampler2D"))

_TOKEN = __import__("re").compile(r"//[^\n]*|/\*.*?\*/|[A-Za-z_]\w*|\s+|.", __import__("re").DOTALL)

# GLSL builtin functions the corpus shadows with local variables, e.g. the inlined rgb->hsl
# helper's `float max = max(r, max(g, b)); float min = min(r, min(g, b));`. Blender's MSL
# backend rejects calling a builtin once a same-named local is in scope ("called object type
# 'float' is not a function"); ANGLE (the reference path) accepts it. We rename the LOCAL.
_SHADOWABLE = frozenset(("max", "min", "mod", "mix", "clamp", "step", "smoothstep",
                         "fract", "abs", "sign", "floor", "ceil", "round"))


def rename_shadow_builtins(src):
    """Rename local variables/params that shadow a GLSL builtin function (`_SHADOWABLE`) to
    `nm_<name>`, scope-aware: the rename covers the declaration and its in-scope uses, but NOT
    the builtin call in the local's own initializer (`float max = max(...)` -> `float nm_max =
    max(...)`). A no-op for sources without such a shadow (lossless tokenize+reconstruct), so
    it is safe to run on every effect. Verified non-regressing via compile_check."""
    out = []
    scopes = [{}]             # stack of {orig: renamed}
    pending = {}              # param renames -> enter the next {}
    paren = 0
    last_sig = None
    member_next = False
    decl_name = None          # name being declared this statement; its initializer keeps the builtin
    for m in _TOKEN.finditer(src):
        t = m.group(0)
        if t.startswith("//") or t.startswith("/*") or t.isspace():
            out.append(t)
            continue
        if t == "{":
            scopes.append(dict(pending)); pending = {}; out.append(t); last_sig = "{"; member_next = False
        elif t == "}":
            if len(scopes) > 1:
                scopes.pop()
            out.append(t); last_sig = "}"; member_next = False
        elif t == "(":
            paren += 1; out.append(t); last_sig = "("; member_next = False
        elif t == ")":
            paren = max(0, paren - 1); out.append(t); last_sig = ")"; member_next = False
        elif t == ";":
            decl_name = None; pending = {}; out.append(t); last_sig = ";"; member_next = False
        elif t == ".":
            out.append(t); last_sig = "."; member_next = True
        elif t[:1].isalpha() or t[:1] == "_":
            if member_next:
                out.append(t); member_next = False; last_sig = t
            elif last_sig in _TYPE_KW and t in _SHADOWABLE:        # decl of a builtin-named local
                new = "nm_" + t
                (pending if paren > 0 else scopes[-1])[t] = new
                if paren == 0:
                    decl_name = t                                  # keep the builtin in its initializer
                out.append(new); last_sig = t
            else:                                                  # a use
                ren = None
                for s in reversed(scopes):
                    if t in s:
                        ren = s[t]; break
                out.append(ren if (ren and t != decl_name) else t)
                last_sig = t
            member_next = False
        else:
            out.append(t); last_sig = t; member_next = False
    return "".join(out)


def rewrite_uniform_refs(src, fields):
    """Rewrite references to the uniform names in `src` to `nm_ub.<name>`, SCOPE-AWARE: a name
    declared as a function parameter or local variable shadows the uniform (GLSL scoping), so
    that declaration and its in-scope uses are left untouched. This is what an anonymous std140
    block would give for free — but Blender's create_from_info only supports a NAMED block, so
    we must qualify the references ourselves (verified necessary by spike_ubo3.py).

    Member accesses (`foo.name`), declaration names, and comments are never rewritten. Handles
    the real collisions in the corpus (noise's `octaves`, cellNoise's `scale`, shapes' `seed`
    are all function params)."""
    U = set(n for _, n in fields)
    if not U:
        return src
    out = []
    scopes = [set()]          # stack of shadowed-name sets; index 0 = global (no shadow)
    pending = set()           # params declared in the current () -> enter the next {}
    paren = 0
    last_sig = None           # last significant token (skips whitespace/comments)
    member_next = False       # the previous significant token was '.'
    for m in _TOKEN.finditer(src):
        t = m.group(0)
        if t.startswith("//") or t.startswith("/*") or t.isspace():
            out.append(t)
            continue
        if t == "{":
            scopes.append(set(pending)); pending = set(); out.append(t); last_sig = "{"; member_next = False
        elif t == "}":
            if len(scopes) > 1:
                scopes.pop()
            out.append(t); last_sig = "}"; member_next = False
        elif t == "(":
            paren += 1; out.append(t); last_sig = "("; member_next = False
        elif t == ")":
            paren = max(0, paren - 1); out.append(t); last_sig = ")"; member_next = False
        elif t == ";":
            pending = set(); out.append(t); last_sig = ";"; member_next = False   # end stmt/prototype
        elif t == ".":
            out.append(t); last_sig = "."; member_next = True
        elif t[:1].isalpha() or t[:1] == "_":
            if member_next:                                  # member access: leave as-is
                out.append(t); member_next = False; last_sig = t
            elif last_sig in _TYPE_KW:                       # declaration of `t`
                if t in U:
                    (pending if paren > 0 else scopes[-1]).add(t)
                out.append(t); last_sig = t
            elif t in U and not any(t in s for s in scopes):  # a genuine uniform reference
                out.append(INSTANCE + "." + t); last_sig = t
            else:
                out.append(t); last_sig = t
        else:
            out.append(t); last_sig = t; member_next = False
    return "".join(out)


def pack(fields, values):
    """Pack values (dict name->value) into a std140 float32 numpy array matching layout().
    Ints/bools are bit-cast into the float buffer — only the bytes matter; the shader reads
    them back per the struct's int/float field types. Missing values stay zero."""
    entries, nfloats = layout(fields)
    buf = bytearray(nfloats * 4)
    for ctype, name, off in entries:
        v = values.get(name)
        if v is None:
            continue
        if ctype == "FLOAT":
            _struct.pack_into("<f", buf, off, float(v))
        elif ctype == "INT":
            _struct.pack_into("<i", buf, off, int(v))
        elif ctype == "BOOL":
            _struct.pack_into("<i", buf, off, 1 if v else 0)
        elif ctype in ("VEC2", "VEC3", "VEC4"):
            for i, c in enumerate(list(v)):
                _struct.pack_into("<f", buf, off + 4 * i, float(c))
        elif ctype in ("IVEC2", "IVEC3", "IVEC4"):
            for i, c in enumerate(list(v)):
                _struct.pack_into("<i", buf, off + 4 * i, int(c))
    # np.frombuffer preserves the exact bytes (incl. int bit patterns that look like NaN
    # floats) — pure-Python float() round-trips would not.
    return np.frombuffer(bytes(buf), dtype=np.float32).copy()
