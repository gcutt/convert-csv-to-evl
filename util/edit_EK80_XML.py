#-----------------------------------------------
## edit_EK80_XML.py
#
#  Purpose:
#   Edit environment data parameters in the XML of EK80 raw files.
#
#   Find XML datagrams in EK80 files, and process <Environment> blocks, only.
#   Revise "Temperature", "Salinity", and "SoundSpeed" values according to user input values.
#
#   Runs on all raw files found in specified data dir
#
#  Arguments:
#    --dir "{mydir}"
#    --temp ##.#
#    --sal ##.#
#    --ssp ####.#
#
#  How to run:
#    Run calling script "edit_EK80_XML_run.py"
#
#  E.g. syntax to run:
#   > python edit_EK80_XML_run.py --dir "D:\_DATA\tst2" --temp 22.2 --sal 33.3 --ssp 1555.5
#
#  Example output:
#     _dev\convert-csv-to-evl\util>python edit_EK80_XML_run.py --dir "D:\_DATA\tst2" --temp 22.2 --sal 33.3 --ssp 1555.5
#
#     Processing directory: D:\_DATA\tst2
#     Found 3 .raw files
#
#     ========================================
#     Processing file: CAL_333CW_512_38_BERMUDA_2025_DAY-Phase0-D20250902-T213836-0.raw
#     Output file    : CAL_333CW_512_38_BERMUDA_2025_DAY-Phase0-D20250902-T213836-0_edited.raw
#     ========================================
#
#     === ENVIRONMENT XML SUMMARY ===
#     XML0 datagrams scanned : 59
#     <Environment> blocks modified : 1
#
#     --- Environment block at offset 2811 ---
#     Original:
#       Temperature: 29.348
#       Salinity: 36.028
#       SoundSpeed: 1545.082
#     Rewritten:
#       Temperature: 22.2
#       Salinity: 33.3
#       SoundSpeed: 1555.5
#
#     Output written to : D:\_DATA\tst2\CAL_333CW_512_38_BERMUDA_2025_DAY-Phase0-D20250902-T213836-0_edited.raw
#     =========================================
#
#     ========================================
#     Processing file: CAL_333CW_512_38_BERMUDA_2025_DAY-Phase0-D20250902-T213930-0.raw
#     Output file    : CAL_333CW_512_38_BERMUDA_2025_DAY-Phase0-D20250902-T213930-0_edited.raw
#     ========================================
#-----------------------------------------------


import struct
from pathlib import Path
import xml.etree.ElementTree as ET

DG_HEADER_FORMAT = "<4sBBHII"
DG_HEADER_SIZE = struct.calcsize(DG_HEADER_FORMAT)

##
VERBOSE  = False

# ----------------------------------------------------------------------
#  Helpers: datagram iteration + header parsing
# ----------------------------------------------------------------------

def iter_datagrams(f):
    """Yield (offset, dg_len, body_bytes) for each datagram in a Simrad .raw file."""
    while True:
        offset = f.tell()
        len_bytes = f.read(4)
        if not len_bytes:
            break  # EOF

        if len(len_bytes) < 4:
            raise IOError(f"Truncated datagram length at offset {offset}")

        dg_len = struct.unpack("<I", len_bytes)[0]
        body = f.read(dg_len)
        if len(body) < dg_len:
            raise IOError(f"Truncated datagram body at offset {offset}")

        len2_bytes = f.read(4)
        if len(len2_bytes) < 4:
            raise IOError(f"Missing trailing length at offset {offset}")

        dg_len2 = struct.unpack("<I", len2_bytes)[0]
        if dg_len != dg_len2:
            raise IOError(f"Length mismatch at offset {offset}: {dg_len} != {dg_len2}")

        yield offset, dg_len, body


def parse_header(body):
    """Return (dg_type, header_bytes, payload_bytes)."""
    header = body[:DG_HEADER_SIZE]
    payload = body[DG_HEADER_SIZE:]
    dg_type, *_ = struct.unpack(DG_HEADER_FORMAT, header)
    return dg_type, header, payload

# ----------------------------------------------------------------------
#  XML helpers: extract + modify environment values
# ----------------------------------------------------------------------

