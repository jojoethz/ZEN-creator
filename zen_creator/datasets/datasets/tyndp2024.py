import numbers
from pathlib import Path

import pandas as pd

from zen_creator.datasets.datasets.dataset import Dataset
from zen_creator.elements.element import Element
from zen_creator.utils.attribute import Attribute
from zen_creator.datasets.datasets.metadata import MetaData
from zen_creator.datasets.datasets.metadata import SourceInformation


class TYNDP2024Dataset(Dataset[pd.DataFrame]):
    """
    Dataset for TYNDP 2024.
    Liefert Kapazitätsdaten für verschiedene Jahre und Szenarien (NT, DE, GA).
    """
    name = "TYNDP2024"

    def __init__(self, source_path: Path | str | None = None):
        super().__init__(source_path=source_path)

    def _set_metadata(self) -> MetaData:
        return MetaData(
            name=self.name,
            author=["ENTSO-E", "ENTSO-G"],
            publication_year=2025,
            title="TYNDP 2024: Europe's electricity infrastructure plan.",
            publication="-",
            url="https://2024.entsos-tyndp-scenarios.eu/download/"
        )

    def _set_path(self) -> Path | None:
        # Den Dateinamen entsprechend dem hochgeladenen CSV anpassen
        return Path(self.source_path) / "TYNDP24_gens.xlsx"

    def _set_data(self) -> pd.DataFrame:
        """Load and preprocess the TYNDP 2024 CSV dataset."""
        data = pd.read_excel(self.path)
        data.columns = data.columns.str.strip()

        # Ländernamen bereinigen
        data["Country"] = data["Country"].replace({"GR": "EL", "GB": "UK"})

        # MAP correctly fuel types to technology names
        tyndp_fuel_map = {
            "Battery-TSO": "battery",
            "Biomass": "biomass_plant",
            "Coal": "hard_coal_plant",
            "Lignite": "lignite_coal_plant",
            "GasCC": "natural_gas_turbine",
            "GasCC-Syn": "natural_gas_turbine",
            "GasSC": "natural_gas_turbine",
            "Nuclear": "nuclear",
            "Oil": "oil_plant",
            "PV-roof": "photovoltaics",
            "Dam": "reservoir_hydro",  
            "RoR": "run-of-river_hydro",
            "Pump-Open": "pumped_hydro",
            "WindOff": "wind_offshore",
            "WindOn": "wind_onshore",
        }
        
        # Wenn kein Mapping gefunden wird, bleibt der ursprüngliche SubType erhalten
        data["Fuel"] = data["SubType"].map(lambda x: tyndp_fuel_map.get(x, x))

        return data

    # ===================================================================
    # Method: get_capacity
    # ===================================================================
    def get_capacity(self, element: Element, scenario: str = "NT", year: int = 2030, climate_year: int = 2009, **kwargs) -> Attribute:
        """
        Returns capacity for a specific scenario and year.
        
        Erwartetes Format in ZEN-creator:
        MultiIndex (node, year) + column 'capacity_existing' in GW.
        
        Keywords:
            scenario (str): "NT" (National Trends), "DE" (Distributed Energy), "GA" (Global Ambition)
            year (int): z.B. 2030, 2040, 2050
            climate_year (int): Klima-Jahr, meistens 1995, 2008 oder 2009.
        """
        tech_name = element.name
        
        # Filter auf Szenario, Jahr, Klima-Jahr und Technologie anwenden
        cond_active = (
            (self.data["Policy"] == scenario) &
            (self.data["start_year"] == year) &
            (self.data["Climate Year"] == climate_year) &
            (self.data["Fuel"] == tech_name)
        )
        df_tech = self.data[cond_active].copy()

        if df_tech.empty:
            df_capacity = pd.DataFrame(columns=["node", "year", "capacity_existing"])
            df_capacity = df_capacity.set_index(["node", "year"])
        else:
            # In TYNDP24_gens.xlsx scheint "P_gen_max in 2015 (MW)" die Kapazitätsspalte zu sein
            df_capacity = df_tech[["Country", "start_year", "P_gen_max in 2015 (MW)"]].rename(columns={
                "Country": "node",
                "start_year": "year",  
                "P_gen_max in 2015 (MW)": "capacity_existing"
            })

            # Umwandeln von MW in GW
            df_capacity["capacity_existing"] = pd.to_numeric(
                df_capacity["capacity_existing"], errors="coerce"
            ).fillna(0) / 1000.0

            # Kapazitäten gleicher Nodes summieren (falls es Duplikate/mehrere Einträge gibt)
            df_capacity = (
                df_capacity.groupby(["node", "year"], as_index=False)["capacity_existing"]
                .sum()
            )
            
            # set multi-index
            df_capacity = df_capacity.set_index(["node", "year"])

        attr = Attribute("capacity", element)
        attr.set_data(
            df=df_capacity,
            unit="GW",
            source=SourceInformation(
                description=f"Capacities extracted from TYNDP2024 for Scenario {scenario}, Year {year}, Climate Year {climate_year}.",
                metadata=self.metadata 
            ),
        )
        return attr