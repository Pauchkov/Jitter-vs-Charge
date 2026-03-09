# Jitter-vs-Charge

`jitter.py` computes TOA jitter (`std`) per pixel and then averages it per ASIC as a function of `DAC Charge`.

## What the script does

1. Reads CSV files from `pixelOn_all_pixelInj_row*` folders.
2. For each `charge / pixel / asic`, keeps only events with:
   - `crc == 0`
   - `toa != 127`
3. Computes:
   - `std_toa` per pixel
   - mean jitter (`mean_jitter_std_toa`) per ASIC
4. Plots `Jitter (TOA std) vs Charge`.
5. Writes two result CSV files.

## Requirements

- Python 3.9+
- Packages:
  - `numpy`
  - `matplotlib`

Install:

```bash
pip install numpy matplotlib
```

## Input data layout

The `--dir` argument must point to a directory containing:

```text
<input_dir>/
  pixelOn_all_pixelInj_row0/
    timing_data_dacCharge_0.csv
    ...
    timing_data_dacCharge_63.csv
  ...
  pixelOn_all_pixelInj_row14/
```

Expected CSV columns: `pixel`, `asic`, `toa`, `crc`.

## Run

```bash
python3 jitter.py --dir ../chargeScan/B_None_On_all_Inj_row_N_200_Vth_380_Q_12
```

or from the project root:

```bash
python3 for_git/jitter.py --dir chargeScan/B_None_On_all_Inj_row_N_200_Vth_380_Q_12
```

## Output files

The script writes:

- `/toa_output.csv`
- `/jitter_output.csv`

Important: these are absolute paths (start with `/`).  
If you do not have write permission in filesystem root, change in code:

- `output_path_pixels = "/toa_output.csv"`
- `output_path_jitter = "/jitter_output.csv"`

to relative paths, for example:

- `output_path_pixels = "toa_output.csv"`
- `output_path_jitter = "jitter_output.csv"`

## Main constants in code

- `N_CHARGES = 64`
- `N_PIXELS = 225`
- `N_ASICS = 4`
- `N_INJ_ROWS = 15`
- `INVALID_TOA_CODE = 127`
- `MIN_SAMPLES_PER_PIXEL = 2`
