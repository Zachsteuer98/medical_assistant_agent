"""Assemble the Hugging Face Space bundle in build/space (whitelist copy, then verify).

    cd backend && uv run python ../deploy/huggingface/stage.py --build-index   # real deploy
    python deploy/huggingface/stage.py --empty-index                           # CI image check

The bundle is the Space repo root: Dockerfile, README.md (Space front matter), the backend
runtime code, the frontend sources (built inside the image) and the prebuilt vector index.
Only the public corpus index is allowed in; the licensed Merck data must never reach a Space
(docs/adr/0001, docs/adr/0004).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HF_DIR = Path(__file__).resolve().parent
REPO_ROOT = HF_DIR.parents[1]
BACKEND = REPO_ROOT / "backend"
FRONTEND = REPO_ROOT / "frontend"
DEFAULT_OUT = REPO_ROOT / "build" / "space"

PUBLIC_CORPUS = "public"
EXPECTED_COLLECTION = "public_rec"
INDEX_DIR_NAME = "index"

BACKEND_FILES = ("pyproject.toml", "uv.lock")
BACKEND_DIRS = ("app",)
BACKEND_SKIP = shutil.ignore_patterns("__pycache__", "*.pyc")
FRONTEND_SKIP = shutil.ignore_patterns(
    "node_modules", "dist", "Dockerfile", "nginx.conf", ".dockerignore", ".gitignore"
)

FORBIDDEN_WORDS = ("merck",)
FORBIDDEN_ENV_PREFIX = ".env"  # .env, .env.local, .env.production, ...
ARTIFACT_DIRS = {".venv", "node_modules", "dist", "__pycache__"}
FORBIDDEN_SUFFIXES = {".pdf"}
SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
MAX_SCANNED_BYTES = 2_000_000

INDEX_INSPECT_SCRIPT = (
    "import json, sys, chromadb;"
    "c = chromadb.PersistentClient(sys.argv[1], settings=chromadb.Settings("
    "anonymized_telemetry=False));"
    "print(json.dumps({x.name: x.count() for x in c.list_collections()}))"
)


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=BACKEND, env=env, check=True)


def build_index(index_dir: Path) -> None:
    """Download the pinned PDFs and ingest them into a fresh, isolated store."""
    env = {**os.environ, "CHROMA_DIR": str(index_dir)}
    for module in ("app.download", "app.ingest"):
        run(["uv", "run", "python", "-m", module, "--corpus", PUBLIC_CORPUS], env=env)


def index_collections(index_dir: Path) -> dict[str, int]:
    cmd = ["uv", "run", "python", "-c", INDEX_INSPECT_SCRIPT, str(index_dir)]
    out = subprocess.run(cmd, cwd=BACKEND, check=True, text=True, capture_output=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def verify_index(index_dir: Path) -> int:
    collections = index_collections(index_dir)
    if set(collections) != {EXPECTED_COLLECTION} or collections[EXPECTED_COLLECTION] <= 0:
        sys.exit(f"index must hold only a non-empty {EXPECTED_COLLECTION!r}, found {collections}")
    return collections[EXPECTED_COLLECTION]


def verify_tree(out: Path) -> None:
    """Refuse to ship licensed data, PDFs, env files, install folders or anything key-shaped."""
    index_root = out / INDEX_DIR_NAME
    problems: list[str] = []
    for root, dirs, files in os.walk(out):
        root_path = Path(root)
        leftovers = [d for d in dirs if d in ARTIFACT_DIRS]
        for name in leftovers:
            rel = (root_path / name).relative_to(out)
            problems.append(f"install/build folder (re-run stage.py on a clean tree): {rel}")
        dirs[:] = [d for d in dirs if d not in ARTIFACT_DIRS]
        for filename in sorted(files):
            path = root_path / filename
            rel = path.relative_to(out)
            if (
                filename.startswith(FORBIDDEN_ENV_PREFIX)
                or path.suffix.lower() in FORBIDDEN_SUFFIXES
            ):
                problems.append(f"forbidden file: {rel}")
            if any(word in str(rel).lower() for word in FORBIDDEN_WORDS):
                problems.append(f"forbidden name: {rel}")
            if index_root in path.parents or path.stat().st_size > MAX_SCANNED_BYTES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if SECRET_PATTERN.search(text):
                problems.append(f"key-shaped string in: {rel}")
    if problems:
        sys.exit("refusing to stage:\n  " + "\n  ".join(problems))


def copy_bundle(out: Path) -> None:
    out.mkdir(parents=True)
    shutil.copy(HF_DIR / "Dockerfile", out / "Dockerfile")
    shutil.copy(HF_DIR / "SPACE_README.md", out / "README.md")
    backend_out = out / "backend"
    backend_out.mkdir()
    for name in BACKEND_FILES:
        shutil.copy(BACKEND / name, backend_out / name)
    for name in BACKEND_DIRS:
        shutil.copytree(BACKEND / name, backend_out / name, ignore=BACKEND_SKIP)
    shutil.copytree(FRONTEND, out / "frontend", ignore=FRONTEND_SKIP)


def total_size_mb(root: Path) -> float:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) / 1e6


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--build-index", action="store_true", help="download PDFs and ingest (~10 min)"
    )
    group.add_argument(
        "--empty-index", action="store_true", help="placeholder index (CI image build)"
    )
    args = parser.parse_args()

    out: Path = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    copy_bundle(out)
    index_dir = out / INDEX_DIR_NAME
    if args.empty_index:
        index_dir.mkdir()
        (index_dir / ".keep").touch()
        chunks = 0
    else:
        build_index(index_dir)
        chunks = verify_index(index_dir)
    verify_tree(out)
    print(f"staged {out} ({total_size_mb(out):.1f} MB, {chunks} indexed chunks)")


if __name__ == "__main__":
    main()
