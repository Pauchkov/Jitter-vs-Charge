# `jitter.py`

## Purpose
`jitter.py` computes TOA jitter from charge-scan timing CSV files and generates:
- a per-pixel TOA statistics table,
- a per-charge/per-ASIC jitter summary,
- a jitter-vs-charge plot.

It can optionally scale TOA by LSB values from a matching `delayScan/DB_results.csv`.

## Requirements
- Python 3.8+
- `numpy`
- `matplotlib`

Install dependencies if needed:

```bash
pip install numpy matplotlib
```

## Input Data

### Mandatory timing files
The script searches under `--input-folder` for files named:

`timing_data_dacCharge_<DAC>.csv`

Search order:
1. `--input-folder/*/timing_data_dacCharge_*.csv`
2. recursive fallback: `--input-folder/**/timing_data_dacCharge_*.csv`

Required columns in each timing CSV:
- `pixel`
- `asic`
- `toa`
- `crc`

Rows are ignored when:
- `pixel` is outside `[0, 224]`
- `crc != 0`
- `toa == 127` (invalid TOA code)

### Optional delayScan LSB calibration
If available, the script tries to find one `DB_results.csv` in delay scan results.
Expected columns:
- `asic`
- `pixel`
- `lsb`

If exactly one file is found, TOA is scaled as:

`toa_scaled = toa * lsb`

with LSB lookup key based on parity:

`asic_lsb = asic % 2`

If no valid delayScan file is found (or multiple are found), the script falls back to raw TOA values.

## Usage

```bash
python jitter.py \
  --input-folder <charge_scan_results_folder> \
  --output-dir <output_folder> \
  [--output-prefix <prefix>] \
  [--min-plot-charge <dac_charge_min>]
```

### Arguments
- `--input-folder` (required): folder analyzed by `run_analysis.py`.
- `--output-dir` (required): output folder for generated files.
- `--output-prefix` (optional, default `""`): prefix added to all output filenames.
- `--min-plot-charge` (optional, default `13`): minimum DAC charge shown on the plot. If no charges satisfy this threshold, all charges are plotted.

## Outputs
Files are created in `--output-dir`:

1. `<prefix>toa_output.csv`
- Columns: `charge,pixel,asic,count,mean_toa,std_toa`
- Contains one row for every `(charge, pixel, asic)` combination.

2. `<prefix>jitter_output.csv`
- Columns: `charge,asic,mean_jitter_std_toa,pixels_used`
- For each `(charge, asic)`, it averages pixel-level TOA standard deviations.
- A pixel contributes only if it has at least 2 samples.

3. `<prefix>jitter_vs_charge.pdf`
- X-axis label: `Charge [fC]`
- Y-axis label:
  - `Jitter (TOA std) [ps]` when LSB scaling is applied
  - `Jitter (TOA std)` otherwise
- Charge conversion used for plotting:

`charge_fC = dac_charge * 0.4 + 1`

## Notes
- Number of pixels is fixed to `225`.
- Minimum samples per pixel for jitter contribution is fixed to `2`.
- The script prints `[DEBUG]` messages for LSB file discovery/loading and `[INFO]` messages for saved outputs.

