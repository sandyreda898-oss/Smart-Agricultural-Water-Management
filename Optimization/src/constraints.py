"""
Constraints Module for LP Optimization
Defines budget constraints and proportional fairness bounds.
Author: Sagda Samy
"""
import pulp

def add_budget_constraint(model, allocations, budget):
    total_alloc = pulp.lpSum(allocations.values())
    model.addConstraint(total_alloc <= budget, "Total_Water_Budget_Constraint")
