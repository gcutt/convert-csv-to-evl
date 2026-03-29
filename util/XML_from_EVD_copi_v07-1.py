import xml.etree.ElementTree as ET
import os
import json
from collections import Counter
from datetime import datetime
import re
import struct
import xml.etree.ElementTree as ET


##
OPTIONS_INSPECTBIN = False


# ============================================================
# 1. STREAM XML PACKETS UNTIL BINARY APPEARS
# ============================================================

BEAM_TAG_RE = re.compile(br'<BeamAngles[^>]*>')
PACKET_START_RE = re.compile(br'<Packet\b')
PACKET_END_RE = re.compile(br'</Packet>')


##
def count_pingdata_blocks(evd_path):
    with open(evd_path, "rb") as f:
        data = f.read()
    # Count all <PingData ...> tags
    return len(re.findall(br'<PingData\b', data))


def iter_xml_packets_binary_aware(evd_path):
    with open(evd_path, "rb") as f:
        data = f.read()

    pos = 0
    n = len(data)
    packets_parsed = 0

    while pos < n:
        # Look for next <Packet or <BeamAngles
        m_pkt = PACKET_START_RE.search(data, pos)
        m_beam = BEAM_TAG_RE.search(data, pos)

        # Decide which comes first
        candidates = [(m_pkt, "packet"), (m_beam, "beam")]
        candidates = [(m, kind) for (m, kind) in candidates if m is not None]
        if not candidates:
            break

        m, kind = min(candidates, key=lambda x: x[0].start())
        pos = m.start()

        if kind == "packet":
            # Find end of this Packet
            m_end = PACKET_END_RE.search(data, pos)
            if not m_end:
                break
            xml_bytes = data[pos:m_end.end()]
            try:
                elem = ET.fromstring(xml_bytes.decode("utf-8", errors="ignore"))
                packets_parsed += 1
                yield elem
            except Exception:
                # malformed packet, skip
                pass
            pos = m_end.end()
        else:
            # BeamAngles: parse start tag, skip binary payload, skip closing tag
            tag_bytes = m.group(0)
            tag_text = tag_bytes.decode("utf-8", errors="ignore")
            # Extract BeamCount
            m_bc = re.search(r'BeamCount="(\d+)"', tag_text)
            beam_count = int(m_bc.group(1)) if m_bc else 0

            # Move pos to end of start tag
            pos = m.end()

            # Skip binary payload: beam_count * 4 bytes (float32)
            skip_bytes = beam_count * 4
            pos += skip_bytes

            # Skip closing tag </BeamAngles>
            close_idx = data.find(b"</BeamAngles>", pos)
            if close_idx == -1:
                break
            pos = close_idx + len(b"</BeamAngles>")
            # Then continue loop



# ============================================================
# 2. PACKET COLLECTION + TIME PARSING
# ============================================================

def parse_time_attr(time_str):
    if time_str is None:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S.%f", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return None

def collect_packets(evd_path):
    packets = []

    for elem in iter_xml_packets_binary_aware(evd_path):
        ptype = elem.attrib.get("Type", "")
        params = elem.find("Parameters")
        attrs = params.attrib if params is not None else {}
        t = parse_time_attr(attrs.get("Time"))

        packets.append({
            "type": ptype,
            "time": t,
            "attrs": attrs,
            "raw_elem": elem,
        })

    # Diagnostics: we no longer track bytes_read here
    diag = {
        "packets_parsed": len(packets),
        "bytes_read": None,
        "file_size": os.path.getsize(evd_path),
        "reached_eof": True,   # binary-aware scanner always reaches EOF
    }

    return packets, diag


# ============================================================
# 3. PACKET COUNTS
# ============================================================

def count_packet_types(packets):
    return Counter(p["type"] for p in packets)


# ============================================================
# 4. TIME BOUNDS + NAVIGATION
# ============================================================

def extract_time_bounds(packets):
    times = [p["time"] for p in packets if p["time"] is not None]
    if not times:
        return None, None, None
    t_min = min(times)
    t_max = max(times)
    duration = (t_max - t_min).total_seconds()
    return t_min, t_max, duration

