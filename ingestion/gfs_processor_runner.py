#!/usr/bin/env python3
"""Auto-discover GFS GRIB2 files and run gfs_processor on them."""
import glob
import os
import re
import subprocess
import sys
from datetime import date, timedelta

raw_dir = "/data/raw/gfs"
files = sorted(glob.glob(os.path.join(raw_dir, "*.grb2")))
if not files:
    print(f"No GRIB2 files found in {raw_dir}", file=sys.stderr)
    sys.exit(1)

dates = set()
for f in files:
    m = re.search(r"gfs_(\d{8})_", os.path.basename(f))
    if m:
        dates.add(m.group(1))

if dates:
    latest = max(dates)
else:
    latest = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

end_date = f"{latest[:4]}-{latest[4:6]}-{latest[6:]}"
args = ["python", "gfs_processor.py", "--files"] + files + ["--end-date", end_date]

print(f"Processing {len(files)} files, end_date={end_date}")
subprocess.run(args, check=True)
