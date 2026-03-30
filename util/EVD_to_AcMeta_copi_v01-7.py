import re
import xml.etree.ElementTree as ET
import os
import csv
from datetime import datetime
import json
from collections import Counter

print("RUNNING SCRIPT VERSION X")

OPTIONS_INSPECTBIN = False
OPTIONS_VERBOSE = False
OPTIONS_DEBUG_BEAMANGLES = False

# ============================================================
# 1. STREAM XML PACKETS UNTIL BINARY APPEARS
# ============================================================

BEAM_TAG_RE = re.compile(br'<BeamAngles[^>]*>')

# PACKET_OPEN_RE = re.compile(
#     br'<Packet\b[^>]*Type\s*=\s*"{1,2}([^"]+)"{1,2}',
#     re.IGNORECASE
# )
# PACKET_OPEN_RE = re.compile(
#     br'<Packet\b[^>]*Type\s*=\s*["\']([^"\']+)["\']',
#     re.IGNORECASE
# )
PACKET_OPEN_RE = re.compile(
    br'<Packet\b(?:(?!</Packet>).)*?\bType\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE | re.DOTALL
)
PACKET_CLOSE_RE = re.compile(br'</Packet\s*>', re.IGNORECASE)

##
def summarize_pingdata(evd_path):
    """
    Scan all <PingData ...> tags and summarize:
      - ping_count
      - min/max SampleCount
      - min StartRange
      - max StopRange
    """
    with open(evd_path, "rb") as f:
        data = f.read()

    ping_tags = re.findall(br'<PingData[^>]*>', data)
    ping_count = len(ping_tags)

    if ping_count == 0:
        return {
            "ping_count": 0,
            "sample_count_min": None,
            "sample_count_max": None,
            "start_range_min": None,
            "stop_range_max": None,
        }

    sample_counts = []
    start_ranges = []
    stop_ranges = []

    for tag in ping_tags:
        text = tag.decode("utf-8", errors="ignore")

        def _get(attr):
            m = re.search(attr + r'="([^"]+)"', text)
            return m.group(1) if m else None

        sc = _get(r'SampleCount')
        sr = _get(r'StartRange')
        er = _get(r'StopRange')

        if sc is not None:
            try:
                sample_counts.append(int(sc))
            except ValueError:
                pass
        if sr is not None:
            try:
                start_ranges.append(float(sr))
            except ValueError:
                pass
        if er is not None:
            try:
                stop_ranges.append(float(er))
            except ValueError:
                pass

    return {
        "ping_count": ping_count,
        "sample_count_min": min(sample_counts) if sample_counts else None,
        "sample_count_max": max(sample_counts) if sample_counts else None,
        "start_range_min": min(start_ranges) if start_ranges else None,
        "stop_range_max": max(stop_ranges) if stop_ranges else None,
    }

def summarize_beamangles(evd_path):

    with open(evd_path, "rb") as f:
        data = f.read()

    ping_idx = data.find(b"<PingData")
    if ping_idx == -1:
        ping_idx = len(data)

    beam_tags = list(re.finditer(br'<BeamAngles[^>]*>', data[:ping_idx]))
    if not beam_tags:
        return {
            "beam_count": None,
        }

    m = beam_tags[-1]
    tag = m.group(0).decode("utf-8", errors="ignore")

    def _get(attr):
        mm = re.search(attr + r'="([^"]+)"', tag)
        return mm.group(1) if mm else None

    beam_count = int(_get("BeamCount")) if _get("BeamCount") else None

    return {
        "beam_count": beam_count,
    }


def collect_beam_spreads_from_multibeam_ping(packets):
    spreads = []
    for p in packets:
        if p.get("type") != "MultibeamPing":
            continue

        elem = p["raw_elem"]
        for ba in elem.findall("BeamAngles"):
            val = ba.attrib.get("BeamSpread")
            if val is None:
                continue
            try:
                spreads.append(float(val))
            except ValueError:
                continue

    return sorted(set(spreads))

