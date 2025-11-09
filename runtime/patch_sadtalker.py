#!/usr/bin/env python3
"""Patch SadTalker for MPS compatibility"""

file_path = "SadTalker/src/facerender/modules/util.py"

with open(file_path, 'r') as f:
    lines = f.readlines()

# Patch make_coordinate_grid_2d
for i in range(len(lines)):
    if 'x = torch.arange(w, dtype=torch.float32, device=heatmap.device)' in lines[i]:
        lines[i] = '    device = type.split(".")[-2] if "mps" in type or "cuda" in type else "cpu"\n'
        lines.insert(i+1, '    x = torch.arange(w, dtype=torch.float32, device=device)\n')
        lines.pop(i+2)  # Remove old x line
        print(f"Fixed make_coordinate_grid_2d at line {i+1}")
        break

# Patch make_coordinate_grid  
for i in range(len(lines)):
    if 'x = torch.arange(w, dtype=torch.float32, device=heatmap.device)' in lines[i]:
        # This is the second occurrence in make_coordinate_grid
        lines[i] = '    device = type.split(".")[-2] if "mps" in type or "cuda" in type else "cpu"\n'
        lines.insert(i+1, '    x = torch.arange(w, dtype=torch.float32, device=device)\n')
        lines.insert(i+2, '    y = torch.arange(h, dtype=torch.float32, device=device)\n')
        lines.insert(i+3, '    z = torch.arange(d, dtype=torch.float32, device=device)\n')
        # Remove old lines
        lines.pop(i+4)  # old y
        lines.pop(i+4)  # old z  
        print(f"Fixed make_coordinate_grid at line {i+1}")
        break

with open(file_path, 'w') as f:
    f.writelines(lines)

print("✅ Patched SadTalker for MPS")
