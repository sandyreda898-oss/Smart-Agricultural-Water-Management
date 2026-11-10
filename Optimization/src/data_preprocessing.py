"""
Data Preprocessing Module for AgriWater Optimization
Handles input data loading, validation, and cleaning integration.
Author: Sagda Samy
"""
import pandas as pd
import numpy as np

def load_and_validate_demand_inputs(filepath):
    df = pd.read_csv(filepath)
    required_cols = ['season_year', 'point_id', 'demand_scenario', 'scenario_demand_m3_per_feddan']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    return df