def extract_multibeam_ping_info(packets):
    for p in packets:
        if p["type"] == "MultibeamPing":
            root = p["raw_elem"]

            calib = root.find("Calibration")
            beam = root.find("BeamAngles")

            return {
                "sound_speed": calib.attrib.get("SoundSpeed") if calib is not None else None,
                "absorption": calib.attrib.get("AbsorptionCoefficient") if calib is not None else None,
                "beam_count": int(beam.attrib.get("BeamCount")) if beam is not None else None,
                "beam_spread": float(beam.attrib.get("BeamSpread")) if beam is not None else None,
                "beam_angle_mode": beam.attrib.get("BeamAngleMode") if beam is not None else None,
            }

    return {}

def extract_initial_xml_region(evd_path):
    with open(evd_path, "rb") as f:
        data = f.read()

    print("DEBUG: extract_initial_xml_region reading:", evd_path)

    # stop before first MultibeamPing (still pure XML)
    idx = data.find(b'<Packet Type="MultibeamPing"')
    if idx == -1:
        idx = len(data)

    xml_region = data[:idx].decode("utf-8", errors="ignore")
    return xml_region


def count_pingdata_blocks(evd_path):
    with open(evd_path, "rb") as f:
        data = f.read()
    # Count all <PingData ...> tags
    return len(re.findall(br'<PingData\b', data))

def iter_xml_packets_binary_aware(evd_path):
    print("\n==============================")
    print("DEBUG: ENTERED iter_xml_packets_binary_aware()")
    print("==============================")

    # --- Read file ---
    with open(evd_path, "rb") as f:
        data = f.read()
    print(f"DEBUG: read {len(data)} bytes from {evd_path}")

    pos = 0
    n = len(data)
    iteration = 0

    print("\nDEBUG: ENTERING MAIN PACKET LOOP")

    while True:
        iteration += 1
        print(f"\nDEBUG: LOOP ITERATION {iteration}, pos={pos}")

        # --- Find opening tag ---
        m_open = PACKET_OPEN_RE.search(data, pos)
        print("DEBUG: PACKET_OPEN_RE.search returned:", m_open)

        if not m_open:
            print("DEBUG: NO MORE PACKETS — EXITING ITERATOR")
            return

        start = m_open.start()
        print(f"DEBUG: packet start at {start}")

        # --- Find closing tag ---
        m_close = PACKET_CLOSE_RE.search(data, m_open.end())
        print("DEBUG: PACKET_CLOSE_RE.search returned:", m_close)

        if not m_close:
            print("DEBUG: NO closing </Packet> found — skipping this packet")
            pos = m_open.end()
            continue

        end = m_close.end()
        print(f"DEBUG: packet block end at {end}, block size {end - start}")

        block = data[start:end]

        # ============================================================
        # SPECIAL CASE: MultibeamPing packets contain binary
        # ============================================================
        if b'Type="MultibeamPing"' in block:
            print("DEBUG: MultibeamPing detected — building synthetic header")

            # Extract safe header tags only
            params = re.search(br'<Parameters[^>]*/>', block)
            calib  = re.search(br'<Calibration[^>]*/>', block)

            # Extract BeamAngles opening tag and self-close it
            beam = re.search(br'<BeamAngles[^>]*>', block)
            beam_tag = None
            if beam:
                bt = beam.group(0)
                # Convert "<BeamAngles ...>" → "<BeamAngles ... />"
                if not bt.endswith(b'/>'):
                    bt = bt[:-1] + b' />'
                beam_tag = bt

            # Build synthetic XML
            xml_parts = [b'<Packet Type="MultibeamPing">']
            if params:
                xml_parts.append(params.group(0))
            if calib:
                xml_parts.append(calib.group(0))
            if beam_tag:
                xml_parts.append(beam_tag)
            xml_parts.append(b'</Packet>')

            safe_xml = b'\n'.join(xml_parts)

            try:
                elem = ET.fromstring(safe_xml.decode("utf-8", errors="ignore"))
                print("DEBUG: SUCCESS: parsed synthetic MultibeamPing header")
                yield elem
            except Exception as e:
                print("DEBUG: STILL FAILED parsing synthetic header:", e)

            pos = end
            continue
        # ============================================================
        # END SPECIAL CASE
        # ============================================================

        # --- Normal packet parsing for all other types ---
        try:
            xml_text = block.decode("utf-8", errors="ignore")
            elem = ET.fromstring(xml_text)
            print("DEBUG: SUCCESS: parsed full packet:", elem.tag)
            yield elem
        except Exception as e:
            print("DEBUG: XML PARSE FAILED:", e)
            print("DEBUG: Offending XML snippet:", xml_text[:200])

        # --- Advance position ---
        print(f"DEBUG: advancing pos from {pos} to {end}")
        pos = end

