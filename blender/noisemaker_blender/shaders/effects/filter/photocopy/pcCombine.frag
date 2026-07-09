#define nmTex(s, uv) (texelFetch((s), clamp(ivec2(floor((uv)*vec2(textureSize((s),0)))), ivec2(0), textureSize((s),0)-ivec2(1)), 0))
/*
 * Photocopy - combine pass.
 *
 * band = lum(src) - lum(blur) is the difference-of-Gaussians edge signal:
 * positive on the light side of an edge, negative on the dark side.
 * edgeInk = clamp(-band * gain, 0, 1) keeps only the dark side, gained by
 * `darkness` (mix(2, 10, darkness/100)).
 *
 * Midtone dropout: smoothstep(0.75, 0.4, lumSrc) is a FALLING ramp
 * (edge0=0.75 > edge1=0.4 by design: the standard clamp/mix smoothstep
 * formula extends gracefully to edge0 > edge1, producing 1 at/below 0.4
 * and 0 at/above 0.75) that zeroes edgeInk in bright source regions, so
 * only edges over darker material ink in. A second falling ramp,
 * smoothstep(0.12, 0.06, lumSrc), adds solid ink in deep shadows
 * (lumSrc < 0.12) regardless of edge content, ramping to full strength by
 * lumSrc <= 0.06. Total ink is clamped to 1.
 *
 * tonemap2 (S9): t=1 -> paper, so 1-ink means full ink -> ink color, zero
 * ink -> paper color. Alpha is taken from the source, not the blur.
 *
 * No directional light, no rotation, no nm_fragment-coordinate-derived
 * vectors anywhere in this pass (DoG is isotropic) - GLSL and WGSL are
 * textually identical, no Y-orientation compensation needed.
 */

float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

vec3 tonemap2(float t, vec3 ink, vec3 paper) {
    return mix(ink, paper, clamp(t, 0.0, 1.0));
}

void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 src = nmTex(inputTex, uv);
    vec4 blur = nmTex(blurTex, uv);

    float lumSrc = lum(src.rgb);
    float lumBlur = lum(blur.rgb);
    float band = lumSrc - lumBlur;

    float gain = mix(2.0, 10.0, darkness / 100.0);
    float edgeInk = clamp(-band * gain, 0.0, 1.0);

    float ink = edgeInk * (1.0 - smoothstep(0.4, 0.75, lumSrc));
    ink = clamp(ink + (1.0 - smoothstep(0.06, 0.12, lumSrc)), 0.0, 1.0);

    vec3 outColor = tonemap2(1.0 - ink, inkColor, paperColor);
    fragColor = vec4(outColor, src.a);
}
