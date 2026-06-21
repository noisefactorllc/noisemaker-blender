"""Build a Blender GPUShader from a transpiled (.frag + .createinfo.json) pair.

This is the core of the backend's compileProgram step, factored out so the
compile-check harness and the executor share one code path. See PORTING-GUIDE.md.
"""
import gpu
from gpu.types import GPUShaderCreateInfo, GPUStageInterfaceInfo

# Fullscreen-triangle vertex shader shared by every effect (body uses gl_FragCoord).
VERT_SRC = "void main(){ gl_Position = vec4(pos, 0.0, 1.0); }"


def build_create_info(frag_src, descriptor, defines=None):
    """Assemble a GPUShaderCreateInfo from a transpiled descriptor + body."""
    info = GPUShaderCreateInfo()
    for ctype, name in descriptor.get("pushConstants", []):
        info.push_constant(ctype, name)
    for slot, stype, name in descriptor.get("samplers", []):
        info.sampler(slot, stype, name)
    for slot, otype, name in descriptor.get("fragmentOut", []):
        info.fragment_out(slot, otype, name)
    info.vertex_in(0, 'VEC2', "pos")
    info.vertex_source(VERT_SRC)
    header = ""
    if defines:
        header = "".join("#define %s %s\n" % (k, v) for k, v in defines.items())
    info.fragment_source(header + frag_src)
    return info


def build_shader(frag_src, descriptor, defines=None):
    """Compile and return a GPUShader (raises on MSL compile error)."""
    return gpu.shader.create_from_info(build_create_info(frag_src, descriptor, defines))


def build_create_info_vf(vert_src, frag_src, descriptor, defines=None):
    """Assemble a GPUShaderCreateInfo for a vertex+fragment program (points/billboards
    deposit, 3D render). Uses the program's own vertex shader (gl_VertexID-driven) plus a
    vertex->fragment varying interface, instead of the fullscreen-triangle VS."""
    info = GPUShaderCreateInfo()
    for ctype, name in descriptor.get("pushConstants", []):
        info.push_constant(ctype, name)
    for slot, stype, name in descriptor.get("samplers", []):
        info.sampler(slot, stype, name)
    for slot, otype, name in descriptor.get("fragmentOut", []):
        info.fragment_out(slot, otype, name)
    for slot, vtype, name in descriptor.get("vertexIn", []):
        info.vertex_in(slot, vtype, name)
    varyings = descriptor.get("varyings", [])
    if varyings:
        iface = GPUStageInterfaceInfo("nm_iface")
        for interp, vtype, name in varyings:
            getattr(iface, interp)(vtype, name)
        info.vertex_out(iface)
    header = ""
    if defines:
        header = "".join("#define %s %s\n" % (k, v) for k, v in defines.items())
    info.vertex_source(header + vert_src)
    info.fragment_source(header + frag_src)
    return info


def build_shader_vf(vert_src, frag_src, descriptor, defines=None):
    """Compile and return a vertex+fragment GPUShader (raises on MSL compile error)."""
    return gpu.shader.create_from_info(build_create_info_vf(vert_src, frag_src, descriptor, defines))
