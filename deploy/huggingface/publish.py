"""Upload the staged bundle (build/space) to a Hugging Face Docker Space.

    uv run --no-project --with huggingface_hub==2.3.0 python deploy/huggingface/publish.py \
        --repo YOUR_USER/medical-assistant-agent [--dry-run]

Needs a write token in HF_TOKEN (never commit it). Set OPENAI_API_KEY as a Space *secret* in
the Space settings; this script never handles it.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_FOLDER = Path(__file__).resolve().parents[2] / "build" / "space"


def git_short_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], check=True, text=True, capture_output=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def describe(folder: Path) -> None:
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in files)
    print(f"{len(files)} files, {total / 1e6:.1f} MB in {folder}")
    for path in sorted(files, key=lambda p: p.stat().st_size, reverse=True)[:5]:
        print(f"  {path.stat().st_size / 1e6:8.1f} MB  {path.relative_to(folder)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--repo", required=True, help="USER/NAME of the Space")
    parser.add_argument("--folder", type=Path, default=DEFAULT_FOLDER)
    parser.add_argument("--dry-run", action="store_true", help="list what would be uploaded")
    args = parser.parse_args()

    if not args.folder.is_dir():
        sys.exit(f"{args.folder} does not exist; run stage.py first")
    describe(args.folder)
    if args.dry_run:
        return

    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN is not set (create a write token at huggingface.co/settings/tokens)")

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(args.repo, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    api.upload_folder(
        folder_path=str(args.folder),
        repo_id=args.repo,
        repo_type="space",
        commit_message=f"Deploy {git_short_sha()}",
        # Never upload local install/build folders if someone worked inside build/space.
        ignore_patterns=[
            ".venv/**",
            "**/node_modules/**",
            "**/dist/**",
            "**/__pycache__/**",
            "**/.env*",
        ],
    )
    print(f"Uploaded. Space: https://huggingface.co/spaces/{args.repo}")


if __name__ == "__main__":
    main()