def build_navigation_series(packets):
    nav = []
    for p in packets:
        if p["type"] != "Position":
            continue
        t = p["time"]
        attrs = p["attrs"]
        lat = attrs.get("Latitude")
        lon = attrs.get("Longitude")
        if t is None or lat is None or lon is None:
            continue
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            continue
        nav.append((t, lat, lon))
    return nav

# def build_navigation_series(packets):
#     """
#     Navigation = Position packet lat/lon + Roll/Pitch timestamps.
#     """
#     pos = next((p for p in packets if p["type"] == "Position"), None)
#     if not pos:
#         return []
#
#     lat = float(pos["attrs"]["Latitude"])
#     lon = float(pos["attrs"]["Longitude"])
#
#     nav = []
#     for p in packets:
#         if p["type"] in ("Roll", "Pitch") and p["time"]:
#             nav.append((p["time"], lat, lon))
#
#     return nav


# ============================================================
# 5. SOUNDer CONFIGURATION
# ============================================================

def extract_sounder_config(packets):
    """
    Extract basic sounder configuration from XML packets.
    If fields are missing (common in Seapix EVD), return defaults.
    """
    cfg = {
        "sonar_model": None,
        "sound_speed": None,
        "absorption": None,
        "beam_count": None,
        "beam_spread": None,
        "beam_angle_mode": None,
    }

    for p in packets:
        attrs = p["attrs"]
        ptype = p["type"]

        if ptype == "TransducerList":
            cfg["sonar_model"] = attrs.get("Sounder")

        if ptype == "Calibration":
            cfg["absorption"] = attrs.get("AbsorptionCoefficient")
            cfg["sound_speed"] = attrs.get("SoundSpeed")

        if ptype == "BeamAngles":
            cfg["beam_count"] = attrs.get("BeamCount")
            cfg["beam_spread"] = attrs.get("BeamSpread")
            cfg["beam_angle_mode"] = attrs.get("BeamAngleMode")

    return cfg

# def extract_sounder_config(packets):
#     cfg = {
#         "sounder_model": None,
#         "absorption": None,
#         "sound_speed": None,
#         "beam_count": None,
#         "beam_spread": None,
#         "beam_angle_mode": None,
#     }
#
#     for p in packets:
#         attrs = p["attrs"]
#         ptype = p["type"]
#
#         if ptype == "TransducerList":
#             cfg["sounder_model"] = attrs.get("Sounder")
#
#         if ptype == "Calibration":
#             cfg["absorption"] = attrs.get("AbsorptionCoefficient")
#             cfg["sound_speed"] = attrs.get("SoundSpeed")
#
#         if ptype == "BeamAngles":
#             cfg["beam_count"] = attrs.get("BeamCount")
#             cfg["beam_spread"] = attrs.get("BeamSpread")
#             cfg["beam_angle_mode"] = attrs.get("BeamAngleMode")
#
#     return cfg


# ============================================================
# 6. INFER PING COUNT
# ============================================================

def infer_ping_count(packets):
    return sum(1 for p in packets if p["type"] in ("Roll", "Pitch"))


# ============================================================
# 7. SONAR-NETCDF4 METADATA GROUPS
# ============================================================

def build_sonarnetcdf4_metadata(packets, evd_path):
    t_start, t_end, duration = extract_time_bounds(packets)
    nav = build_navigation_series(packets)  # see below
    sounder = extract_sounder_config(packets)

    ping_count = count_pingdata_blocks(evd_path)

    return {
        "platform": {
            "platform_type": "vessel",
        },
        "sonar": {
            "sonar_model": sounder["sonar_model"],
            "sound_speed": sounder["sound_speed"],
            "absorption": sounder["absorption"],
        },
        "beam": {
            "beam_count": sounder["beam_count"],
            "beam_spread": sounder["beam_spread"],
            "beam_angle_mode": sounder["beam_angle_mode"],
        },
        "ping": {
            "ping_count": ping_count,
            "time_start": t_start.isoformat() if t_start else None,
            "time_end": t_end.isoformat() if t_end else None,
            "duration_seconds": duration,
        },
        "navigation": {
            "nav_count": len(nav),
            "time": [t.isoformat() for (t, _, _) in nav],
            "latitude": [lat for (_, lat, _) in nav],
            "longitude": [lon for (_, _, lon) in nav],
        },
    }

