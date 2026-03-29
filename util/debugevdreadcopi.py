evd_path = r"D:\Cutter\0-PROJECTS\EVD-TestData\EVD-x01.evd"

# NBYTES = 1024
# with open(evd_path, "rb") as f:
#     print(f.read(NBYTES))

NBYTES = 15000
with open(evd_path, "rb") as f:
    print(f.read(NBYTES))