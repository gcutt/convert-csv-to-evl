import sys
from pathlib import Path
from datetime import timedelta

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.converter import convert_csv_to_evl
from src.utils import parse_offset_string

def main():
    input_csv = input("📄 Enter path to input CSV file: ").strip()
    output_evl = input("📁 Enter path to output EVL file: ").strip()
    offset_str = input("⏱️ Enter time offset [+/-hh:mm:ss] (e.g. +07:00:00): ").strip()
    mode = input("🎛️ Choose mode [depth | vertical_state]: ").strip().lower()

    # if mode not in {"depth", "vertical_state"}:
    #     print("⚠️ Invalid mode. Defaulting to 'depth'.")
    #     mode = "depth"

    def resolve_mode(user_input: str) -> str:
        user_input = user_input.strip().lower()
        if "depth".startswith(user_input):
            return "depth"
        elif "vertical_state".startswith(user_input):
            return "vertical_state"
        else:
            print("⚠️ Invalid mode. Defaulting to 'depth'.")
            return "depth"

    mode_input = input("🎛️ Choose mode [depth | vertical_state]: ")
    mode = resolve_mode(mode_input)

    try:
        offset = parse_offset_string(offset_str)
    except ValueError as e:
        print(f"⚠️ {e}. Using no offset.")
        offset = timedelta()

    depth_multiplier = 1.0
    if mode == "depth":
        multiplier_str = input("📐 Enter depth multiplier (e.g. -10.0): ").strip()
        try:
            depth_multiplier = float(multiplier_str)
        except ValueError:
            print("⚠️ Invalid multiplier. Using 1.0.")
            depth_multiplier = 1.0

    evl_lines = convert_csv_to_evl(
        csv_path=input_csv,
        offset=offset,
        depth_multiplier=depth_multiplier,
        mode=mode
    )

    with open(output_evl, "w", newline="") as f:
        for line in evl_lines:
            f.write(line + "\r\n")

    print(f"\n✅ EVL file written to {output_evl}")
    print(f"   Mode: {mode}")
    print(f"   Offset: {offset}")
    if mode == "depth":
        print(f"   Depth scaled by: {depth_multiplier}")

if __name__ == "__main__":
    main()

##----------------------------------------------
# import sys
# from pathlib import Path
#
# # Add project root to sys.path
# sys.path.append(str(Path(__file__).resolve().parent.parent))
#
# from src.converter import convert_csv_to_evl
# from src.utils import parse_offset_string
#
# ## add prompt for multiplier
# def main():
#     input_csv = input("Enter path to input CSV file: ").strip()
#     output_evl = input("Enter path to output EVL file: ").strip()
#     offset_str = input("Enter time offset [+/-hh:mm:ss] (e.g. +07:00:00): ").strip()
#     multiplier_str = input("Enter depth multiplier (e.g. -10.0): ").strip()
#
#     try:
#         offset = parse_offset_string(offset_str)
#     except ValueError as e:
#         print(f"⚠️ {e}. Using no offset.")
#         offset = timedelta()
#
#     try:
#         depth_multiplier = float(multiplier_str)
#     except ValueError:
#         print("⚠️ Invalid multiplier. Using 1.0.")
#         depth_multiplier = 1.0
#
#     evl_lines = convert_csv_to_evl(input_csv, offset, depth_multiplier)
#
#     with open(output_evl, "w", newline="") as f:
#         for line in evl_lines:
#             f.write(line + "\r\n")
#
#     print(f"✅ EVL file written to {output_evl} with offset {offset} and depth scaled by {depth_multiplier}")
#
#
# def main():
#     input_csv = input("Enter path to input CSV file: ").strip()
#     output_evl = input("Enter path to output EVL file: ").strip()
#     offset_str = input("Enter time offset [+/-hh:mm:ss] (e.g. +07:00:00): ").strip()
#
#     try:
#         offset = parse_offset_string(offset_str)
#     except ValueError as e:
#         print(f"⚠️ {e}. Using no offset.")
#         offset = timedelta()
#
#     evl_lines = convert_csv_to_evl(input_csv, offset)
#
#     with open(output_evl, "w", newline="") as f:
#         for line in evl_lines:
#             f.write(line + "\r\n")
#
#     print(f"✅ EVL file written to {output_evl} with offset {offset}")
#
# #
# def main():
#     input_csv = input("Enter path to input CSV file: ").strip()
#     output_evl = input("Enter path to output EVL file: ").strip()
#     offset_str = input("Enter time offset in hours (e.g. +7 or -3.5): ").strip()
#
#     try:
#         offset_hours = float(offset_str)
#     except ValueError:
#         print("⚠️ Invalid offset. Using 0.")
#         offset_hours = 0.0
#
#     evl_lines = convert_csv_to_evl(input_csv, offset_hours)
#
#     with open(output_evl, "w", newline="") as f:
#         for line in evl_lines:
#             f.write(line + "\r\n")
#
#     print(f"✅ EVL file written to {output_evl} with offset {offset_hours:+.2f} hours")
#
#
# def main():
#     input_csv = input("Enter path to input CSV file: ").strip()
#     output_evl = input("Enter path to output EVL file: ").strip()
#
#     evl_lines = convert_csv_to_evl(input_csv)
#
#     with open(output_evl, "w", newline="") as f:
#         for line in evl_lines:
#             f.write(line + "\r\n")
#
#     print(f"✅ Process done. EVL file written to {output_evl}")
#
# if __name__ == "__main__":
#     main()