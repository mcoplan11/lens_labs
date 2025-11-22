# Lens Labs

Healthcare analytics toolkit for Medicare claims, quality metrics, and staffing analysis.

## Overview

This repository contains Python scripts for analyzing CMS (Centers for Medicare & Medicaid Services) data, including:

- **CERT audit analysis** - Payment error detection and leakage analysis
- **E/M coding patterns** - Provider evaluation & management complexity analysis
- **Discharge planning** - Nursing home staffing stability monitoring
- **HCC/risk adjustment** - Diabetes comorbidity mapping

## Key Scripts

### CERT Analysis
- [cert_leakage.py](cert_leakage.py) - Deep-dive on CMS CERT FFS audit data
  - Generates leakage matrices showing disagreement rates by service category
  - Analyzes error patterns (medical necessity, documentation, coding/technical)
  - Outputs: PNG visualizations + CSV summary tables

- [cert_ffs_analysis.py](cert_ffs_analysis.py) - Additional FFS CERT analysis

### E/M Coding Analysis
- [em_coding.py](em_coding.py) - Provider-level E/M complexity analysis
  - Compares E/M service distributions across specialties
  - Identifies provider outliers and overlap patterns
  - State-level and urban/rural (RUCA) breakdowns
  - Outputs: Heatmaps, violin plots, choropleth maps

- [em_coding_2019_to_2023.py](em_coding_2019_to_2023.py) - Longitudinal E/M trends

### Discharge Planning
- [discharge_planning/cms_watch.py](discharge_planning/cms_watch.py) - Nursing home staffing monitor
  - Pulls latest CMS Payroll Based Journal (PBJ) data automatically
  - Tracks HPRD (hours per resident day) trends
  - Monitors weekend staffing ratios and turnover deltas
  - Generates alerts for staffing instability signals

- [discharge_planning/change_of_ownership.py](discharge_planning/change_of_ownership.py)

### Other Analysis
- [hcc_diabetes_map.py](hcc_diabetes_map.py) - HCC risk adjustment for diabetes populations
- [lodestar_figures.py](lodestar_figures.py) - Custom visualizations
- [lodestar_fig2.py](lodestar_fig2.py), [lodestar_output_figs.py](lodestar_output_figs.py) - Figure generation

## Data Sources

Scripts use public CMS datasets including:
- Medicare Physician & Other Supplier PUF
- CERT FFS audit files
- Payroll Based Journal (PBJ) Daily Nurse Staffing
- Provider Information (Care Compare)

## Setup

1. Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
```

2. Install dependencies (common requirements):
```bash
pip install pandas numpy matplotlib seaborn plotly requests python-dateutil
```

## Usage

Most scripts are configured at the top with file paths and parameters. Update the `INPUT_CSV` or `CSV_FILE` paths to point to your local data files.

Example:
```bash
python cert_leakage.py
```

Outputs are typically saved to `outputs/` or `outputs_discharge/` directories.

## Output Directories

- `outputs/` - Main analysis outputs (charts, CSVs)
- `outputs_discharge/` - Discharge planning analysis outputs

## Git Status

Currently modified:
- `discharge_planning/cms_watch.py`

## License

MIT
