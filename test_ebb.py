from pathlib import Path
from turtle import pd
from zen_creator.model import Model
from zen_creator.datasets.datasets.entsoe_powerplants import EntsoePPDataset   # ← dein neues Dataset

# 1) Load existing model
model = Model.from_existing(Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden/europe_but_better_cleaned")) 

# 2) Modify model
model.output_folder = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden")
model.name = "Ebb_joel_with_pp_new"

# 3) Load new dataset
entsoe_ds = EntsoePPDataset(source_path=Path("C:/Users/joell/Documents/ETH/Master/master_thesis/datasets"))

# 4) Change parameters
# 1. For all technologies: set capacity_addition_max to 0 for 2025 
# (to prevent new additions in 2025, as the new dataset already includes all plants that are active in 2025)
for tech_name, technology in model.elements.items():
    if not hasattr(technology, "capacity_addition_max"):
        continue

    attr = technology.capacity_addition_max

    # Only modify if it's an Attribute with a DataFrame (i.e., not a simple scalar)
    if hasattr(attr, 'data') and isinstance(attr.data, pd.DataFrame):
        df_add = attr.data.copy()

        # Only for 2025: set capacity_addition_max to 0
        if "year" in df_add.columns:
            df_add.loc[df_add["year"] == 2025, "value"] = 0
        elif 2025 in df_add.index:
            df_add.loc[2025, "value"] = 0

        attr.set_data(df=df_add, source="custom")

# ================================================
# 2. Only for technologies in technology_list: set capacity_existing based on new dataset
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
        source=temp_attr.source
    )

    print(f"✅ capacity_updated for {tech_name} (rows: {len(temp_attr.df)})")

# # 3) Rebuild to apply subclass-specific _set_ logic, use only later
# model.build()

# 4) Validate and write files
model.write()   # validiert + schreibt alles auf Festplatte
print("Model saved - only 2025 includes capacity_addition_max = 0")