# def build_sonarnetcdf4_metadata(packets):
#     t_start, t_end, duration = extract_time_bounds(packets)
#     nav = build_navigation_series(packets)
#     sounder = extract_sounder_config(packets)
#     ping_count = infer_ping_count(packets)
#
#     return {
#         "platform": {
#             "platform_type": "vessel",
#         },
#         "sonar": {
#             "sonar_model": sounder["sounder_model"],
#             "sound_speed": sounder["sound_speed"],
#             "absorption": sounder["absorption"],
#         },
#         "beam": {
#             "beam_count": sounder["beam_count"],
#             "beam_spread": sounder["beam_spread"],
#             "beam_angle_mode": sounder["beam_angle_mode"],
#         },
#         "ping": {
#             "ping_count": ping_count,
#             "time_start": t_start.isoformat() if t_start else None,
#             "time_end": t_end.isoformat() if t_end else None,
#             "duration_seconds": duration,
#         },
#         "navigation": {
#             "nav_count": len(nav),
#             "time": [t.isoformat() for (t, _, _) in nav],
#             "latitude": [lat for (_, lat, _) in nav],
#             "longitude": [lon for (_, _, lon) in nav],
#         },
#     }


# ============================================================
# 8. ACMETA METADATA
# ============================================================

def build_acmeta_metadata(packets, sonarnc_meta):
    t_start, t_end, duration = extract_time_bounds(packets)

    return {
        "source": {
            "file_type": "Seapix_EVD",
            "original_file": None,
        },
        "time_coverage": {
            "start": t_start.isoformat() if t_start else None,
            "end": t_end.isoformat() if t_end else None,
            "duration_seconds": duration,
        },
        "platform": sonarnc_meta["platform"],
        "sonar": sonarnc_meta["sonar"],
        "beam": sonarnc_meta["beam"],
        "ping": sonarnc_meta["ping"],
        "navigation": sonarnc_meta["navigation"],
        "packet_counts": count_packet_types(packets),
    }


# ============================================================
# 9. MAIN
# ============================================================

def main():
    # evd_path = r"D:\Cutter\0-PROJECTS\EVD-TestData\EVD-x01.evd"
    evd_path = r"D:\Cutter\0-PROJECTS\EVD-TestData\1018_0008.evd"

    print(f"Reading XML packets from:\n  {evd_path}\n")

    packets, diag = collect_packets(evd_path)

    print("Diagnostics:")
    for k, v in diag.items():
        print(f"  {k}: {v}")
    print()

    print("Packet counts:")
    for k, v in count_packet_types(packets).items():
        print(f"  {k}: {v}")
    print()

    # sonarnc_meta = build_sonarnetcdf4_metadata(packets)
    sonarnc_meta = build_sonarnetcdf4_metadata(packets, evd_path)
    acmeta = build_acmeta_metadata(packets, sonarnc_meta)


    print("AcMeta metadata (text):")
    print(json.dumps(acmeta, indent=2))

    out_json = os.path.splitext(evd_path)[0] + "_acmeta_v07-1.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(acmeta, f, indent=2)
    print(f"\nAcMeta JSON written to:\n  {out_json}")


    if( OPTIONS_INSPECTBIN ):
        ## Examine binary data
        NBYTESBIN = 20000
        print( f"Examine binary data NBYTES = {NBYTESBIN}")
        with open(evd_path, "rb") as f:
            data = f.read(NBYTESBIN)
        # Find the BeamAngles tag
        idx = data.find(b"<BeamAngles")
        print(idx)
        # Print 300 bytes starting at the binary payload
        print(data[idx:idx + 300])

        ## Examine the first <BeamData> block
        print(f"\nExamine first <BeamData> block\n")
        with open(evd_path, "rb") as f:
            data = f.read()

        idx = data.find(b"<BeamData")
        print("BeamData starts at:", idx)

        print(data[idx:idx + 500])


if __name__ == "__main__":
    main()