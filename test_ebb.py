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

# 2. For all technologies: set capacity_addition_max to 0 for 2025 
# (to prevent new additions in 2025, as the new dataset already includes all plants that are active in 2025)
model_years = [2025, 2030, 2035,2040, 2045, 2050] 

for tech_name, technology in model.elements.items():
    if not hasattr(technology, "capacity_addition_max"):
        continue

    attr = technology.capacity_addition_max

    # case A: limits already exist → modify existing DataFrame
    if hasattr(attr, 'df') and attr.df is not None and not attr.df.empty:
        df_add = attr.df.copy()
        idx_names = df_add.index.names
        df_reset = df_add.reset_index()

        if "year" in df_reset.columns:
            # Setze value auf 0 für das Jahr 2025
            df_reset.loc[df_reset["year"] == 2025, "value"] = 0

            # Ursprünglichen MultiIndex wiederherstellen
            if idx_names != [None]:  
                df_reset.set_index(idx_names, inplace=True)

        # APPLY TO df_reset IN THIS BRANCH
        attr.set_data(
            df=df_reset, 
            source=SourceInformation(
                description="Max capacity addition forced to 0 for 2025.",
                metadata=thesis_metadata
            )
        )

    # case B: no existing limits → create new DataFrame with 0 for 2025 and np.inf for the rest
    else:
        new_limits = []
        for y in model_years:
            if y == 2025:
                new_limits.append({"year": y, "value": 0.0}) # Verbot für 2025
            else:
                new_limits.append({"year": y, "value": np.inf}) # "Kein Limit" für den Rest
        
        df_new = pd.DataFrame(new_limits)
        
        # ZEN-creator bevorzugt oft, dass die Dimension ('year') im Index liegt
        df_new.set_index("year", inplace=True)
        
        # APPLY TO df_new IN THIS BRANCH
        attr.set_data(
            df=df_new, 
            source=SourceInformation(
                description="Max capacity addition forced to 0 for 2025.",
                metadata=thesis_metadata
            )
        )

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
            new_lifetime = base_lifetime + 10
            
            # Create a DataFrame and explicitly set the index to 'technology'
            df_life = pd.DataFrame({
                "technology": [tech_name], 
                "value": [new_lifetime]
            })
            df_life.set_index("technology", inplace=True)
            
            # Try to keep the original unit if it exists, otherwise default to "1"
            current_unit = getattr(attr, "unit", "1")
            
            # Inject the new DataFrame and your thesis metadata
            attr.set_data(
                df=df_life, 
                unit=current_unit,
                source=SourceInformation(
                    description=f"Lifetime extended by 10 years (from {base_lifetime} to {new_lifetime}) to prevent early retirements in 2025.",
                    metadata=thesis_metadata
                )
            )
            print(f"Lifetime extended for {tech_name}: {base_lifetime} -> {new_lifetime}")
        else:
            print(f"Could not find a default_value for {tech_name}'s lifetime.")

# # 3) Rebuild to apply subclass-specific _set_ logic, use only later
# model.build()

# 4) Validate and write files
model.write() 
print("Model saved - only 2025 includes capacity_addition_max = 0")