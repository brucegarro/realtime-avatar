#!/usr/bin/env python3
"""
Test loading multiple Ditto instances sequentially (no threading)
"""
import sys
import os
import time

sys.path.insert(0, '/app')
sys.path.insert(0, '/app/runtime')
os.chdir('/app/runtime')

print("\n" + "="*70)
print("🔍 MULTIPLE DITTO INSTANCES TEST (Sequential)")
print("="*70)

from models.ditto_model import DittoModel
import torch

print("\n[1/3] Loading Ditto instance #1...")
start = time.time()
ditto1 = DittoModel(device="cuda")
elapsed = time.time() - start
print(f"✅ Ditto #1 loaded in {elapsed:.1f}s")

if torch.cuda.is_available():
    mem = torch.cuda.memory_allocated("cuda") / 1024**3
    print(f"💾 GPU Memory: {mem:.2f}GB")

print("\n[2/3] Loading Ditto instance #2...")
start = time.time()
ditto2 = DittoModel(device="cuda")
elapsed = time.time() - start
print(f"✅ Ditto #2 loaded in {elapsed:.1f}s")

if torch.cuda.is_available():
    mem = torch.cuda.memory_allocated("cuda") / 1024**3
    print(f"💾 GPU Memory: {mem:.2f}GB")

print("\n[3/3] Loading Ditto instance #3...")
start = time.time()
ditto3 = DittoModel(device="cuda")
elapsed = time.time() - start
print(f"✅ Ditto #3 loaded in {elapsed:.1f}s")

if torch.cuda.is_available():
    mem = torch.cuda.memory_allocated("cuda") / 1024**3
    print(f"💾 GPU Memory: {mem:.2f}GB")

print("\n" + "="*70)
print("✅ SUCCESS: Multiple Ditto instances work sequentially!")
print("="*70 + "\n")