# def iter_xml_packets_binary_aware(evd_path):
#     print("\n==============================")
#     print("DEBUG: ENTERED iter_xml_packets_binary_aware()")
#     print("==============================")
#
#     # --- Read file ---
#     with open(evd_path, "rb") as f:
#         data = f.read()
#     print(f"DEBUG: read {len(data)} bytes from {evd_path}")
#
#     pos = 0
#     n = len(data)
#     iteration = 0
#
#     print("\nDEBUG: ENTERING MAIN PACKET LOOP")
#
#     while True:
#         iteration += 1
#         print(f"\nDEBUG: LOOP ITERATION {iteration}, pos={pos}")
#
#         # --- Find opening tag ---
#         m_open = PACKET_OPEN_RE.search(data, pos)
#         print("DEBUG: PACKET_OPEN_RE.search returned:", m_open)
#
#         if not m_open:
#             print("DEBUG: NO MORE PACKETS — EXITING ITERATOR")
#             return
#
#         start = m_open.start()
#         print(f"DEBUG: packet start at {start}")
#
#         # --- Find closing tag ---
#         m_close = PACKET_CLOSE_RE.search(data, m_open.end())
#         print("DEBUG: PACKET_CLOSE_RE.search returned:", m_close)
#
#         if not m_close:
#             print("DEBUG: NO closing </Packet> found — skipping this packet")
#             pos = m_open.end()
#             continue
#
#         end = m_close.end()
#         print(f"DEBUG: packet block end at {end}, block size {end - start}")
#
#         block = data[start:end]
#
#         # ============================================================
#         # SPECIAL CASE: MultibeamPing packets contain binary
#         # ============================================================
#         if b'Type="MultibeamPing"' in block:
#             print("DEBUG: MultibeamPing detected — building synthetic header")
#
#             # Extract safe header tags only
#             params = re.search(br'<Parameters[^>]*/>', block)
#             calib  = re.search(br'<Calibration[^>]*/>', block)
#             beam   = re.search(br'<BeamAngles[^>]*>', block)
#
#             xml_parts = [b'<Packet Type="MultibeamPing">']
#             if params:
#                 xml_parts.append(params.group(0))
#             if calib:
#                 xml_parts.append(calib.group(0))
#             if beam:
#                 xml_parts.append(beam.group(0))
#             xml_parts.append(b'</Packet>')
#
#             safe_xml = b'\n'.join(xml_parts)
#
#             try:
#                 elem = ET.fromstring(safe_xml.decode("utf-8", errors="ignore"))
#                 print("DEBUG: SUCCESS: parsed synthetic MultibeamPing header")
#                 yield elem
#             except Exception as e:
#                 print("DEBUG: STILL FAILED parsing synthetic header:", e)
#
#             pos = end
#             continue
#         # ============================================================
#         # END SPECIAL CASE
#         # ============================================================
#
#         # --- Normal packet parsing for all other types ---
#         try:
#             xml_text = block.decode("utf-8", errors="ignore")
#             elem = ET.fromstring(xml_text)
#             print("DEBUG: SUCCESS: parsed full packet:", elem.tag)
#             yield elem
#         except Exception as e:
#             print("DEBUG: XML PARSE FAILED:", e)
#             print("DEBUG: Offending XML snippet:", xml_text[:200])
#
#         # --- Advance position ---
#         print(f"DEBUG: advancing pos from {pos} to {end}")
#         pos = end

