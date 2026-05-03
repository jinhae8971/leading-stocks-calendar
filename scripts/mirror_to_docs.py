"""
Mirror data/ to docs/data/ for GitHub Pages deployment.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data"
DST = ROOT / "docs" / "data"


def main():
    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True, exist_ok=True)

    for sub in ["daily", "monthly", "weekly"]:
        src_sub = SRC / sub
        dst_sub = DST / sub
        if src_sub.exists():
            shutil.copytree(src_sub, dst_sub)
            print(f"Mirrored {sub}: {sum(1 for _ in dst_sub.rglob('*.json'))} files")


if __name__ == "__main__":
    main()
