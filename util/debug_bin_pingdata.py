import re
import struct

evd_path = r"D:\Cutter\0-PROJECTS\EVD-TestData\1018_0008.evd"


with open(evd_path, "rb") as f:
    data = f.read()

# Find first PingData tag
m = re.search(br'<PingData[^>]*>', data)
if not m:
    print("No PingData found")
else:
    tag_end = m.end()

    # Dump first 256 bytes after the tag
    header = data[tag_end:tag_end+256]

    print("PingData header bytes:")
    print(header)