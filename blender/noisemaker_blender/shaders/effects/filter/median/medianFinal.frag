#define nmTex(s, uv) (texelFetch((s), clamp(ivec2(floor((uv)*vec2(textureSize((s),0)))), ivec2(0), textureSize((s),0)-ivec2(1)), 0))
/*
 * Median - final pass: threshold-gated mix between the original image and
 * the fully-iterated median result. threshold == 0 always uses the plain
 * median (classic Photoshop Median filter); threshold > 0 only replaces
 * pixels whose original/median difference exceeds the threshold (Dust &
 * Scratches behavior), leaving larger detail untouched.
 */

void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 orig = nmTex(inputTex, uv);
    vec4 med = nmTex(medTex, uv);

    vec3 d = abs(orig.rgb - med.rgb);
    float maxDiff = max(max(d.r, d.g), d.b);
    float gate = (threshold <= 0.0) ? 1.0 : step(threshold / 100.0, maxDiff);

    fragColor = vec4(mix(orig.rgb, med.rgb, gate), orig.a);
}
