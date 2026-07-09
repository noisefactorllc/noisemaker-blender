#define nmTex(s, uv) (texelFetch((s), clamp(ivec2(floor((uv)*vec2(textureSize((s),0)))), ivec2(0), textureSize((s),0)-ivec2(1)), 0))
/*
 * High pass - vertical Gaussian pass
 */

void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 dirPx = vec2(0.0, 1.0);
    float sigma = max(radius * 0.5, 0.001);
    float fTaps = min(radius, 32.0);
    // Beyond 32 taps we can't add more samples (bounded loop), so widen the
    // spacing between them to keep the nm_kernel reaching the full radius.
    float stride = radius > 32.0 ? radius / 32.0 : 1.0;
    vec4 sum = nmTex(inputTex, uv);
    float wsum = 1.0;
    for (int i = 1; i <= 32; i++) {
        if (float(i) > fTaps) { break; }
        float w = exp(-float(i * i) / (2.0 * sigma * sigma));
        vec2 o = dirPx * float(i) * stride / resolution;
        sum += (nmTex(inputTex, uv + o) + nmTex(inputTex, uv - o)) * w;
        wsum += 2.0 * w;
    }
    fragColor = sum / wsum;
}
