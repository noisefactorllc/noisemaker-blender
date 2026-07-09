#define nmTex(s, uv) (texelFetch((s), clamp(ivec2(floor((uv)*vec2(textureSize((s),0)))), ivec2(0), textureSize((s),0)-ivec2(1)), 0))
/*
 * Photocopy - horizontal Gaussian pass.
 *
 * Separable blur of the source image (S3 snippet). The blurred result
 * feeds pcBlurV, and pcCombine reads its luminance as the low-passed half
 * of the difference-of-Gaussians edge band.
 *
 * radius = mix(1.0, 24.0, (detail-1)/99): higher detail -> larger blur
 * radius -> the DoG band captures coarser edges (Photoshop Photocopy's
 * "Detail" slider).
 */

void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 dirPx = vec2(1.0, 0.0);
    float radius = mix(1.0, 24.0, (detail - 1.0) / 99.0);
    float sigma = max(radius * 0.5, 0.001);
    float fTaps = min(radius, 32.0);
    vec4 sum = nmTex(inputTex, uv);
    float wsum = 1.0;
    for (int i = 1; i <= 32; i++) {
        if (float(i) > fTaps) { break; }
        float w = exp(-float(i * i) / (2.0 * sigma * sigma));
        vec2 o = dirPx * float(i) / resolution;
        sum += (nmTex(inputTex, uv + o) + nmTex(inputTex, uv - o)) * w;
        wsum += 2.0 * w;
    }
    fragColor = sum / wsum;
}
