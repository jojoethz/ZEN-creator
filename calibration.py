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
# 3. Add capacity limits for 2030 based on TYNDP
# ================================================
# We apply this to the same technology list but add PV
technology_list.append("photovoltaics")

for tech_name in technology_list:
    if tech_name not in model.elements:
        continue
        
    technology = model.elements[tech_name]


    # 1. Fetch the capacity from TYNDP dataset for the year 2030
    # Note: Ensure your TYNDP2024Dataset.get_capacity uses 'year' as index name now
    tyndp_attr = tyndp_ds.get_capacity(technology, target_year=2030)
    df_tyndp = tyndp_attr.df.copy()
    
    if df_tyndp.empty:
        continue
        
    # TYNDP data is provided in the 'capacity_existing' column
    cap_existing = df_tyndp["capacity_existing"]
    
    # 2. Calculate the bounds
    # Lower bound: 70% of projected capacity
    lower_bound_values = cap_existing * 0.7
    
    # Upper bound: 130% of projected capacity, or 0.1 GW if projection is 0
    upper_bound_values = cap_existing * 1.3
    upper_bound_values = upper_bound_values.where(cap_existing > 0, 0.1)  # Set to 0.1 GW if projected capacity is 0 to avoid zero upper bound
    
    # 3. Set the Upper Bound (capacity_limit)
    # This will create/update capacity_limit.csv and trigger constraint_technology_max_capacity
    if hasattr(technology, "capacity_limit"):
        df_max = pd.DataFrame({"capacity_limit": upper_bound_values})
        technology.capacity_limit.set_data(
            df=df_max,
            unit="GW",
            source=tyndp_attr.sources[0]
        )
        print(f"Upper capacity limit (130%) set for {tech_name}")


    # 4. Set the Lower Bound (capacity_min_limit)
    # This will create/update capacity_min_limit.csv and trigger constraint_technology_min_capacity
    if hasattr(technology, "capacity_min_limit"):
        df_min = pd.DataFrame({"capacity_min_limit": lower_bound_values})
        technology.capacity_min_limit.set_data(
            df=df_min,
            unit="GW",
            source=tyndp_attr.sources[0]
        )
        print(f"Lower capacity limit (70%) set for {tech_name}")

# # 3) Rebuild to apply subclass-specific _set_ logic, use only later
# model.build()

# 4) Validate and write files
model.write() 