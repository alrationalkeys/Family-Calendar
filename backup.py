"""
Simple SQLite backup. Run on a schedule (cron / systemd timer) so a dead SD card
doesn't wipe the family calendar.

    python backup.py            # writes backups/familyhub-YYYYMMDD-HHMM.db
    python backup.py --keep 14  # also prune backups older than the newest 14

Uses SQLite's online backup API so it's safe while the app is running.
"""
import argparse
import datetime as dt
import os
import sqlite3
import glob

DB = os.getenv("FAMILYHUB_DB", "familyhub.db")
BACKUP_DIR = "backups"


def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    dest = os.path.join(BACKUP_DIR, f"familyhub-{stamp}.db")
    src = sqlite3.connect(DB)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close(); dst.close()
    print(f"Backed up -> {dest}")
    return dest


def prune(keep):
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, "familyhub-*.db")))
    for f in files[:-keep] if keep < len(files) else []:
        os.remove(f); print(f"Pruned {f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=0, help="keep N most recent backups")
    a = ap.parse_args()
    backup()
    if a.keep:
        prune(a.keep)
