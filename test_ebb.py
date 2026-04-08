from pathlib import Path
from zen_creator.model import Model
import pandas as pd

# 1) Load existing model
model = Model.from_existing(Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden/europe_but_better_cleaned")) 

# 2) Modify model
model.output_folder = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden")
model.name = "Ebb_joel_with_custom_changes"




# 3) Rebuild to apply subclass-specific _set_ logic
#model.build()

# 4) Validate and write files
model.write()