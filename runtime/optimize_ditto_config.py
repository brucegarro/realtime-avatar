#!/usr/bin/env python3
"""
Optimize Ditto config for faster inference with CUDA.

This script reduces diffusion sampling steps and frame overlap
to achieve ~40-50% speedup with minimal quality impact.
"""
import pickle
import os
import sys
from pathlib import Path

def optimize_config(input_path, output_path, 
                   sampling_timesteps=10,
                   overlap_v2=2):
    """
    Create optimized Ditto config for speed.
    
    Args:
        input_path: Path to original config .pkl file
        output_path: Path to save optimized config
        sampling_timesteps: Diffusion steps (default 10, original 50)
        overlap_v2: Frame overlap (default 2, original 10)
    """
    print(f"Loading config from: {input_path}")
    with open(input_path, 'rb') as f:
        cfg = pickle.load(f)
    
    # Optimize for speed
    if 'default_kwargs' in cfg:
        orig_steps = cfg['default_kwargs'].get('sampling_timesteps', 50)
        orig_overlap = cfg['default_kwargs'].get('overlap_v2', 10)
        
        cfg['default_kwargs']['sampling_timesteps'] = sampling_timesteps
        cfg['default_kwargs']['overlap_v2'] = overlap_v2
        
        print(f"Optimizations applied:")
        print(f"  sampling_timesteps: {orig_steps} → {sampling_timesteps}")
        print(f"  overlap_v2: {orig_overlap} → {overlap_v2}")
    
    # Save optimized config
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        pickle.dump(cfg, f)
    
    print(f"Optimized config saved to: {output_path}")
    print("\nExpected performance: 40-50% faster inference")
    print("Note: Slightly reduced quality trade-off for speed")

if __name__ == '__main__':
    # Default paths
    base_path = Path('/app/ditto-talkinghead/checkpoints/ditto_cfg')
    input_cfg = base_path / 'v0.4_hubert_cfg_pytorch.pkl'
    output_cfg = base_path / 'v0.4_hubert_cfg_pytorch_fast.pkl'
    
    # Allow override from command line
    if len(sys.argv) > 1:
        input_cfg = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_cfg = Path(sys.argv[2])
    
    if not input_cfg.exists():
        print(f"Error: Config file not found: {input_cfg}")
        sys.exit(1)
    
    optimize_config(str(input_cfg), str(output_cfg))
