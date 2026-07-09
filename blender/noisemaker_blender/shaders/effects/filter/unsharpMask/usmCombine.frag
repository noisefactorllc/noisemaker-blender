#define nmTex(s, uv) (texelFetch((s), clamp(ivec2(floor((uv)*vec2(textureSize((s),0)))), ivec2(0), textureSize((s),0)-ivec2(1)), 0))
/*
 * Unsharp mask - combine pass: out = img + amount * (img - blur), threshold-gated
 */

void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 src = nmTex(inputTex, uv);
    vec4 blur = nmTex(blurTex, uv);
    vec3 diff = src.rgb - blur.rgb;
    // Soft threshold gate (PS levels 0-255 mapped to 0-100 param): fade in the
    // effect over a half-level band above the threshold to avoid banding.
    float t = threshold / 100.0;
    float mag = max(max(abs(diff.r), abs(diff.g)), abs(diff.b));
    float gate = smoothstep(t, t + 0.02, mag);
    vec3 outc = src.rgb + diff * (amount / 100.0) * gate;
    fragColor = vec4(clamp(outc, 0.0, 1.0), src.a);
}
