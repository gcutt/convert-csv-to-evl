## edit_EK80_XML_run.py

#!/usr/bin/env python3
import argparse
from pathlib import Path
from edit_EK80_XML import rewrite_raw_with_env   # your module

def process_directory(
    directory,
    temperature,
    salinity,
    soundspeed,
    suffix="_edited"
):
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    raw_files = sorted(directory.glob("*.raw"))
    if not raw_files:
        print(f"No .raw files found in: {directory}")
        return

    print(f"\nProcessing directory: {directory}")
    print(f"Found {len(raw_files)} .raw files\n")

    for raw in raw_files:
        out_raw = raw.with_name(raw.stem + suffix + raw.suffix)

        print("\n========================================")
        print(f"Processing file: {raw.name}")
        print(f"Output file    : {out_raw.name}")
        print("========================================\n")

        rewrite_raw_with_env(
            in_raw=raw,
            out_raw=out_raw,
            temperature=temperature,
            salinity=salinity,
            soundspeed=soundspeed,
        )

    print("\nBatch processing complete.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Modify environment parameters in EK80 .raw XML0 datagrams."
    )

    parser.add_argument(
        "--dir",
        required=True,
        help="Directory containing .raw files to process"
    )

    parser.add_argument("--temp", type=float, default=None,
                        help="Temperature value to apply")
    parser.add_argument("--sal", type=float, default=None,
                        help="Salinity value to apply")
    parser.add_argument("--ssp", type=float, default=None,
                        help="Sound speed value to apply")

    parser.add_argument("--suffix", default="_edited",
                        help="Suffix added to output .raw files")

    args = parser.parse_args()

    process_directory(
        directory=args.dir,
        temperature=args.temp,
        salinity=args.sal,
        soundspeed=args.ssp,
        suffix=args.suffix,
    )


if __name__ == "__main__":
    main()