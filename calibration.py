from pathlib import Path
import pandas as pd
import numpy as np
from zen_creator.model import Model
from zen_creator.datasets.datasets.metadata import MetaData
from zen_creator.datasets.datasets.metadata import SourceInformation
from zen_creator.datasets.datasets.entsoe_powerplants import EntsoePPDataset 
from zen_creator.datasets.datasets.tyndp2024 import TYNDP2024Dataset

# 1) Load existing model
model = Model.from_existing(Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden/europe_but_better_cleaned")) 

# 2) Modify model
model.output_folder = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden")
model.name = "Europe_calibrated"

# 3) Load new dataset
entsoe_ds = EntsoePPDataset(source_path=Path("C:/Users/joell/Documents/ETH/Master/master_thesis/datasets"))
tyndp_ds = TYNDP2024Dataset(source_path=Path("C:/Users/joell/Documents/ETH/Master/master_thesis/datasets"))

thesis_metadata = MetaData(
    name="thesis_modifications",
    author=["Joel"], # Remember, author must be a list!
    publication_year=2026,
    title="Manual modifications for Master Thesis",
    publication="ETH Zurich",
    url=""
)

# 4) Change parameters
# ================================================
# 1. Only for technologies in technology_list: set capacity_existing based on new dataset
# ================================================
technology_list = ["battery", "biomass_plant", "hard_coal_plant", "lignite_coal_plant", "natural_gas_turbine", "nuclear", "oil_plant", 
                #"photovoltaics", 
                "reservoir_hydro", 
                "run-of-river_hydro", 
                "waste_plant", 
                "wind_offshore", 
                "wind_onshore", 
                "pumped_hydro"]
for tech_name in technology_list:
    if tech_name not in model.elements:
        continue
    technology = model.elements[tech_name]

    # Temporäres Attribut mit dem korrekten DataFrame erzeugen
    temp_attr = entsoe_ds.get_capacity(technology)
    
    technology.capacity_existing.set_data(
        df=temp_attr.df,           # the fully prepared MultiIndex DataFrame
        unit=temp_attr.unit,
        source=temp_attr.sources[0]
    )

    # Automated synchronization for storage (pumped storage & batteries)
    if hasattr(technology, "capacity_existing_energy"):
        # Select specific ratio
        if tech_name == "battery":
            ep_ratio = 2.0  # example: 2 hours of storage for batteries
        else:
            ep_ratio = 6.0  # Standard 6 hours for hydro storage, adjust as needed
        
        df_energy = pd.DataFrame({
            "capacity_existing_energy": temp_attr.df["capacity_existing"] * ep_ratio
        })
        
        technology.capacity_existing_energy.set_data(
            df=df_energy,
            unit="GWh",
            source=temp_attr.sources[0]
        )
        print(f"Synchronized: {tech_name} with {ep_ratio}")


# ================================================
# 2. lifetime has to be extended by +10 years for all fossil technologies 
# (to prevent early retirements due to the new dataset already including all active plants in 2025)
# ================================================
fossil_techs = ["hard_coal_plant", "lignite_coal_plant", "natural_gas_turbine", "oil_plant"]

for tech_name in fossil_techs:
    if tech_name not in model.elements:
        continue
        
    technology = model.elements[tech_name]
    
    if hasattr(technology, "lifetime"):
        attr = technology.lifetime
        
        # Grab the scalar default value (e.g., 46.0 for hard_coal_plant)
        base_lifetime = getattr(attr, "default_value", None)
        
        if base_lifetime is not None:
            new_lifetime = float(base_lifetime + 10) # Ensure it's a float for JSON compatibility
            
            # EXPLICITLY OVERWRITE THE DEFAULT VALUE
            # By skipping the .set_data() method and dataframe creation, 
            # ZEN-creator will only log this change in attributes.json and skip CSV creation.
            attr.default_value = new_lifetime
            
            print(f"Lifetime extended for {tech_name} from {base_lifetime} to {new_lifetime} in attributes.json")


# ================================================
# 3. Add capacity limits for 2025 (fixed) and 2030 (TYNDP)
# ================================================
technology_list.append("photovoltaics")

for tech_name in technology_list:
    if tech_name not in model.elements:
        continue
        
    technology = model.elements[tech_name]

    # --- 1. Fetch 2025 Existing Capacity ---
    entsoe_attr = entsoe_ds.get_capacity(technology)
    
    spatial_indices = [idx for idx in entsoe_attr.df.index.names if idx in ["location", "node", "edge"]]
    
    df_2025 = entsoe_attr.df.copy().reset_index()
    
    if not df_2025.empty:
        df_2025 = df_2025.groupby(spatial_indices, as_index=False)["capacity_existing"].sum()
    else:
        # Handle case where technology has zero existing capacity everywhere
        df_2025 = pd.DataFrame(columns=spatial_indices + ["capacity_existing"])
        
    df_2025["year"] = 2025
    
    # Set limit EXACTLY to existing capacity
    df_max_2025 = df_2025[spatial_indices + ["year", "capacity_existing"]].rename(columns={"capacity_existing": "capacity_limit"})

    # --- 2. Fetch 2030 TYNDP Capacity ---
    tyndp_attr = tyndp_ds.get_capacity(technology, target_year=2030)
    df_2030 = tyndp_attr.df.copy().reset_index()
    
    if not df_2030.empty:
        if "year" not in df_2030.columns:
            df_2030["year"] = 2030
            
        upper_bound_values = df_2030["capacity_existing"] * 1.3
        upper_bound_values = upper_bound_values.where(df_2030["capacity_existing"] > 0, 0.1) 
        
        df_max_2030 = df_2030[spatial_indices + ["year"]].copy()
        df_max_2030["capacity_limit"] = upper_bound_values
        
        # --- NEW: Ensure all locations have a 2025 limit ---
        # Extract all unique locations from both 2025 and 2030
        locs_2025 = df_max_2025[spatial_indices].drop_duplicates()
        locs_2030 = df_max_2030[spatial_indices].drop_duplicates()
        all_locs = pd.concat([locs_2025, locs_2030]).drop_duplicates()
        
        # Create a full 2025 DataFrame for all known locations
        full_2025 = all_locs.copy()
        full_2025["year"] = 2025
        
        # Merge the known 2025 limits and fill any missing locations with 0.0
        df_max_2025 = pd.merge(full_2025, df_max_2025, on=spatial_indices + ["year"], how="left")
        df_max_2025["capacity_limit"] = df_max_2025["capacity_limit"].fillna(0.0)
        # ---------------------------------------------------
        
        df_max_combined = pd.concat([df_max_2025, df_max_2030], ignore_index=True)
        source_to_use = tyndp_attr.sources[0]
    else:
        df_max_combined = df_max_2025
        source_to_use = entsoe_attr.sources[0]

    # --- 3. Rebuild the Index ---
    index_cols = spatial_indices + ["year"]
    df_max_combined.set_index(index_cols, inplace=True)

    # --- 4. Set the Data in ZEN-creator ---
    if hasattr(technology, "capacity_limit"):
        technology.capacity_limit.set_data(
            df=df_max_combined,
            unit="GW",
            source=source_to_use
        )
        print(f"Combined Upper capacity limit set for {tech_name}")

# 4) Validate and write files
model.write() 

# # ================================================
# # 5) Post-write cleanup: Delete unwanted files
# # ================================================
# print("\n--- Cleaning up unwanted files ---")
# files_deleted = 0

# for file_path in model.output_folder.rglob("capacity_limit_yearly_variation.csv"):
#     try:
#         file_path.unlink()  
#         print(f"Deleted: {file_path}")
#         files_deleted += 1
#     except Exception as e:
#         print(f"Could not delete {file_path}: {e}")
        
# if files_deleted == 0:
#     print("No 'capacity_limit_yearly_variation.csv' files were found to delete.")
# else:
#     print(f"Successfully deleted {files_deleted} file(s).")