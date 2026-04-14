import numbers
from pathlib import Path

import pandas as pd

from zen_creator.datasets.datsets.dataset import Dataset
from zen_creator.elements.element import Element
from zen_creator.utils.attribute import Attribute


class TYNDP2024Dataset(Dataset[pd.DataFrame]):
    """
    Dataset for TYNDP 2024.
    
    """
    name = "TYNDP2024"

    def __init__(self, source_path: Path | str | None = None):
        super().__init__(source_path=source_path)

    def _set_author(self) -> str:
        """
        Return the author(s) of the dataset.

        This method is used to set the self.author property when the
        dataset is constructed.
        """
        return "ENTSO-E and ENTSO-G"

    def _set_publication_year(self) -> int:
        """
        Return the publication year of the dataset.

        This method is used to set the self.publication_year property when the
        dataset is constructed.
        """
        return 2025

    def _set_title(self) -> str:
        """
        Return the title of the dataset.

        This method is used to set the self.title property when the
        dataset is constructed.
        """
        return "TYNDP 2024: Europe's electricity infrastructure plan."

    def _set_publication(self) -> str:
        """
        Return the publication where the dataset was published.

        This method is used to set the self.publication property when the
        dataset is constructed.
        """
        return "-"

    def _set_url(self) -> str:
        """
        Return the url from which the dataset was downloaded.

        This method is used to set the self.url property when the dataset is
        constructed.
        """
        return "https://2024.entsos-tyndp-scenarios.eu/download/"

    def _set_path(self) -> Path | None:
        """
        Return the path to the dataset file.

        This method is used to set the self.path property when the dataset is
        constructed.
        """
        return self.source_path/"TYNDP24_gens.xlsx"

    def _set_data(self) -> pd.DataFrame:
        """
        Load the dataset from self.path.

        This should be implemented to load the dataset from self.path and return
        it as a pandas DataFrame or a dictonary of pandas DataFrames. The exact
        implementation will depend on the format of the dataset (e.g., CSV, Excel,
        etc.) and the structure of the data. Any preprocessing steps (e.g.,
        handling missing values, renaming columns, etc.) should also be
        included in this method.

        The method is used to set the self.data property when the dataset is
        constructed. It therefore cannot take any inpyut arguments, but can
        access self.path and any other properties of the dataset.

        'TODO': This method must be implemented.
        """
        # can access self.path to load the dataset,
        # but here we will just return a dummy dataset for demonstration purposes
        data = pd.read_excel(self.path(), sheet_name="Capacity_dispatch")
        data.columns = data.columns.str.strip()

        tyndp = data[
            (data["Scenario"] == "National Trends") &
            (data["Year"] == target_year) &
            (data["Climate Year"] == "CY 2009")
        ].copy()

        tyndp["Country"] = tyndp["Node"].str[:2].replace({"GR": "EL"})
        tyndp = tyndp[tyndp["Country"].isin(zen_countries)].copy()

        tyndp_fuel_map = {
            "biomass_plant": "biomass_plant",
            "hard_coal_plant": "hard_coal_plant",
            "lignite_coal_plant": "lignite_coal_plant",
            "natural_gas_turbine": "natural_gas_turbine",
            "nuclear": "nuclear",
            "oil_plant": "oil_plant",
            "photovoltaics": "photovoltaics",
            "reservoir_hydro": "reservoir_hydro",
            "run-of-river_hydro": "run-of-river_hydro",
            "waste_plant": "waste_plant",
            "wind_offshore": "wind_offshore",
            "wind_onshore": "wind_onshore",
            "pumped_hydro": "pumped_hydro",
        }
        tyndp["Fuel"] = tyndp["Fuel"].map(lambda x: tyndp_fuel_map.get(x, x))
        #tyndp = tyndp[tyndp["Fuel"].isin(zen_fuels)].copy()

        # --- TYNDP KAPAZITÄT ---
        tyndp_capacity = tyndp[tyndp["Parameter"] == "Capacity (MW)"].copy()
        tyndp_country_cap = (
            tyndp_capacity.groupby(["Country", "Fuel"])["Value"]
            .sum()
            .reset_index()
            .rename(columns={"Value": "Value_TYNDP_cap"})
        )
        tyndp_country_cap["Value_TYNDP_cap"] = tyndp_country_cap["Value_TYNDP_cap"] / 1000

        return data

    # -------- methods ------------------------

    def get_max_load(self, element: Element, **kwargs) -> Attribute:
        """
        Function for creating max_load attribute.

        Functions for other attributes should follow the same naming
        convention i.e. get_<attribute_name>.

        This function uses information from self.data and returns an object
        of class Attribute. Any internal functions which are called by this
        function should begin with an underscore to clearly mark them as
        internal.

        Additional keyword arguments can be added to the function signature if needed.
        These can be helpful if, for example, the dataset has multiple configurations
        and/or settings which control the result. In this case, the relevant settings
        can be passed as keyword arguments to the function.
        """
        default_value = self.data.at[element.name, "max_load"]
        if not isinstance(default_value, numbers.Real):
            raise ValueError(
                "Expected numeric value for max_load, got type "
                f"{type(default_value).__name__}"
            )
        attr = Attribute("max_load", element)
        attr.set_data(
            default_value=float(default_value),
            unit=self._max_load_unit(),
            source=self.metadata,
        )
        return attr

    def _max_load_unit(self):
        """
        Helper function for creating the 'max_load' attribute.

        All helper functions should begin with an underscore to clearly mark them as
        internal.
        """
        return "MW"
