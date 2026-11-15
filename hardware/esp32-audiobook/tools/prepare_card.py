"""Convert chapter-split audiobook archives into a CYD microSD library."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile


AUDIO = {".m4b", ".m4a", ".mp3", ".aac", ".flac", ".wav"}
CHAPTER = re.compile(r"^(.*?)\s+-\s+(\d+)\s+-\s+(.*)$")
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def clean(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return INVALID.sub("_", text).strip(" .") or "Untitled"


def collect(sources, stack, include):
    tracks = {}
    for source in sources:
        paths = []
        archive = None
        if source.suffix.lower() == ".zip" and source.is_file():
            archive = stack.enter_context(zipfile.ZipFile(source))
            paths = [(Path(entry.filename), entry) for entry in archive.infolist()
                     if not entry.is_dir()]
        elif source.is_dir():
            paths = [(file, file) for file in source.rglob("*") if file.is_file()]
        elif source.is_file():
            paths = [(source, source)]
        else:
            raise ValueError(f"Cannot find {source}")
        for file, entry in paths:
            if file.suffix.lower() not in AUDIO:
                continue
            if file.name.startswith(".") or "__MACOSX" in file.parts:
                continue
            if include and include.casefold() not in file.stem.casefold():
                continue
            key = (file.stem.casefold(), file.suffix.lower())
            existing = tracks.get(key)
            if existing:
                previous, _ = existing
                if archive and isinstance(previous, zipfile.ZipInfo) and (
                    previous.CRC, previous.file_size
                ) == (entry.CRC, entry.file_size):
                    continue
                raise ValueError(f"Duplicate chapter name: {file.name}")
            tracks[key] = (entry, archive)
    return tracks


def chapter_names(tracks):
    pattern_keys = []
    for stem, suffix in tracks:
        entry, archive = tracks[stem, suffix]
        name = Path(entry.filename if archive else entry).stem
        match = CHAPTER.fullmatch(name)
        order = (match[1].casefold(), int(match[2]), name.casefold()) if match else (
            name.casefold(), 0, name.casefold())
        title = f"{int(match[2]):03d} - {match[3]}" if match else name
        pattern_keys.append((order, title, entry, archive))
    return sorted(pattern_keys, key=lambda item: item[0])


def convert(args):
    with ExitStack() as stack:
        tracks = chapter_names(collect(args.sources, stack, args.include))
        if not tracks:
            raise ValueError("No audio files found")
        if args.list:
            for _, title, _, _ in tracks:
                print(clean(title))
            print(f"{len(tracks)} chapters")
            return
        ffmpeg = shutil.which(args.ffmpeg)
        if ffmpeg is None:
            raise ValueError("FFmpeg is required. Put it on PATH or pass --ffmpeg.")
        card = args.card / "Audiobooks"
        card.mkdir(parents=True, exist_ok=True)
        plan = []
        for index, (_, title, entry, archive) in enumerate(tracks, 1):
            if args.limit and index > args.limit:
                break
            output = card / f"{index:04d} {clean(title)[:110]}.pcm"
            plan.append((output, entry, archive))
        # Refuse to mix a new chapter ordering with a previously prepared library.
        unexpected = {file.name for file in card.glob("*.pcm")} - {f.name for f, _, _ in plan}
        if unexpected:
            raise ValueError(f"{card} contains chapters outside this conversion plan")
        if not args.resume and any(out.exists() for out, _, _ in plan):
            raise ValueError(f"{card} already contains output. Use --resume to skip existing files.")
        with tempfile.TemporaryDirectory() as temporary:
            for index, (out, entry, archive) in enumerate(plan, 1):
                if out.exists():
                    if out.stat().st_size < 2 or out.stat().st_size % 2:
                        raise ValueError(f"Invalid existing chapter: {out}")
                    continue
                source = entry
                if archive:
                    source = Path(temporary) / ("chapter" + Path(entry.filename).suffix)
                    with archive.open(entry) as packed, source.open("wb") as extracted:
                        shutil.copyfileobj(packed, extracted)
                pending = out.with_suffix(".part")
                print(f"[{index}/{len(plan)}] {out.name}", flush=True)
                try:
                    subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                                    "-i", str(source), "-map", "0:a:0", "-ac", "1", "-ar", "22050",
                                    "-c:a", "pcm_s16le", "-f", "s16le", str(pending)], check=True)
                    if pending.stat().st_size < 2 or pending.stat().st_size % 2:
                        raise ValueError(f"Invalid output for {out.name}")
                    pending.replace(out)
                finally:
                    pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path, help="ZIP archives, files, or folders")
    parser.add_argument("--include", help="only include filenames containing this text")
    parser.add_argument("--card", type=Path, help="microSD root or staging folder")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable")
    parser.add_argument("--list", action="store_true", help="list the chapters in playback order")
    parser.add_argument("--limit", type=int, help="convert only the first N chapters")
    parser.add_argument("--resume", action="store_true", help="skip finished files from the same inputs")
    args = parser.parse_args()
    if not args.list and args.card is None:
        parser.error("--card is required when converting")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        convert(args)
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
