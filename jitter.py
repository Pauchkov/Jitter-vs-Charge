import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

import csv

N_CHARGES = 64
N_PIXELS = 225
N_ASICS = 4
N_INJ_ROWS = 15
INVALID_TOA_CODE = 127
MIN_SAMPLES_PER_PIXEL = 2

TOA = [[[[] for _ in range(N_ASICS)] for _ in range(N_PIXELS)] for _ in range(N_CHARGES)]

def load_toa(input_dir: str):
    toa_data = [[[[] for _ in range(N_ASICS)] for _ in range(N_PIXELS)] for _ in range(N_CHARGES)]
    base_dir = Path(input_dir)

    for i in range(N_INJ_ROWS):
        for charge in range(N_CHARGES):
            file_path = base_dir / f"pixelOn_all_pixelInj_row{i}" / f"timing_data_dacCharge_{charge}.csv"
            with file_path.open(newline="") as csvfile:
                reader = csv.DictReader(csvfile, delimiter=",")
                for row in reader:
                    pixel = int(row["pixel"])
                    asic = int(row["asic"])
                    toa = int(row["toa"])
                    crc = int(row["crc"])
                    if 0 <= pixel < N_PIXELS and 0 <= asic < N_ASICS:
                        if crc == 0 and toa != INVALID_TOA_CODE:
                            toa_data[charge][pixel][asic].append(toa)

    return toa_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute TOA jitter from charge scan CSV files.")
    parser.add_argument("--dir", dest="input_dir", required=True, help="Input directory with pixelOn_all_pixelInj_row* subdirectories.")
    args = parser.parse_args()

    TOA = load_toa(args.input_dir)

    pixel_std_toa = np.full((N_CHARGES, N_PIXELS, N_ASICS), np.nan)

    mean_jitter_toa = np.full((N_CHARGES, N_ASICS), np.nan)
    pixels_used = np.zeros((N_CHARGES, N_ASICS), dtype=int)

    for charge in range(N_CHARGES):
        for asic in range(N_ASICS):
            pixel_stds = []
            for pixel in range(N_PIXELS):
                values = TOA[charge][pixel][asic]
                if len(values) >= MIN_SAMPLES_PER_PIXEL:
                    pixel_std = np.std(values)
                    pixel_std_toa[charge][pixel][asic] = pixel_std
                    pixel_stds.append(pixel_std)
            if pixel_stds:
                mean_jitter_toa[charge][asic] = float(np.mean(pixel_stds))
                pixels_used[charge][asic] = len(pixel_stds)

    plt.figure(figsize=(10, 6))
    for asic in range(N_ASICS):
        if np.all(np.isnan(mean_jitter_toa[:, asic])):
            continue
        plt.plot(range(N_CHARGES), mean_jitter_toa[:, asic], label=f"ASIC {asic}")
    plt.xlabel("DAC Charge Code")
    plt.ylabel("Mean per-pixel TOA std")
    plt.title("Jitter (TOA std) vs Charge")
    plt.legend()
    plt.grid()
    plt.show()

    output_path_pixels = "/toa_output.csv"
    output_path_jitter = "/jitter_output.csv"

    with open(output_path_pixels, "w", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["charge", "pixel", "asic", "count", "mean_toa", "std_toa"])
        for charge in range(N_CHARGES):
            for pixel in range(N_PIXELS):
                for asic in range(N_ASICS):
                    values = TOA[charge][pixel][asic]
                    if values:
                        writer.writerow([charge, pixel, asic, len(values), float(np.mean(values)), float(np.std(values))])
                    else:
                        writer.writerow([charge, pixel, asic, 0, "", ""])

    with open(output_path_jitter, "w", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["charge", "asic", "mean_jitter_std_toa", "pixels_used"])
        for charge in range(N_CHARGES):
            for asic in range(N_ASICS):
                value = mean_jitter_toa[charge][asic]
                if np.isnan(value):
                    writer.writerow([charge, asic, "", pixels_used[charge][asic]])
                else:
                    writer.writerow([charge, asic, float(value), pixels_used[charge][asic]])
