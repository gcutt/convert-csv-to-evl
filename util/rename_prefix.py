"""
rename_file_prefixes.py**How to use it**
### **Dry run first (recommended):**
```
python rename_prefix.py ./myfiles pltf-instr-workflow svf-instr-workflow --dry-run
```
This prints what *would* be renamed.

### **Then actually rename:**
```
python rename_prefix.py ./myfiles pltf-instr-workflow svf-instr-workflow
```
"""

#!/usr/bin/env python3
import os
import argparse

def rename_prefix(directory, old_prefix, new_prefix, dry_run=False):
    """
    Renames files in `directory` whose names start with `old_prefix`,
    replacing that prefix with `new_prefix`.
    """

    for fname in os.listdir(directory):
        if fname.startswith(old_prefix):
            new_name = new_prefix + fname[len(old_prefix):]
            old_path = os.path.join(directory, fname)
            new_path = os.path.join(directory, new_name)

            if dry_run:
                print(f"[DRY RUN] {fname}  →  {new_name}")
            else:
                print(f"Renaming: {fname}  →  {new_name}")
                os.rename(old_path, new_path)

def main():
    parser = argparse.ArgumentParser(description="Rename file prefixes in a directory.")
    parser.add_argument("directory", help="Directory containing files to rename")
    parser.add_argument("old_prefix", help="Prefix to replace")
    parser.add_argument("new_prefix", help="New prefix")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be renamed without changing anything")

    args = parser.parse_args()

    rename_prefix(args.directory, args.old_prefix, args.new_prefix, dry_run=args.dry_run)

if __name__ == "__main__":
    main()