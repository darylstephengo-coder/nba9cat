"""Copy a new version of the program into your existing folder, keeping your own data.

You never overwrite your rankings, league settings, ADP snapshots or notes: this script
only replaces program files (the app, the engine, the fetch scripts and the guides).

How to use:
  1. Download the new nba9cat.zip and unzip it somewhere temporary, e.g. your Downloads folder.
  2. Open a terminal in that NEW folder.
  3. Run:   python update.py "C:\\path\\to\\your\\existing\\nba9cat"
     (Mac:  python3 update.py /path/to/your/existing/nba9cat)

It prints exactly what it changed, and backs up anything it replaces into a dated folder
inside your existing copy, so nothing is lost even if something goes wrong.
"""
import datetime as dt
import filecmp
import shutil
import sys
from pathlib import Path

# Program files — safe to replace.
PROGRAM_FILES = ["app.py", "config.py", "requirements.txt", "requirements-local.txt",
                 "run.bat", "setup.bat",
                 "update.py", "VERSION", "README.md", "START_HERE.md",
                 "DEPLOY_TO_PHONE.md", "REFRESH_ADP_AND_XRANK.md", "YAHOO_EXTENSION_PROMPT.md"]
PROGRAM_DIRS = ["engine", "yahoo", ".streamlit"]
PROGRAM_IN_DATA = ["fetch_stats.py", "schedule.py", "injuries.py", "import_yahoo.py", "make_sample.py"]

# Your files — never touched.
YOURS = ["my_rankings.csv", "leagues.json", "no_stats.csv", "overrides.csv",
         "yahoo_players.csv", "yahoo_adp.csv", "yahoo_xrank.csv",
         "season_*.csv", "schedule.csv", "injuries.csv", "adp/"]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    new = Path(__file__).resolve().parent
    old = Path(sys.argv[1]).expanduser().resolve()
    if not (old / "app.py").exists():
        sys.exit(f"That doesn't look like an nba9cat folder: {old}")
    if old == new:
        sys.exit("Those are the same folder. Point me at your existing copy, not this one.")

    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    backup = old / "_backup" / stamp
    changed, added, same = [], [], 0

    def copy(src: Path, dst: Path, label: str):
        nonlocal same
        if not src.exists():
            return
        if dst.exists():
            if filecmp.cmp(src, dst, shallow=False):
                same += 1
                return
            backup_path = backup / label
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup_path)
            changed.append(label)
        else:
            added.append(label)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for name in PROGRAM_FILES:
        copy(new / name, old / name, name)
    for d in PROGRAM_DIRS:
        for src in sorted((new / d).rglob("*.py")) + sorted((new / d).rglob("*.toml")):
            copy(src, old / src.relative_to(new), str(src.relative_to(new)))
    for name in PROGRAM_IN_DATA:
        copy(new / "data" / name, old / "data" / name, f"data/{name}")

    print(f"\nUpdated: {old}")
    print(f"  {len(added)} new file(s), {len(changed)} replaced, {same} already up to date")
    for f in added:
        print(f"    + {f}")
    for f in changed:
        print(f"    ~ {f}")
    if changed:
        print(f"\n  Old versions backed up to: {backup}")
    print("\nYour data was not touched:")
    print("    " + ", ".join(YOURS))
    print("\nNow start the app from your folder: double-click run.bat, "
          "or run  python -m streamlit run app.py")


if __name__ == "__main__":
    main()
