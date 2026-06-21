void main() {
    // Each particle deposits a nm_constant value
    // The nm_kernel convolution will spread this according to K(r)
    fragColor = vec4(depositAmount, 0.0, 0.0, 1.0);
}
