"""
Objective Function Module for AgriWater Optimization
Defines the mathematical objective function for Proportional Fairness.
Author: Sagda Samy
"""
import pulp

def set_proportional_fairness_objective(model, satisfaction_var):
    """
    Sets the objective function to maximize the minimum satisfaction ratio (t)
    across all agricultural fields to ensure equitable water distribution.
    """
    model.setObjective(satisfaction_var)
    return model
