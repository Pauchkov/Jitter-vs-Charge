import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

INVALID_TOA_CODE = 127
MIN_SAMPLES_PER_PIXEL = 2
MIN_PLOT_CHARGE = 13
N_PIXELS = 225


def find_timing_files(input_folder):
    root = Path(input_folder).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Input folder does not exist: {root}")

    files = sorted(root.glob("*/timing_data_dacCharge_*.csv"))
    if not files:
        files = sorted(root.rglob("timing_data_dacCharge_*.csv"))
    if not files:
        raise FileNotFoundError(f"No timing_data_dacCharge_*.csv files found under: {root}")
    return files


def charge_from_filename(path):
    match = re.search(r"timing_data_dacCharge_(\d+)\.csv$", path.name)
    if match is None:
        return None
    return int(match.group(1))


def load_lsb_from_delayscan(delayscan_csv_path):
    csv_path = Path(delayscan_csv_path).resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(f"delayScan DB_results.csv not found: {csv_path}")

    print(f"[DEBUG] LSB load: reading {csv_path}")
    lsb_per_asic = defaultdict(lambda: np.full(N_PIXELS, np.nan, dtype=float))
    with csv_path.open(newline="") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=",")
        for row in reader:
            try:
                asic = int(row["asic"])
                pixel = int(row["pixel"])
                lsb = float(row["lsb"])
            except (KeyError, TypeError, ValueError):
                continue

            if 0 <= pixel < N_PIXELS:
                lsb_per_asic[asic][pixel] = lsb

    lsb_dict = dict(lsb_per_asic)
    print(f"[DEBUG] LSB load: loaded ASICs = {len(lsb_dict)}")
    for asic, arr in sorted(lsb_dict.items()):
        valid = int(np.sum(~np.isnan(arr)))
        print(f"[DEBUG] LSB load: ASIC {asic}, valid pixels = {valid}")
    return lsb_dict


