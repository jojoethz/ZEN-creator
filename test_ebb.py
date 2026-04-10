from pathlib import Path
from zen_creator.model import Model
import pandas as pd

# 1) Load existing model
model = Model.from_existing(Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden/europe_but_better_cleaned")) 

# 2) Modify model
model.output_folder = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden")
model.name = "Ebb_joel_with_custom_changes"

technology_list = ["solar", "wind", "pumped_hydro"]
for technology in model.technologies:
    if technology.name in technology_list:
        capacity_addition_min = TYNDP2024(model.source_path).get_capacity_addition_min(technology.name)

        technology.capacity_addition_min.set_data(df=capacity_addition_min)

# # 3) Rebuild to apply subclass-specific _set_ logic, use only later
# model.build()

# 4) Validate and write files
model.write()