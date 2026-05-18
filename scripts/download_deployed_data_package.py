"""Download the deployed GitHub Pages runtime data package into data/derived."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_PACKAGES_URL = (
    "https://deinspanjer.github.io/bcf-visualization/data/packages.json"
)
DEFAULT_OUTPUT = Path("data/derived")


def load_json_url(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "bcf-visualization setup"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def package_base_url(packages_url: str, package_index: dict) -> str:
    packages = package_index.get("packages")
    default_package_id = package_index.get("default_package_id")
    if not isinstance(packages, list) or not packages:
        raise RuntimeError("deployed packages index has no packages")
    package = next(
        (
            item for item in packages
            if isinstance(item, dict) and item.get("package_id") == default_package_id
        ),
        packages[0],
    )
    path = package.get("path")
    if not isinstance(path, str) or not path:
        raise RuntimeError("deployed package entry has no path")
    pages_root = urllib.parse.urljoin(packages_url, "../")
    return urllib.parse.urljoin(pages_root, path.rstrip("/") + "/")


def download_package(*, packages_url: str, output_dir: Path, force: bool = False) -> dict:
    if (output_dir / "visualization_facts.json").exists() and not force:
        print(f"{output_dir} already hydrated; skipping download")
        return {}

    index = load_json_url(packages_url)
    base_url = package_base_url(packages_url, index)
    manifest = load_json_url(urllib.parse.urljoin(base_url, "data_package.json"))
    files = manifest.get("files")
    if not isinstance(files, dict) or "visualization_facts" not in files:
        raise RuntimeError("deployed package manifest does not contain runtime files")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data_package.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    for meta in files.values():
        path = meta.get("path") if isinstance(meta, dict) else None
        if not isinstance(path, str) or not path:
            raise RuntimeError("deployed package manifest has invalid file metadata")
        source_url = urllib.parse.urljoin(base_url, path)
        target = output_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(source_url, headers={"User-Agent": "bcf-visualization setup"})
        with urllib.request.urlopen(request, timeout=120) as response:
            target.write_bytes(response.read())
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages-url", default=DEFAULT_PACKAGES_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        manifest = download_package(
            packages_url=args.packages_url,
            output_dir=args.output_dir,
            force=args.force,
        )
    except Exception as exc:
        print(f"failed to download deployed data package: {exc}", file=sys.stderr)
        return 1

    package_id = manifest.get("package_id") if manifest else "existing data"
    print(f"hydrated {args.output_dir} from {package_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