def find_delayscan_lsb_csv(results_root):
    root = Path(results_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Results folder does not exist: {root}")

    parts = root.parts
    base_dir = Path(*parts[:parts.index("chargeScan")]) if "chargeScan" in parts else root
    module_folder = next((part for part in parts if re.fullmatch(r"module_\d+", part)), None)
    search_roots = [base_dir / "delayScan", Path.cwd().resolve() / "results" / base_dir.name / "delayScan"]

    print(f"[DEBUG] LSB search: input root = {root}")
    print(f"[DEBUG] LSB search: base before chargeScan = {base_dir}")
    seen = set()
    candidates = []
    for search_root in search_roots:
        print(f"[DEBUG] LSB search: scanning {search_root}")
        if not search_root.exists():
            continue
        found = sorted(search_root.rglob("DB_results.csv"))
        if module_folder is not None:
            filtered = [p for p in found if module_folder in p.parts]
            found = filtered or found
        for path in found:
            if path not in seen:
                seen.add(path)
                candidates.append(path)
    print(f"[DEBUG] LSB search: candidates = {len(candidates)}")

    if not candidates:
        raise FileNotFoundError(f"No delayScan DB_results.csv found under {[str(x) for x in search_roots]}")
    if len(candidates) > 1:
        raise RuntimeError(
            "Multiple delayScan DB_results.csv files found; "
            "narrow the search path or pass an explicit file path"
        )
    print(f"[DEBUG] LSB search: selected {candidates[0]}")
    return candidates[0]


def run_jitter_analysis(input_folder, output_dir, output_prefix="", min_plot_charge=MIN_PLOT_CHARGE):
    timing_files = find_timing_files(input_folder)
    toa_values_dac = defaultdict(list)
    toa_values_scaled = defaultdict(list)
    charges_seen = set()
    asics_seen = set()
    try:
        LSB = load_lsb_from_delayscan(find_delayscan_lsb_csv(input_folder))
    except (FileNotFoundError, RuntimeError):
        LSB = None
        print("[DEBUG] LSB: not loaded, fallback to raw TOA")

    for csv_path in timing_files:
        charge = charge_from_filename(csv_path)
        if charge is None:
            continue
        charges_seen.add(charge)

        with csv_path.open(newline="") as csvfile:
            reader = csv.DictReader(csvfile, delimiter=",")
            for row in reader:
                try:
                    pixel = int(row["pixel"])
                    asic = int(row["asic"])
                    toa = int(row["toa"])
                    crc = int(row["crc"])
                except (KeyError, TypeError, ValueError):
                    continue

                if pixel < 0 or pixel >= N_PIXELS:
                    continue
                if crc != 0 or toa == INVALID_TOA_CODE:
                    continue

                asics_seen.add(asic)
                key = (charge, pixel, asic)
                toa_values_dac[key].append(toa)
                asic_lsb = asic - 2
                if LSB is not None and asic_lsb in LSB:
                    lsb_value = LSB[asic_lsb][pixel]
                    toa_scaled = toa * lsb_value if not np.isnan(lsb_value) else toa
                else:
                    toa_scaled = toa
                toa_values_scaled[key].append(toa_scaled)

    charges = sorted(charges_seen)
    asics = sorted(asics_seen)
    if not charges or not asics:
        raise RuntimeError("No valid TOA samples found for jitter computation")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path_pixels = output_dir / f"{output_prefix}toa_output.csv"
    output_path_jitter = output_dir / f"{output_prefix}jitter_output.csv"
    output_plot = output_dir / f"{output_prefix}jitter_vs_charge.pdf"

    mean_jitter = {}
    pixels_used = {}

    with output_path_pixels.open("w", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow([
            "charge",
            "pixel",
            "asic",
            "count",
            "mean_toa",
            "std_toa",
            "mean_toa_dac",
            "std_toa_dac",
        ])

        for charge in charges:
            for pixel in range(N_PIXELS):
                for asic in asics:
                    values_scaled = toa_values_scaled.get((charge, pixel, asic), [])
                    values_dac = toa_values_dac.get((charge, pixel, asic), [])
                    if values_scaled:
                        writer.writerow([
                            charge,
                            pixel,
                            asic,
                            len(values_scaled),
                            float(np.mean(values_scaled)),
                            float(np.std(values_scaled)),
                            float(np.mean(values_dac)),
                            float(np.std(values_dac)),
                        ])
                    else:
                        writer.writerow([charge, pixel, asic, 0, "", "", "", ""])

    with output_path_jitter.open("w", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["charge", "asic", "mean_jitter_std_toa", "pixels_used"])

        for charge in charges:
            for asic in asics:
                pixel_stds = []
                for pixel in range(N_PIXELS):
                    values = toa_values_scaled.get((charge, pixel, asic), [])
                    if len(values) >= MIN_SAMPLES_PER_PIXEL:
                        pixel_stds.append(float(np.std(values)))

                if pixel_stds:
                    mean_val = float(np.mean(pixel_stds))
                    used = len(pixel_stds)
                    mean_jitter[(charge, asic)] = mean_val
                    pixels_used[(charge, asic)] = used
                    writer.writerow([charge, asic, mean_val, used])
                else:
                    mean_jitter[(charge, asic)] = np.nan
                    pixels_used[(charge, asic)] = 0
                    writer.writerow([charge, asic, "", 0])

    

    plt.figure(figsize=(10, 6))

    plot_charges = [c for c in charges if c >= min_plot_charge]
    if not plot_charges:
        plot_charges = charges
    plot_charges_real = [c * 0.4 + 1 for c in plot_charges]

    for asic in asics:
        y = np.array([mean_jitter[(charge, asic)] for charge in plot_charges], dtype=float)
        if np.all(np.isnan(y)):
            continue
        plt.plot(plot_charges_real, y, label=f"ASIC {asic}")

    plt.xlabel("Charge [fC]")
    if LSB is not None:
        plt.ylabel("Jitter (TOA std) [ps]")
    else:
        plt.ylabel("Jitter (TOA std)")
    plt.title("Jitter (TOA std) vs Charge")
    plt.grid()
    if asics:
        plt.legend()
    plt.tight_layout()
    plt.savefig(output_plot)
    plt.close()

    print(f"[INFO] jitter: saved per-pixel TOA summary to {output_path_pixels}")
    print(f"[INFO] jitter: saved jitter summary to {output_path_jitter}")
    print(f"[INFO] jitter: saved plot to {output_plot}")

    return {
        "toa_csv": str(output_path_pixels),
        "jitter_csv": str(output_path_jitter),
        "plot_pdf": str(output_plot),
    }


def main():
    parser = argparse.ArgumentParser("jitter analysis")
    parser.add_argument("--input-folder", required=True, help="Folder analysed by run_analysis.py")
    parser.add_argument("--output-dir", required=True, help="Directory where jitter outputs are saved")
    parser.add_argument("--output-prefix", default="", help="Prefix for output files")
    parser.add_argument("--min-plot-charge", type=int, default=MIN_PLOT_CHARGE)
    args = parser.parse_args()

    run_jitter_analysis(
        input_folder=args.input_folder,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
        min_plot_charge=args.min_plot_charge,
    )


if __name__ == "__main__":
    main()
