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
model.name = "Europe_calibrated"

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

# Nur für den Test:
tech_test = model.elements["biomass_plant"]
temp_attr = entsoe_ds.get_capacity(tech_test)

print("Index-Namen:", temp_attr.df.index.names)
print("Spalten:", temp_attr.df.columns)
print(temp_attr.df.head(2))

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
    
    technology.capacity_existing.set_data(
        df=temp_attr.df,           # der fertig vorbereitete MultiIndex-DataFrame
        unit=temp_attr.unit,
        source=temp_attr.sources[0]
    )

    print(f"capacity_updated for {tech_name} (rows: {len(temp_attr.df)})")


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

# # 3) Rebuild to apply subclass-specific _set_ logic, use only later
# model.build()

# 4) Validate and write files
model.write() 