# def iter_xml_packets_binary_aware(evd_path):
#     print("\n==============================")
#     print("DEBUG: ENTERED iter_xml_packets_binary_aware()")
#     print("==============================")
#
#     # --- Read file ---
#     try:
#         with open(evd_path, "rb") as f:
#             data = f.read()
#         print(f"DEBUG: read {len(data)} bytes from {evd_path}")
#     except Exception as e:
#         print(f"DEBUG: file open FAILED: {e}")
#         return
#
#     m = re.search(br'<Packet[^>]{0,200}MultibeamPing', data)
#     print("DEBUG: raw MultibeamPing tag:", m.group(0) if m else None)
#
#     # --- Quick sanity check ---
#     first_packet = data.find(b"<Packet")
#     print("DEBUG: first <Packet> index:", first_packet)
#     if first_packet != -1:
#         print("DEBUG: raw first <Packet> bytes:", data[first_packet:first_packet + 120])
#     else:
#         print("DEBUG: NO <Packet> found in file!")
#         return
#
#     pos = 0
#     n = len(data)
#     iteration = 0
#
#     print("\nDEBUG: ENTERING MAIN PACKET LOOP")
#
#     while True:
#         iteration += 1
#         print(f"\nDEBUG: LOOP ITERATION {iteration}, pos={pos}")
#
#         # --- Find opening tag ---
#         m_open = PACKET_OPEN_RE.search(data, pos)
#         print("DEBUG: PACKET_OPEN_RE.search returned:", m_open)
#
#         if not m_open:
#             print("DEBUG: NO MORE PACKETS — EXITING ITERATOR")
#             return
#
#         start = m_open.start()
#         print(f"DEBUG: packet start at {start}")
#
#         # --- Find closing tag ---
#         m_close = PACKET_CLOSE_RE.search(data, m_open.end())
#         print("DEBUG: PACKET_CLOSE_RE.search returned:", m_close)
#
#         if not m_close:
#             print("DEBUG: NO closing </Packet> found — skipping this packet")
#             pos = m_open.end()
#             continue
#
#         end = m_close.end()
#         print(f"DEBUG: packet block end at {end}, block size {end - start}")
#
#         # --- Extract full packet block ---
#         block = data[start:end]
#
#         # --- Try to parse full XML packet ---
#         try:
#             xml_text = block.decode("utf-8", errors="ignore")
#
#             # Extract only the header portion up to the end of the BeamAngles opening tag
#             header_end = block.find(b'>', block.find(b'<BeamAngles')) + 1
#             safe_xml = block[:header_end]
#
#             try:
#                 elem = ET.fromstring(safe_xml.decode("utf-8", errors="ignore"))
#                 yield elem
#             except Exception as e:
#                 print("DEBUG: XML PARSE FAILED EVEN AFTER TRIM:", e)
#
#             # elem = ET.fromstring(xml_text)
#             # print("DEBUG: SUCCESS: parsed full packet:", elem.tag)
#             # yield elem
#
#         except Exception as e:
#             print("DEBUG: XML PARSE FAILED:", e)
#             print("DEBUG: Offending XML snippet:", xml_text[:200])
#             # Continue scanning
#             pass
#
#         # --- Advance position ---
#         print(f"DEBUG: advancing pos from {pos} to {end}")
#         pos = end


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
    print("DEBUG: collect_packets called (print is inside collect_packets.")

    packets = []
    print(f"DEBUG (collect_packets): packets = {packets}")

    for elem in iter_xml_packets_binary_aware(evd_path):
        print(f"DEBUG (collect_packets): elem in iter_xml...: {elem}")

        ptype = elem.attrib.get("Type", "")
        params = elem.find("Parameters")
        attrs = params.attrib if params is not None else {}
        t = parse_time_attr(attrs.get("Time"))
        print(f"DEBUG (collect_packets): ptype: {ptype}")
        print(f"DEBUG (collect_packets): params: {params}")
        print(f"DEBUG (collect_packets): attrs: {attrs}")
        print(f"DEBUG (collect_packets): t: {t}")

        packets.append({
            "type": ptype,
            "time": t,
            "attrs": attrs,
            "raw_elem": elem,
            "xml": ET.tostring(elem, encoding="unicode"),  # <-- add this
        })

    diag = {
        "packets_parsed": len(packets),
        "bytes_read": None,
        "file_size": os.path.getsize(evd_path),
        "reached_eof": True,
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


# ============================================================
# 5. SOUNDer CONFIGURATION
# ============================================================

def extract_sounder_config(packets):
    """
    Extract basic sounder configuration from packets.
    Calibration and BeamAngles live inside MultibeamPing.
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
        ptype = p["type"]
        elem = p["raw_elem"]

        if ptype == "TransducerList":
            td = elem.find("Transducer")
            if td is not None:
                cfg["sonar_model"] = td.attrib.get("Sounder")

        if ptype == "MultibeamPing":
            cal = elem.find("Calibration")
            if cal is not None:
                cfg["absorption"] = cal.attrib.get("AbsorptionCoefficient")
                cfg["sound_speed"] = cal.attrib.get("SoundSpeed")

            ba = elem.find("BeamAngles")
            if ba is not None:
                cfg["beam_count"] = ba.attrib.get("BeamCount")
                cfg["beam_spread"] = ba.attrib.get("BeamSpread")
                cfg["beam_angle_mode"] = ba.attrib.get("BeamAngleMode")

    return cfg


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

def debug_scan_beamangles(evd_path):

    with open(evd_path, "rb") as f:
        data = f.read()

    print("\n=== DEBUG: SCANNING ALL <BeamAngles> TAGS ===")

    # Find all BeamAngles tags
    tags = list(re.finditer(br'<BeamAngles[^>]*>', data))
    print(f"Found {len(tags)} BeamAngles tags total")

    # Find first PingData
    ping_idx = data.find(b"<PingData")
    print(f"First <PingData> at offset {ping_idx}")

    for i, m in enumerate(tags):
        start = m.start()
        end = m.end()
        tag_text = m.group(0).decode("utf-8", errors="ignore")

        print(f"\n--- BeamAngles #{i+1} ---")
        print(f"Offset: {start}")
        print(f"Tag: {tag_text}")

        # Check if before or after PingData
        if start < ping_idx:
            print("Location: BEFORE first PingData (candidate REAL block)")
        else:
            print("Location: AFTER first PingData (likely inside PingData)")

        # Find closing tag
        close = data.find(b"</BeamAngles>", end)
        print(f"Closing tag at: {close}")

        if close == -1:
            print("WARNING: No closing tag found")
            continue

        payload_len = close - end
        print(f"Payload length: {payload_len} bytes")

        # Print first 32 bytes of payload (hex)
        payload = data[end:close]
        print("Payload (first 32 bytes hex):", payload[:32].hex())

# ============================================================
# 8. ACMETA METADATA
# ============================================================

def build_acmeta_metadata(packets, evd_path):
    # --- Time coverage ---
    t_start, t_end, duration = extract_time_bounds(packets)

    # --- Navigation ---
    nav = build_navigation_series(packets)
    times = [t for (t, _, _) in nav]
    lats  = [lat for (_, lat, _) in nav]
    lons  = [lon for (_, _, lon) in nav]

    # --- Sonar (from MultibeamPing) ---
    sounder = extract_sounder_config(packets)

    # --- PingData summary ---
    ping_summary = summarize_pingdata(evd_path)

    # --- Beam metadata ---
    beam_info = summarize_beamangles(evd_path)   # only beam_count
    spreads   = collect_beam_spreads_from_multibeam_ping(packets)

    acmeta = {
        "source": {
            "file_type": "Seapix_EVD",
            "original_file": None,
        },

        "time_coverage": {
            "start": t_start.isoformat() if t_start else None,
            "end": t_end.isoformat() if t_end else None,
            "duration_seconds": duration,
        },

        "platform": {
            "platform_type": "vessel",
        },

        "sonar": {
            "sonar_model": sounder.get("sonar_model"),
            "sound_speed": sounder.get("sound_speed"),
            "absorption": sounder.get("absorption"),
        },

        "beam": {
            "beam_count": beam_info["beam_count"],
            "beam_spread": spreads if spreads else None,   # e.g. [10, 60]
            "beam_angle_mode": "Variable",                 # from MultibeamPing
            "beam_span_min": None,                         # no angle table in this EVD
            "beam_span_max": None,
        },

        "ping": {
            "ping_count": ping_summary["ping_count"],
            "time_start": t_start.isoformat() if t_start else None,
            "time_end": t_end.isoformat() if t_end else None,
            "duration_seconds": duration,
            "sample_count_min": ping_summary["sample_count_min"],
            "sample_count_max": ping_summary["sample_count_max"],
            "start_range_min": ping_summary["start_range_min"],
            "stop_range_max": ping_summary["stop_range_max"],
        },

        "navigation": {
            "nav_count": len(nav),
            "time_min": min(times).isoformat() if times else None,
            "time_max": max(times).isoformat() if times else None,
            "latitude_min": min(lats) if lats else None,
            "latitude_max": max(lats) if lats else None,
            "longitude_min": min(lons) if lons else None,
            "longitude_max": max(lons) if lons else None,
        },

        "packet_counts": summarize_packet_counts(packets),
    }

    # Debug XML (sanitized)
    acmeta["debug_xml"] = extract_initial_xml_region(evd_path)

    mb = extract_multibeam_ping_info(packets)

    acmeta["sonar"]["sound_speed"] = mb.get("sound_speed")
    acmeta["sonar"]["absorption"] = mb.get("absorption")

    acmeta["beam"]["beam_count"] = mb.get("beam_count")
    acmeta["beam"]["beam_spread"] = mb.get("beam_spread")
    acmeta["beam"]["beam_angle_mode"] = mb.get("beam_angle_mode")

    return acmeta


## 4. Export AcMeta to CSV for evaluation
# For quick eval, a simple key,value CSV
def flatten_acmeta_for_csv(acmeta):
    """
    Flatten nested AcMeta dict into (key, value) pairs.
    Arrays are JSON-encoded strings.
    """
    rows = []

    def _add(prefix, value):
        rows.append((prefix, value))

    def _walk(prefix, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _walk(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(obj, list):
            import json
            _add(prefix, json.dumps(obj))
        else:
            _add(prefix, obj)

    _walk("", acmeta)
    return rows


def write_acmeta_csv(acmeta, csv_path):
    rows = flatten_acmeta_for_csv(acmeta)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "value"])
        for k, v in rows:
            w.writerow([k, v])

def summarize_packet_counts(packets):
    """
    Return a simple dict of packet type → count.
    This wraps the existing count_packet_types() logic.
    """
    from collections import Counter
    return dict(Counter(p["type"] for p in packets))

# ============================================================
# 9. MAIN
# ============================================================

def main():
    print("DEBUG: main() is running")

    # evd_path = r"D:\Cutter\0-PROJECTS\EVD-TestData\EVD-x01.evd"
    evd_path = r"D:\Cutter\0-PROJECTS\EVD-TestData\1018_0008.evd"

    print(f"Reading XML packets from:\n  {evd_path}\n")

    packets, diag = collect_packets(evd_path)
    print("DEBUG: collect_packets diag:", diag)
    print("DEBUG: first 5 packet types:", [p["type"] for p in packets[:5]])
    print("DEBUG: unique packet types:", sorted(set(p["type"] for p in packets)))
    print("DEBUG: count MultibeamPing:", sum(1 for p in packets if p["type"] == "MultibeamPing"))

    #
    if( OPTIONS_DEBUG_BEAMANGLES ):
        debug_scan_beamangles(evd_path)

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
    # acmeta = build_acmeta_metadata(packets, sonarnc_meta)
    acmeta = build_acmeta_metadata(packets, evd_path)

    if( OPTIONS_VERBOSE ):
        # Print to terminal
        print("AcMeta metadata (text):")
        print(json.dumps(acmeta, indent=2))

    # Write to json
    json_path = os.path.splitext(evd_path)[0] + "_acmeta_v01-7.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(acmeta, f, indent=2)

    # write to csv
    csv_path = evd_path.replace(".evd", "_acmeta_v01-7.csv")
    write_acmeta_csv(acmeta, csv_path)

    print(f"\nAcMeta JSON written to:\n  {json_path}")
    print(f"AcMeta CSV written to:\n  {csv_path}")

    # print(f"\nAcMeta JSON written to:\n  {out_json}")



if __name__ == "__main__":
    main()