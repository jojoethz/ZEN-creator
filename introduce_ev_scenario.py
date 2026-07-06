from pathlib import Path
import pandas as pd
from zen_creator.model import Model
from zen_creator import SourceInformation, MetaData

def country_to_iso2(country_name):
    """
    Converts a standard European country name to its ISO 3166-1 alpha-2 code.
    """
    if not isinstance(country_name, str):
        return country_name

    iso2_mapping = {
        "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG",
        "Croatia": "HR", "Cyprus": "CY", "Czechia": "CZ", "Czech Republic": "CZ",
        "Denmark": "DK", "Estonia": "EE", "Finland": "FI",
        "France": "FR", "Germany": "DE", "Greece": "EL",
        "Hungary": "HU", "Ireland": "IE", "Italy": "IT",
        "Latvia": "LV", "Liechtenstein": "LI", "Lithuania": "LT", "Luxembourg": "LU",
        "Malta": "MT", "Netherlands": "NL", "Poland": "PL",
        "Portugal": "PT", "Romania": "RO", "Slovakia": "SK",
        "Slovenia": "SI", "Spain": "ES", "Sweden": "SE",
        "United Kingdom": "UK", "Great Britain": "UK",
        "Norway": "NO", "Switzerland": "CH", "Iceland": "IS",
        "Serbia": "RS", "Bosnia and Herzegovina": "BA", "Montenegro": "ME",
        "North Macedonia": "MK", "Albania": "AL", "Kosovo": "XK"
    }
    
    return iso2_mapping.get(country_name.strip(), country_name.strip())

# ================================================
# 1) Setup Paths & Configuration
# ================================================
base_model_path = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden/Europe_calibrated")
output_base_folder = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden")

# Directory where your 6 scenarios were saved
scenarios_dir = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ev-grid-impacts-eu/Outputs/scenarios")

electric_carriers = ["bev_electricity", "phev_electricity"]

thesis_metadata = MetaData(
    name="thesis_modifications", author=["Joel"], publication_year=2026,
    title="Manual modifications for Master Thesis", publication="ETH Zurich", url=""
)
thesis_source = SourceInformation(description="Manual modifications for Master Thesis", metadata=thesis_metadata)

carrier_to_powertrains = {
    "bev_electricity": ["BEV"],
    "phev_electricity": ["G-PHEV electric part"],
    "cng_natural_gas": ["CNG"],
    "diesel_ICE_diesel": ["Diesel", "D-HEV"],
    "gasoline_ICE_gasoline": ["Gasoline"],
    "fcev_hydrogen": ["FCEV"],
    "phev_gasoline": ["G-PHEV gasoline part"],
    "ghev_gasoline": ["G-HEV"],
    "lpg_lpg": ["LPG"]
}

# ================================================
# 2) Loop Through All Scenarios
# ================================================
# Find all the yearly total files to identify the scenario names dynamically
scenario_files = list(scenarios_dir.glob("*_yearly_total.csv"))

if not scenario_files:
    print(f"No scenario files found in {scenarios_dir}. Check your paths!")

