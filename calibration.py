from pathlib import Path
import pandas as pd
import numpy as np
from zen_creator import Model, MetaData, SourceInformation
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

thesis_source = SourceInformation(description="Manual modifications for Master Thesis", metadata=thesis_metadata)

# 4) Change parameters
# ================================================
# 4.1 Only for technologies in technology_list: set capacity_existing based on new dataset
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
# 4.2 lifetime has to be extended by +10 years for all fossil technologies 
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
# 4.3 Add capacity limits for 2025 (fixed to 0) and 2030 (TYNDP)
# ================================================
technology_list.append("photovoltaics")  
technology_list.append("fuel_cell")

# --- PREPARE MASTER LOCATIONS ---
# Extract the true master list of all nodes, explicitly ignoring transmission lines (edges).
master_nodes = set()
for name, element in model.elements.items():
    if hasattr(element, "capacity_existing") and element.capacity_existing.df is not None:
        df_idx = element.capacity_existing.df.index.names
        
        # STRICT FILTER: Only grab from elements that have 'node' or 'location', 
        # and explicitly exclude anything that has 'edge' in its index.
        if "edge" not in df_idx:
            if "node" in df_idx:
                master_nodes.update(element.capacity_existing.df.index.get_level_values("node").unique())
            elif "location" in df_idx:
                master_nodes.update(element.capacity_existing.df.index.get_level_values("location").unique())

master_nodes_list = list(master_nodes)
print(f"\n--- Detected {len(master_nodes_list)} pure countries/nodes. Applying 2025 zero-limits to ALL of them. ---")

for tech_name in technology_list:
    if tech_name not in model.elements:
        continue
        
    technology = model.elements[tech_name]
    source_to_use = thesis_metadata

    # Determine the correct spatial index name for this specific technology ('node' or 'location')
    spatial_index = "node" 
    if hasattr(technology, "capacity_existing") and technology.capacity_existing.df is not None:
        for col in ["node", "location"]:
            if col in technology.capacity_existing.df.index.names:
                spatial_index = col
                break

    # --- 1. Build 2025 Capacity Limits (All Zeros for ALL Countries) ---
    df_max_2025 = pd.DataFrame({spatial_index: master_nodes_list})
    df_max_2025["year"] = 2025
    df_max_2025["capacity_limit"] = 0.0  
    
    df_min_2025 = pd.DataFrame({spatial_index: master_nodes_list})
    df_min_2025["year"] = 2025
    df_min_2025["capacity_lower_limit"] = 0.0 

    # --- 2. Fetch 2030 Data (TYNDP) Safely ---
    df_max_2030 = pd.DataFrame()
    df_min_2030 = pd.DataFrame()
    
    try:
        tyndp_attr = tyndp_ds.get_capacity(technology, target_year=2030)
        df_2030_base = tyndp_attr.df.copy().reset_index()
        source_to_use = tyndp_attr.sources[0]
        
        if not df_2030_base.empty:
            if "year" not in df_2030_base.columns:
                df_2030_base["year"] = 2030
                
            # Upper Bounds (TYNDP * 1.3)
            upper_bound_values = df_2030_base["capacity_existing"] * 1.3
            upper_bound_values = upper_bound_values.where(df_2030_base["capacity_existing"] > 0, 0.1) 
            df_max_2030 = df_2030_base[[spatial_index, "year"]].copy()
            df_max_2030["capacity_limit"] = upper_bound_values

            # Lower Bounds (70% of TYNDP)
            lower_bound_values = df_2030_base["capacity_existing"] * 0.7
            df_min_2030 = df_2030_base[[spatial_index, "year"]].copy()
            df_min_2030["capacity_lower_limit"] = lower_bound_values
            
    except ValueError as e:
        if "Invalid index names" not in str(e): raise e

    # --- 3. Combine and Apply ---
    df_max_combined = pd.concat([df_max_2025, df_max_2030], ignore_index=True)
    df_min_combined = pd.concat([df_min_2025, df_min_2030], ignore_index=True)

    if not df_max_combined.empty:
        index_cols = [spatial_index, "year"]
        df_max_combined.set_index(index_cols, inplace=True)
        df_min_combined.set_index(index_cols, inplace=True)

        if hasattr(technology, "capacity_limit"):
            technology.capacity_limit.set_data(
                df=df_max_combined,
                unit="GW",
                source=source_to_use
            )
            print(f"Combined Upper capacity limit set for {tech_name}")
            
        if hasattr(technology, "capacity_lower_limit"):
            technology.capacity_lower_limit.set_data(
                df=df_min_combined,
                unit="GW",
                source=source_to_use
            )
            print(f"Combined Lower capacity limit set for {tech_name}")


