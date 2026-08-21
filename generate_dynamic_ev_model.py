import os
import shutil
import json
from pathlib import Path

# ============================================================
# 1) CONFIGURATION & PATHS
# ============================================================
BASE_ZEN_PATH = Path(r"C:\Users\joell\Documents\ETH\Master\master_thesis\ZEN-garden")

model_100_path = BASE_ZEN_PATH / "EV100_carbon_budget"  #change if needed
model_90_path = BASE_ZEN_PATH / "EV90_carbon_budget"  #change if needed
hybrid_model_path = BASE_ZEN_PATH / "EV_dynamic_adoption_carbon_budget"  #change if needed
print("Starting Pure File-Based Model Merge & Registry Patch...")

# ============================================================
# 2) RE-CREATE THE HYBRID DESTINATION FOLDER
# ============================================================
if hybrid_model_path.exists():
    print(f"Removing existing hybrid folder: {hybrid_model_path.name}...")
    shutil.rmtree(hybrid_model_path)

print(f"Copying baseline structure from {model_100_path.name}...")
shutil.copytree(model_100_path, hybrid_model_path)

# ============================================================
# 3) DUAL-BOUNDARY MERGING FOR ALL CARRIERS
# ============================================================
print("\nMerging demand files across ALL carriers...")

# Walk through every directory in the new hybrid model to find carrier folders
for root, dirs, files in os.walk(hybrid_model_path):
    root_path = Path(root)
    
    # We want to process any folder that contains demand configuration files
    demand_files = [f for f in files if f.startswith("demand") and f.endswith(".csv")]
    if not demand_files:
        continue
        
    # Find the corresponding relative path to locate it in 100% and 90% source models
    rel_path = root_path.relative_to(hybrid_model_path)
    dir_100 = model_100_path / rel_path
    dir_90 = model_90_path / rel_path
    
    # Clean up any copied original 'demand' files in the hybrid folder first to prevent mixing
    for d_file in demand_files:
        (root_path / d_file).unlink()
        
    # Gather all unique demand file names present in either source directory
    all_demand_names = set()
    if dir_100.exists():
        all_demand_names.update([f.name for f in dir_100.iterdir() if f.is_file() and f.name.startswith("demand") and f.name.endswith(".csv")])
    if dir_90.exists():
        all_demand_names.update([f.name for f in dir_90.iterdir() if f.is_file() and f.name.startswith("demand") and f.name.endswith(".csv")])
        
    for name in all_demand_names:
        file_100 = dir_100 / name if dir_100.exists() else Path("")
        file_90 = dir_90 / name if dir_90.exists() else Path("")
        
        # Determine the new names (e.g., demand_2030.csv -> demand_100_2030.csv / demand_90_2030.csv)
        name_100 = name.replace("demand", "demand_100", 1)
        name_90 = name.replace("demand", "demand_90", 1)
        
        target_100 = root_path / name_100
        target_90 = root_path / name_90
        
        # 1. Inject the 100% Boundary
        if file_100.exists():
            shutil.copy(file_100, target_100)
        
        # 2. Inject the 90% Boundary
        if file_90.exists():
            shutil.copy(file_90, target_90)
            
        # 3. Fallback Security: If a carrier (like ammonia) has a file in 100% but not 90% (or vice-versa),
        # duplicate it so that D1 == D2 perfectly for that unchanged parameter.
        if target_100.exists() and not target_90.exists():
            shutil.copy(target_100, target_90)
        elif target_90.exists() and not target_100.exists():
            shutil.copy(target_90, target_100)

print("Demand file restructuring completed successfully for all carriers.")

# ============================================================
# 4) AUTOMATIC ATTRIBUTES.JSON REGISTRY PATCHER
# ============================================================
print("\n Scanning and patching ZEN-garden attributes.json files...")

def add_demand_variants(d):
    """Recursively checks and updates config schemas to allow demand_100 and demand_90."""
    modified = False
    if isinstance(d, dict):
        if "demand" in d and isinstance(d["demand"], dict):
            if "demand_100" not in d:
                d["demand_100"] = d["demand"].copy()
                modified = True
            if "demand_90" not in d:
                d["demand_90"] = d["demand"].copy()
                modified = True
        for k, v in d.items():
            if add_demand_variants(v):
                modified = True
    return modified

# Find all registry files in your master thesis directory tree
attributes_paths = list(BASE_ZEN_PATH.rglob("attributes.json"))
patch_count = 0

for attr_path in attributes_paths:
    # Skip output or cache directories
    if "outputs" in attr_path.parts or ".git" in attr_path.parts:
        continue
    try:
        with open(attr_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if add_demand_variants(data):
            with open(attr_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"Patched schema rules in: {attr_path.relative_to(BASE_ZEN_PATH)}")
            patch_count += 1
    except Exception as e:
        print(f"Could not automatically patch {attr_path.name}: {e}")

if patch_count == 0:
    print("No attributes.json files needed patching (they might already be up to date).")

print(f"\nDynamic model successfully built and configured at:\n {hybrid_model_path}\n")