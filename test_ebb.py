from pathlib import Path
import pandas as pd
import numpy as np
from zen_creator.model import Model
from zen_creator.datasets.datasets.metadata import MetaData
from zen_creator.datasets.datasets.metadata import SourceInformation
from zen_creator.datasets.datasets.entsoe_powerplants import EntsoePPDataset 

# 1) Load existing model
model = Model.from_existing(Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden/europe_but_better_cleaned")) 

# 2) Modify model
model.output_folder = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden")
model.name = "Ebb_joel_with_pp_new"

# 3) Load new dataset
entsoe_ds = EntsoePPDataset(source_path=Path("C:/Users/joell/Documents/ETH/Master/master_thesis/datasets"))

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
technology_list = ["biomass_plant", "hard_coal_plant", "lignite_coal_plant", "natural_gas_turbine", "nuclear", "oil_plant", 
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
    
    # WICHTIG: set_data auf dem BESTEHENDEN capacity-Attribut aufrufen
    technology.capacity_existing.set_data(
        df=temp_attr.df,           # der fertig vorbereitete MultiIndex-DataFrame
        unit=temp_attr.unit,
        source=temp_attr.sources[0]
    )

    print(f"capacity_updated for {tech_name} (rows: {len(temp_attr.df)})")

# # ================================================
# # 2. For all technologies: set capacity_addition_max to 0 for 2025 
# # ================================================
# model_years = [2025, 2030, 2035, 2040, 2045, 2050] 
# # These are the ONLY indices ZEN-garden officially recognizes
# allowed_indices = ['carrier', 'edge', 'location', 'node', 'technology', 'time', 'year', 'year_construction']

# for tech_name, technology in model.elements.items():
#     if not hasattr(technology, "capacity_addition_max"):
#         continue

#     attr = technology.capacity_addition_max

#     # case A: limits already exist → STRICTLY filter and clean the DataFrame
#     if hasattr(attr, 'df') and attr.df is not None and not attr.df.empty:
#         df_mod = attr.df.copy()
        
#         # 1. Temporarily flatten to clean up columns easily
#         if df_mod.index.names != [None]:
#             df_mod = df_mod.reset_index()
            
#         # 2. Identify the true value column (usually the last column that isn't an index)
#         non_index_cols = [c for c in df_mod.columns if c not in allowed_indices]
#         val_col = non_index_cols[-1] if non_index_cols else df_mod.columns[-1]
        
#         # 3. NUKE ANY EXTRA COLUMNS: Keep ONLY the official index columns + the single value column
#         valid_cols = [c for c in df_mod.columns if c in allowed_indices]
#         df_mod = df_mod[valid_cols + [val_col]]
        
#         # 4. Rename the data column STRICTLY to the attribute name
#         df_mod.rename(columns={val_col: "capacity_addition_max"}, inplace=True)
        
#         # 5. Apply the zero limit for 2025
#         if "year" in df_mod.columns:
#             df_mod.loc[df_mod["year"] == 2025, "capacity_addition_max"] = 0.0
            
#         # 6. Put the valid indices back!
#         if valid_cols:
#             df_mod.set_index(valid_cols, inplace=True)

#         attr.set_data(
#             df=df_mod, 
#             source=SourceInformation(
#                 description="Max capacity addition forced to 0 for 2025.",
#                 metadata=thesis_metadata
#             )
#         )

#     # case B: no existing limits → create brand new clean DataFrame
#     else:
#         new_limits = []
#         for y in model_years:
#             new_limits.append({
#                 "year": y, 
#                 "capacity_addition_max": 0.0 if y == 2025 else np.inf # <-- Explicitly named here too!
#             })
            
#         df_new = pd.DataFrame(new_limits)
#         df_new.set_index("year", inplace=True)
        
#         attr.set_data(
#             df=df_new, 
#             source=SourceInformation(
#                 description="Max capacity addition forced to 0 for 2025.",
#                 metadata=thesis_metadata
#             )
#         )

# ================================================
# 3. lifetime has to be extended by +10 years for all fossil technologies 
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
            
            # 1. EXPLICITLY OVERWRITE THE DEFAULT VALUE SO IT SAVES CORRECTLY
            attr.default_value = new_lifetime
            
            # 2. Keep the DataFrame so ZEN-creator still logs your thesis metadata!
            df_life = pd.DataFrame({
                "technology": [tech_name], 
                "value": [new_lifetime]
            })
            df_life.set_index("technology", inplace=True)
            
            current_unit = getattr(attr, "unit", "1")
            
            attr.set_data(
                df=df_life, 
                unit=current_unit,
                source=SourceInformation(
                    description=f"Lifetime extended by 10 years (from {base_lifetime} to {new_lifetime}) to prevent early retirements in 2025.",
                    metadata=thesis_metadata
                )
            )

# # 3) Rebuild to apply subclass-specific _set_ logic, use only later
# model.build()

# 4) Validate and write files
model.write() 
print("Model saved - only 2025 includes capacity_addition_max = 0")