for annual_totals_path in scenario_files:
    # Extract the scenario name (e.g., "all_100_except_Poland_90")
    scenario_name = annual_totals_path.name.replace("_yearly_total.csv", "")
    
    # Construct the corresponding hourly profile path
    hourly_profile_path = scenarios_dir / f"{scenario_name}_hourly_profiles.csv"
    
    print(f"\n{'='*60}\nPROCESSING SCENARIO: {scenario_name}\n{'='*60}")
    
    # Load a fresh copy of the base model for each scenario
    model = Model.from_existing(base_model_path) 
    model.output_folder = output_base_folder
    model.name = f"Europe_calibrated_{scenario_name}"

    # Load datasets (Updated to read standard comma-separated format)
    df_ev_hourly = pd.read_csv(hourly_profile_path, low_memory=False)
    df_annual_totals = pd.read_csv(annual_totals_path)

    # ================================================
    # 3) Change parameters for current scenario
    # ================================================
    for carrier_name, powertrains in carrier_to_powertrains.items():
        if carrier_name not in model.elements:
            continue
            
        carrier = model.elements[carrier_name]
        
        # BRANCH 1: ELECTRIC VEHICLES (Update Hourly Profiles)
        if carrier_name in electric_carriers:
            df_filtered = df_ev_hourly[df_ev_hourly["powertrain"].isin(powertrains)].copy()
            
            if not df_filtered.empty:
                df_filtered.rename(columns={"geo country": "location", "charging_demand_GWh": "demand"}, inplace=True) 
                df_filtered["location"] = df_filtered["location"].apply(country_to_iso2)

                df_grouped = df_filtered.groupby(["time", "location"])["demand"].sum().reset_index()

                df_wide = df_grouped.pivot_table(index="time", columns="location", values="demand")
                df_wide.columns.name = None
                
                carrier.demand.set_data(df=df_wide, unit="GW", source=thesis_source)
                print(f"Hourly DEMAND profile updated for: {carrier_name}")

        # BRANCH 2: FOSSIL FUELS & HYDROGEN
        else:
            df_filtered = df_annual_totals[df_annual_totals["powertrain"].isin(powertrains)].copy()
            
            if not df_filtered.empty:
                df_filtered["location"] = df_filtered["geo country"].apply(country_to_iso2)

                df_grouped = df_filtered.groupby(["year", "location"])["total_energy_demand"].sum().reset_index()
                df_grouped["total_energy_demand"] = df_grouped["total_energy_demand"] / 8760

                df_wide = df_grouped.pivot_table(index="year", columns="location", values="total_energy_demand")
                df_wide.columns.name = None 
                
                ref_year = 2021 if 2021 in df_wide.index else df_wide.index[0]
                base_demand_series = df_wide.loc[ref_year]
                
                df_base_demand = pd.DataFrame({
                    "node": base_demand_series.index,
                    "total_energy_demand": base_demand_series.values
                }).set_index("node")
                
                df_variation = df_wide.div(base_demand_series)
                df_variation = df_variation.fillna(0) 
                
                carrier.demand.set_data(df=df_base_demand, unit="GW", source=thesis_source)
                carrier.demand.yearly_variations_df = df_variation
                
                print(f" Baseline DEMAND updated for: {carrier_name} (Ref Year: {ref_year})")

    # ================================================
    # 4) Validate and write files for current scenario
    # ================================================
    print(f"\n--- Writing the Model: {model.name} ---")
    model.write()

    # POST-PROCESSING: Generate yearly demand files
    print("\n--- Running Post-Processing for Electric Carriers ---")
    output_path = model.output_folder / model.name

    for carrier_name in electric_carriers:
        carrier_dirs = list(output_path.glob(f"**/carriers/{carrier_name}")) or list(output_path.glob(f"**/{carrier_name}"))
        
        for carrier_dir in carrier_dirs:
            demand_file = carrier_dir / "demand.csv"
            if demand_file.exists():
                
                df_written = pd.read_csv(demand_file)
                time_col = df_written.columns[0]
                df_written['_year_tmp'] = pd.to_datetime(df_written[time_col]).dt.year
                
                start_year = df_written['_year_tmp'].min()
                
                for year, df_year in df_written.groupby('_year_tmp'):
                    df_year_out = df_year.drop(columns=['_year_tmp']).copy()
                    df_year_out[time_col] = range(len(df_year_out))
                    df_year_out.rename(columns={time_col: 'time'}, inplace=True)
                    
                    year_file = carrier_dir / f"demand_{year}.csv"
                    df_year_out.to_csv(year_file, index=False)
                    
                    if year == start_year:
                        df_year_out.to_csv(demand_file, index=False)
                print(f"Split profiles and overwrote demand.csv for {carrier_name}")

print("\n ALL SCENARIOS PROCESSED SUCCESSFULLY!")