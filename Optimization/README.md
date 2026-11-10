# AgriWater Optimization

## Project
Smart Agricultural Water Management System - Kafr El Sheikh

## Current Status & Completed Milestones
- Cleaning Stage 1: completed and verified.
- Data audit: completed.
- SQLite readiness audit: completed (Git LFS recovery & schema audits done).
- LP mathematical formulation: completed (Proportional Fairness LP model).
- LP implementation & Batch Experiments: completed (70 experiments: 7 years x 2 scenarios x 5 budget ratios).

## Directory Structure
- data/input/raw_snapshots/
- data/processed/cleaning_stage1/
- data/processed/optimization_input/
- results/pilot/
- results/batch_70_experiments/

## Important Data Limitations
- Water scenario values are modeled estimates, not measured irrigation.
- Daily ETc is not the complete irrigation requirement.
- Soil AWC values are provisional and not field validated.
- Individual field areas and actual irrigation records were not established.
- Pump assignments and operating capacities were not established.

## Optimization & Results Summary
- Formulated a transparent proportional-fairness linear programming model.
- Executed 70 batch experiments covering 2017-2023 with LOW/HIGH scenarios and water budgets from 60% to 100%.
- All 70 experiments solved successfully to Optimal status with verified constraint adherence.
