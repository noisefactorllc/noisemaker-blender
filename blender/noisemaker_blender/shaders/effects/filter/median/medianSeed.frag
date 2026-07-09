#define nmTex(s, uv) (texelFetch((s), clamp(ivec2(floor((uv)*vec2(textureSize((s),0)))), ivec2(0), textureSize((s),0)-ivec2(1)), 0))
/*
 * Median - seed pass: copies the source image into the ping-pong state
 * texture before the iterated 3x3 median passes run.
 */

void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    fragColor = nmTex(inputTex, uv);
}
