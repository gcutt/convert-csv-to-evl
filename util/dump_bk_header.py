## **Python script: dump first part of SDOC.BK**

# dump_bk_header.py

def dump_header(path, nbytes=256):
    with open(path, "rb") as f:
        data = f.read(nbytes)

    # Hex view
    hex_view = " ".join(f"{b:02X}" for b in data)

    # ASCII view (replace non-printable with '.')
    ascii_view = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)

    print(f"File: {path}")
    print(f"Bytes read: {len(data)}\n")
    print("HEX:")
    print(hex_view)
    print("\nASCII:")
    print(ascii_view)


if __name__ == "__main__":
    # Change this to your actual file path
    # dump_header("SDOC.BK", nbytes=512)

    BKFILE = r"SDOC.BK"
    dump_header(BKFILE, nbytes=512)


# ## **How to use it**
# 1. Save the script as `dump_bk_header.py`
# 2. Put it in the same folder as your `SDOC.BK` file
# 3. Run:
#
# python dump_bk_header.py


