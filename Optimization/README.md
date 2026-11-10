# Smart Agricultural Water Management - Kafr El Sheikh
## Optimization Module

**Author:** Sagda Samy  

---

## Project Overview
This module optimizes agricultural water allocation for rice cultivation in Kafr El Sheikh using a Linear Programming (LP) model governed by Proportional Fairness.

---

## Repository Structure
- `data/`: Contains raw snapshots, audit reports, cleaning stages, and optimization inputs.
- `notebooks/`: Includes the 5 structured Jupyter notebooks (from problem formulation to evaluation).
- `src/`: Python source files (`optimization_model.py`, `data_preprocessing.py`, `unit_conversion.py`, `constraints.py`, `objective_function.py`, etc.).
- `results/`: Contains pilot runs, analysis reports, and the 70 batch experiments.

---

## Mathematical Formulation
- **Decision Variables:** Satisfaction ratio ($t$) and allocated water per field ($x_i$).
- **Objective Function:** Maximize the minimum satisfaction ratio ($\max t$) to ensure fair distribution.
- **Constraints:** Total allocated water must respect the available water budget ($B$) and demand bounds.
