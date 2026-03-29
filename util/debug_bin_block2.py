import re

evd_path = r"D:\Cutter\0-PROJECTS\EVD-TestData\1018_0008.evd"

with open(evd_path, "rb") as f:
    data = f.read()

# Find BeamAngles start tag
m = re.search(br'<BeamAngles[^>]*BeamCount="(\d+)"[^>]*>', data)
if not m:
    print("No BeamAngles found")
else:
    tag_end = m.end()

    # Extract BeamCount
    import re as _re
    tag_text = m.group(0).decode("utf-8", errors="ignore")
    bc = int(_re.search(r'BeamCount="(\d+)"', tag_text).group(1))

    # Skip binary beam angles
    beam_bytes = bc * 4
    after_beam = tag_end + beam_bytes

    print("Binary block starts at:", after_beam)

    # Dump first 512 bytes of the next block
    chunk = data[after_beam:after_beam+512]
    print(chunk)