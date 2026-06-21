// DLA - Deposit stuck agents to anchor grid (nm_fragment shader)

void main() {
    // Discard if not a stuck agent
    if (v_weight < 0.5) {
        discard;
    }
    
    // Deposit energy with agent color
    // deposit range [0.5, 20] maps to energy [0.05, 2.0]
    float energy = deposit * 0.1;
    fragColor = vec4(v_color * energy, energy);
}