TAG_MAP = {
    "temperature": ["waterTemperature", "Temperature", "temperature"],
    "salinity": ["Salinity", "salinity"],
    "soundspeed": ["SoundSpeed", "soundSpeed", "sound_speed"],
}

def extract_environment_values(root):
    """Return dict of found environment values and which tags were used."""
    found = {
        "temperature": (None, None),
        "salinity": (None, None),
        "soundspeed": (None, None),
    }

    for key, tag_list in TAG_MAP.items():
        for tag in tag_list:
            elem = root.find(f".//{tag}")
            if elem is not None and elem.text is not None:
                found[key] = (elem.text.strip(), tag)
                break

    return found


def modify_environment_xml(payload, temperature=None, salinity=None, soundspeed=None):
    """Modify <Environment> blocks inside XML0 payloads and return summary info."""
    start = payload.find(b"<")
    if start == -1:
        return payload, False, None

    xml_bytes = payload[start:]
    xml_text = xml_bytes.decode("utf-8", errors="replace")

    if "<Environment" not in xml_text:
        return payload, False, None

    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return payload, False, None

    # Only process <Environment> blocks
    if root.tag != "Environment":
        return payload, False, None

    # Extract original values
    original = {
        "Temperature": root.get("Temperature"),
        "Salinity": root.get("Salinity"),
        "SoundSpeed": root.get("SoundSpeed"),
    }

    changed = False

    # Apply updates
    if temperature is not None:
        root.set("Temperature", str(temperature))
        changed = True
    if salinity is not None:
        root.set("Salinity", str(salinity))
        changed = True
    if soundspeed is not None:
        root.set("SoundSpeed", str(soundspeed))
        changed = True

    # Update nested transducer SoundSpeed
    for elem in root.iter("Transducer"):
        if soundspeed is not None:
            elem.set("SoundSpeed", str(soundspeed))
            changed = True

    if not changed:
        return payload, False, None

    # Build new payload
    new_xml = ET.tostring(root, encoding="utf-8")
    new_payload = payload[:start] + new_xml

    # Build summary
    summary = {
        "original": original,
        "new": {
            "Temperature": str(temperature),
            "Salinity": str(salinity),
            "SoundSpeed": str(soundspeed),
        }
    }

    return new_payload, True, summary




# ----------------------------------------------------------------------
#  Main rewrite function with full diagnostics
# ----------------------------------------------------------------------

def rewrite_raw_with_env(in_raw, out_raw, temperature, salinity, soundspeed):
    in_raw = Path(in_raw)
    out_raw = Path(out_raw)

    xml0_count = 0
    env_modified = 0
    summaries = []
    output_chunks = []

    with in_raw.open("rb") as fin:
        for offset, dg_len, body in iter_datagrams(fin):
            dg_type, header, payload = parse_header(body)

            if dg_type == b"XML0":
                xml0_count += 1

                new_payload, changed, summary = modify_environment_xml(
                    payload,
                    temperature=temperature,
                    salinity=salinity,
                    soundspeed=soundspeed,
                )

                if changed:
                    env_modified += 1
                    payload = new_payload
                    summaries.append((offset, summary))

            # Rebuild datagram
            new_body = header + payload
            new_len = len(new_body)
            output_chunks.append((new_len, new_body))

    # Only write output if something changed
    if env_modified > 0:
        with out_raw.open("wb") as fout:
            for new_len, new_body in output_chunks:
                fout.write(struct.pack("<I", new_len))
                fout.write(new_body)
                fout.write(struct.pack("<I", new_len))

        print("\n=== ENVIRONMENT XML SUMMARY ===")
        print(f"XML0 datagrams scanned : {xml0_count}")
        print(f"<Environment> blocks modified : {env_modified}\n")

        for offset, summary in summaries:
            print(f"--- Environment block at offset {offset} ---")
            print("Original:")
            for k, v in summary["original"].items():
                print(f"  {k}: {v}")
            print("Rewritten:")
            for k, v in summary["new"].items():
                print(f"  {k}: {v}")
            print()

        print(f"Output written to : {out_raw}")
        print("=========================================\n")

    else:
        print("\n=== ENVIRONMENT XML SUMMARY ===")
        print(f"XML0 datagrams scanned : {xml0_count}")
        print("⚠️  No <Environment> blocks found — no output file written.")
        print("=========================================\n")

