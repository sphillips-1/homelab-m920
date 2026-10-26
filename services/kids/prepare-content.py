"""Fetch the pinned offline archive atomically; never replace family content."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(os.environ.get("KIDS_CONTENT_ROOT", "/content"))
NAME = "vikidia_en_all_maxi_2026-09.zim"
SHA256 = "16728e6be34081f6c627b3cbf2c36ff31823defb0f30b68fab146b5ca68e591e"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    encyclopedia = ROOT / "encyclopedia"
    arcade = ROOT / "arcade"
    encyclopedia.mkdir(parents=True, exist_ok=True)
    (arcade / "roms").mkdir(parents=True, exist_ok=True)
    (arcade / "emulator").mkdir(parents=True, exist_ok=True)
    catalog = arcade / "catalog.json"
    if not catalog.exists():
        with catalog.open("x") as output:
            json.dump([], output)
    target = encyclopedia / NAME
    if target.exists():
        if digest(target) != SHA256:
            raise SystemExit("Existing encyclopedia checksum differs; inspect it before replacing.")
        print("Encyclopedia already verified.")
        return
    temporary = target.with_suffix(".zim.part")
    url = "https://download.kiwix.org/zim/vikidia/" + NAME
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if digest(temporary) != SHA256:
            raise SystemExit("Downloaded encyclopedia checksum mismatch.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print("Encyclopedia downloaded and verified.")


if __name__ == "__main__":
    main()
