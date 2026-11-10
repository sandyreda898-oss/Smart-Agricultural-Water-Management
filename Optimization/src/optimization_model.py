"""
AgriWater Optimization Model Module
Implements the Proportional Fairness Linear Programming optimization for Kafr El Sheikh rice irrigation.
Author: Sagda Samy
"""

import pulp
import pandas as pd
import numpy as np

def solve_proportional_fairness_allocation(demand_series, budget):
    """
    Solves water allocation using linear programming with proportional fairness.
    """
    model = pulp.LpProblem("AgriWater_Proportional_Fairness_Allocation", pulp.LpMaximize)
    
    # Decision variable: satisfaction ratio t (0 <= t <= 1)
    t = model.addVariable("satisfaction_ratio", lowBound=0.0, upBound=1.0, cat=pulp.LpContinuous)
    
    # Objective: Maximize minimum satisfaction ratio (t)
    model.setObjective(t)
    
    # Constraint: Total allocated water <= available budget
    allocations = {i: t * demand_series[i] for i in demand_series.index}
    total_allocation = pulp.lpSum(allocations.values())
    model.addConstraint(total_allocation <= budget, "Water_Budget_Constraint")
    
    # Solve using HiGHS
    solver = pulp.HiGHS(msg=False)
    result = model.solve(solver)
    
    status = pulp.LpStatus[model.status]
    if status != 'Optimal':
        return None, None, status
        
    solved_t = pulp.value(t)
    allocated_df = pd.Series({i: solved_t * demand_series[i] for i in demand_series.index})
    
    return allocated_df, solved_t, status
