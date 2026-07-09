#define nmTex(s, uv) (texelFetch((s), clamp(ivec2(floor((uv)*vec2(textureSize((s),0)))), ivec2(0), textureSize((s),0)-ivec2(1)), 0))
/*
 * High pass - combine pass: hp = src - blur + 0.5 gray, optional luminance-only
 */

float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 src = nmTex(inputTex, uv);
    vec4 blur = nmTex(blurTex, uv);
    vec3 diff = src.rgb - blur.rgb;
    vec3 hp = mono ? vec3(lum(diff) + 0.5) : (diff + 0.5);
    fragColor = vec4(clamp(hp, 0.0, 1.0), src.a);
}
