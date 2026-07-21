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
# 1) Load existing model & Set up output
# ================================================
base_model_path = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden/Europe_calibrated_carbon_budget")
model = Model.from_existing(base_model_path) 

model.output_folder = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ZEN-garden")
model.name = "Europe_calibrated_with_Updated_EVs_carbon_budget"

# ================================================
# 2) Load datasets (Input files use ; and ,)
# ================================================
hourly_profile_path = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ev-grid-impacts-eu/Outputs/charging demand by country/EV_charging_profile_hourly_detailed.csv")
annual_totals_path = Path("C:/Users/joell/Documents/ETH/Master/master_thesis/ev-grid-impacts-eu/Outputs/charging demand by country/yearly_total_energy_demand_by_country.csv")

electric_carriers = ["bev_electricity", "phev_electricity"]

df_ev_hourly = pd.read_csv(hourly_profile_path, delimiter=";", decimal=",", low_memory=False)
df_annual_totals = pd.read_csv(annual_totals_path, delimiter=";", decimal=",")

thesis_metadata = MetaData(
    name="thesis_modifications", author=["Joel"], publication_year=2026,
    title="Manual modifications for Master Thesis", publication="ETH Zurich", url=""
)
thesis_source = SourceInformation(description="Manual modifications for Master Thesis", metadata=thesis_metadata)

# ================================================
# 3) Group Powertrains by Carrier (Prevents Overwriting)
# ================================================
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
# 4) Change parameters
# ================================================
for carrier_name, powertrains in carrier_to_powertrains.items():
    if carrier_name not in model.elements:
        continue
        
    carrier = model.elements[carrier_name]
    
    # ⚡ BRANCH 1: ELECTRIC VEHICLES (Update Hourly Profiles)
    if carrier_name in electric_carriers:
        df_filtered = df_ev_hourly[df_ev_hourly["powertrain"].isin(powertrains)].copy()
        
        if not df_filtered.empty:
            df_filtered.rename(columns={"geo country": "location", "charging_demand_GWh": "demand"}, inplace=True) 
            df_filtered["location"] = df_filtered["location"].apply(country_to_iso2)

            # Sum up demands if multiple powertrains match this carrier
            df_grouped = df_filtered.groupby(["time", "location"])["demand"].sum().reset_index()

            df_wide = df_grouped.pivot_table(index="time", columns="location", values="demand")
            df_wide.columns.name = None
            
            # Pass full wide format back to zen_creator
            carrier.demand.set_data(df=df_wide, unit="GW", source=thesis_source)
            print(f"✅ Hourly DEMAND profile updated for: {carrier_name} (Combined: {powertrains})")

    # 🛢️ BRANCH 2: FOSSIL FUELS & HYDROGEN (Update Absolute Demand + Yearly Fractions)
    else:
        df_filtered = df_annual_totals[df_annual_totals["powertrain"].isin(powertrains)].copy()
        
        if not df_filtered.empty:
            df_filtered["location"] = df_filtered["geo country"].apply(country_to_iso2)

            # Group by year and location, then SUM their energy demand values together
            df_grouped = df_filtered.groupby(["year", "location"])["total_energy_demand"].sum().reset_index()

            # Fix: Convert GWh to GW by dividing by 8760 hours in a year
            df_grouped["total_energy_demand"] = df_grouped["total_energy_demand"] / 8760

            # 1. Create Wide Format (Rows = Year, Columns = Location/Node)
            df_wide = df_grouped.pivot_table(index="year", columns="location", values="total_energy_demand")
            df_wide.columns.name = None 
            
            # 2. Determine reference year (2021)
            ref_year = 2021 if 2021 in df_wide.index else df_wide.index[0]
            
            # 3. Extract baseline values for the reference year
            base_demand_series = df_wide.loc[ref_year]
            
            # Format baseline values for demand.csv
            df_base_demand = pd.DataFrame({
                "node": base_demand_series.index,
                "total_energy_demand": base_demand_series.values
            }).set_index("node")
            
            # 4. Calculate fractional multipliers
            df_variation = df_wide.div(base_demand_series)
            df_variation = df_variation.fillna(0) 
            
            # 5. Assign both datasets into the ZEN-creator carrier
            carrier.demand.set_data(df=df_base_demand, unit="GW", source=thesis_source)
            carrier.demand.yearly_variations_df = df_variation
            
            print(f"✅ Baseline DEMAND & DEMAND_YEARLY_VARIATION updated for: {carrier_name} (Combined: {powertrains}, Ref Year: {ref_year})")

# ================================================
# 5) Validate and write files
# ================================================
print("\n--- Writing the Model ---")
model.write()

# 🌟 POST-PROCESSING: Generate the necessary yearly demand files (demand_2025.csv, etc.)
print("\n--- Running Post-Processing for Electric Carrier Yearly Profiles ---")
output_path = model.output_folder / model.name

for carrier_name in electric_carriers:
    # Locate the element folders dynamically
    carrier_dirs = list(output_path.glob(f"**/carriers/{carrier_name}")) or list(output_path.glob(f"**/{carrier_name}"))
    
    for carrier_dir in carrier_dirs:
        demand_file = carrier_dir / "demand.csv"
        if demand_file.exists():
            print(f"Processing compiled demand file for {carrier_name} at: {demand_file}")
            
            # Read standard comma-separated format outputted by ZEN-creator
            df_written = pd.read_csv(demand_file)
            
            # Track the first column containing the timestamps
            time_col = df_written.columns[0]
            df_written['_year_tmp'] = pd.to_datetime(df_written[time_col]).dt.year
            
            # Automatically detect the starting year
            start_year = df_written['_year_tmp'].min()
            
            # Group by parsed year and split out separate profiles
            for year, df_year in df_written.groupby('_year_tmp'):
                df_year_out = df_year.drop(columns=['_year_tmp']).copy()
                
                # Replace datetime strings with continuous natural numbers (0, 1, 2...)
                df_year_out[time_col] = range(len(df_year_out))
                
                # Rename column header from the dynamic timestamp column name to exactly 'time'
                df_year_out.rename(columns={time_col: 'time'}, inplace=True)
                
                # Write the yearly file (e.g., demand_2030.csv)
                year_file = carrier_dir / f"demand_{year}.csv"
                df_year_out.to_csv(year_file, index=False)
                print(f"   Successfully generated: {year_file.name}")
                
                # If this is the start year, overwrite the main demand.csv!
                if year == start_year:
                    df_year_out.to_csv(demand_file, index=False)
                    print(f"   ✅ Overwrote massive demand.csv with ONLY the start year ({start_year})")