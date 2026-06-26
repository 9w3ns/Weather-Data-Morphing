# Weather Data Morphing

A Python-based tool for morphing EnergyPlus Weather (.epw) files to project future climate conditions.

## Project Scope
This tool was developed to support a KMITL architecture thesis investigating a **Public Thermal Transit Hub** in Bangkok. It implements two distinct morphing methodologies:

1. **Normal Shift Method (Belcher 2005)**: The standard shift/stretch approach.
2. **Bounded Temperature Weighted Stretch (BTWS, Eames 2024)**: An advanced algorithm preserving projected daily minimum, maximum, and mean changes while adhering to physical limits.

## Directory Structure
- `morphing/`: Core python scripts for the morphing logic and orchestration.
- `data/`: Contains sample `.epw` files and `.csv` files for monthly climate deltas.
- `docs/`: Documentation on morphing theory, Grasshopper integration, and methodology limitations.
- `research/`: Relevant research papers and literature.
- `thesis/`: Thesis context documents exploring UTCI, CA algorithms, and site specifics.

## Usage
Run the morphing engine by passing a baseline EPW and a monthly delta CSV file:
```python
from morphing.epw_morphing_engine import EPWMorphingEngine

engine = EPWMorphingEngine("data/epw/Bangkok_baseline_2026_TMYx.epw", "data/deltas/bangkok_ssp585_2070.csv")
engine.morph(method="btws")
engine.save("morphed_future.epw")
```
