from pathlib import Path
from zen_creator.model import Model

existing_model_path = Path("./path/to/existing_model")
model = Model.from_existing(existing_model_path=existing_model_path)