# ================================================
# 4.4 Fix Units for Non-Energy Technologies (like Steel/Chemicals)
# ================================================
for tech_name, element in model.elements.items():
    # Sync Power / Base Units
    if hasattr(element, "capacity_lower_limit") and hasattr(element, "capacity_limit"):
        element.capacity_lower_limit.unit = element.capacity_limit.unit
        
    # Sync Energy Units for Storage
    if hasattr(element, "capacity_lower_limit_energy") and hasattr(element, "capacity_limit_energy"):
        element.capacity_lower_limit_energy.unit = element.capacity_limit_energy.unit

# ================================================
# 4.5 Set realistic CAPEX for all vehicle technologies
# ================================================
realistic_capex = {
    "gasoline_ICE": 275000.0,
    "Diesel": 290000.0,
    "CNG": 310000.0,
    "LPG": 285000.0,
    "GHEV": 320000.0,
    "BEV": 350000.0,
    "FCEV": 600000.0,
    "PHEV gasoline part": 280000.0,
    "PHEV electric part": 120000.0
}

for tech_name, capex_val in realistic_capex.items():
    if tech_name in model.elements:
        technology = model.elements[tech_name]
        
        if hasattr(technology, "capex_specific_conversion"):
            attr = technology.capex_specific_conversion
            
            # Explicitly overwrite the default value for attributes.json
            attr.default_value = capex_val
            print(f"Updated CAPEX for {tech_name} to {capex_val} Euro/MW")

# ================================================
# 4.6 Clear Carbon Emission Trajectory
# ================================================
for element_name, element in model.elements.items():
    if hasattr(element, "carbon_emissions_annual_limit"):
        print(f"\n--- Clearing Carbon Limit Trajectory for: '{element_name}' ---")
        
        # Empty the internal DataFrame so ZEN-creator doesn't export the old trajectory
        element.carbon_emissions_annual_limit.df = pd.DataFrame()
        print("-> Trajectory DataFrame cleared. Model will look to the default 'inf' value.")

# ================================================
# 4.7 Inject Year-Dependent Carbon Price from Shadow Prices
# ================================================
carbon_price_file = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/calculated_carbon_prices.csv")
parameter_name = "price_carbon_emissions" 

if carbon_price_file.exists():
    print("\n--- Injecting Dynamic Carbon Price for the Energy System ---")
    
    # Load the prices we calculated in the other script
    df_carbon = pd.read_csv(carbon_price_file)
    
    # Ensure the dataframe has 'year' as the index for ZEN-creator's time-series ingestion
    df_carbon.set_index("year", inplace=True)
    
    # In ZEN-creator, the energy_system is usually a direct attribute of the model
    system_element = model.energy_system
    
    attr = getattr(system_element, parameter_name)
    
    # Apply the time-series DataFrame
    attr.set_data(
        df=df_carbon,
        unit="Euro/tons", # Matched to the unit in your attributes.json
        source=thesis_source 
    )
    print(f"-> Successfully applied dynamic carbon prices: \n{df_carbon}")

# 5) Validate and write files
model.write()

# ================================================
# 6) Post-write modifications & cleanup
# ================================================
print("\n--- Running Post-Write Actions ---")
new_model_path = model.output_folder / model.name
files_deleted = 0

# Combined list of all files you want to purge from the output directory
target_cleanup_files = [
    "capacity_limit_yearly_variation.csv",
    "carbon_emissions_annual_limit.csv",
    "carbon_emissions_annual_limit_yearly_variation.csv"
]

if new_model_path.exists():
    for target_file in target_cleanup_files:
        # rglob searches recursively for the specific filename
        for file_path in new_model_path.rglob(target_file):
            try:
                file_path.unlink()  
                print(f"Deleted: {file_path}")
                files_deleted += 1
            except Exception as e:
                print(f"Could not delete {file_path}: {e}")
                
if files_deleted == 0:
    print(f"No targeted restriction CSV files were found to delete in {model.name}.")
else:
    print(f"Successfully cleaned up {files_deleted} restriction file(s) from the output directory.")