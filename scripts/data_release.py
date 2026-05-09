"""Build and manage versioned derived-data release bundles.

Top-level ``data/derived/*.json`` files are generated release data. This
script builds, validates, downloads, and stages the release artifacts
that hydrate local checkouts and GitHub Pages deployments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
DIST = ROOT / "dist" / "data-packages"

CONTRACT = "bcf-visualization-data"
CONTRACT_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
PACKAGE_PREFIX = "bcf-visualization"

RUNTIME_REQUIRED = ["chapter_facts"]
RUNTIME_OPTIONAL = ["constellation_wireframes", "roll_resolutions"]
PACKAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
DATA_RELEASE_RE = re.compile(
    r"^(?:data-v\d{8}\.\d+|bcf-visualization-data-v\d{8}\.\d+-ch\d+-[A-Za-z0-9_.-]+)$"
)


@dataclass(frozen=True)
class PackageOutputs:
    release_tag: str
    runtime_tar: Path
    dev_tar: Path
    checksums_path: Path


@dataclass(frozen=True)
class StoryFreshness:
    chapter_ordinal: int
    chapter_num: str
    chapter_title: str


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%d")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _top_level_json_files(source_dir: Path) -> list[Path]:
    return sorted(
        path for path in source_dir.glob("*.json")
        if path.name != "data_package.json"
    )


def _file_meta(source_dir: Path, path: Path) -> dict:
    doc = _read_json(path)
    rel = path.relative_to(source_dir).as_posix()
    return {
        "path": rel,
        "schema": path.stem,
        "schema_version": doc.get("schema_version"),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _safe_id_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    token = token.strip(".-")
    if not token:
        raise ValueError(f"could not build safe id token from {value!r}")
    return token


def _story_freshness(source_dir: Path) -> StoryFreshness:
    chapter_facts = _read_json(source_dir / "chapter_facts.json")
    chapters = chapter_facts.get("chapters") or []
    if not chapters:
        raise ValueError("chapter_facts.json has no chapters")
    last = chapters[-1]
    chapter_num = str(last.get("chapter_num") or "").strip()
    if not chapter_num:
        raise ValueError("latest chapter has no chapter_num")
    return StoryFreshness(
        chapter_ordinal=len(chapters),
        chapter_num=chapter_num,
        chapter_title=str(last.get("full_title") or chapter_num),
    )


def _version_slug(
    *,
    package_date: str,
    build_number: int,
    story: StoryFreshness,
) -> str:
    return (
        f"v{package_date}.{build_number}"
        f"-ch{story.chapter_ordinal}-{_safe_id_token(story.chapter_num)}"
    )


def _release_tag(*, package_date: str, build_number: int, story: StoryFreshness) -> str:
    return f"{PACKAGE_PREFIX}-data-{_version_slug(package_date=package_date, build_number=build_number, story=story)}"


def _package_id(
    *,
    package_kind: str,
    package_date: str,
    build_number: int,
    story: StoryFreshness,
) -> str:
    return f"{PACKAGE_PREFIX}-{package_kind}-{_version_slug(package_date=package_date, build_number=build_number, story=story)}"


def _version_label(*, package_date: str, build_number: int, story: StoryFreshness) -> str:
    return (
        f"BCF data {package_date}.{build_number}, "
        f"story ch {story.chapter_ordinal} / {story.chapter_num}"
    )


def _safe_manifest_path(path: str) -> Path:
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe manifest file path: {path}")
    return rel


def validate_package_dir(
    package_dir: Path,
    *,
    expected_bundle_class: str | None = None,
) -> dict:
    manifest = _read_json(package_dir / "data_package.json")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "unsupported manifest schema_version: "
            f"{manifest.get('schema_version')}"
        )
    if manifest.get("contract") != CONTRACT:
        raise ValueError(f"unsupported data package contract: {manifest.get('contract')}")
    if manifest.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(
            "unsupported data package contract_version: "
            f"{manifest.get('contract_version')}"
        )
    if expected_bundle_class and manifest.get("bundle_class") != expected_bundle_class:
        raise ValueError(
            f"expected {expected_bundle_class} bundle, "
            f"found {manifest.get('bundle_class')}"
        )
    package_id = manifest.get("package_id")
    if not isinstance(package_id, str) or not PACKAGE_ID_RE.match(package_id):
        raise ValueError(f"unsafe package id: {package_id}")

    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("data package manifest has no files")
    web = manifest.get("entrypoints", {}).get("web", {})
    required = web.get("required", [])
    if manifest.get("bundle_class") == "pages-runtime":
        missing = [name for name in RUNTIME_REQUIRED if name not in required or name not in files]
        if missing:
            raise ValueError(f"runtime package missing required files: {', '.join(missing)}")

    for name, meta in files.items():
        if not isinstance(meta, dict):
            raise ValueError(f"invalid file metadata for {name}")
        rel = _safe_manifest_path(str(meta.get("path", "")))
        path = package_dir / rel
        if not path.is_file():
            raise FileNotFoundError(f"package file is missing: {rel.as_posix()}")
        size = path.stat().st_size
        if meta.get("size_bytes") != size:
            raise ValueError(f"package file size mismatch: {rel.as_posix()}")
        digest = _sha256(path)
        if meta.get("sha256") != digest:
            raise ValueError(f"package file hash mismatch: {rel.as_posix()}")
        doc = _read_json(path)
        expected_schema_version = meta.get("schema_version")
        if expected_schema_version is None:
            continue
        if expected_schema_version != doc.get("schema_version"):
            raise ValueError(f"package file schema_version mismatch: {rel.as_posix()}")

    return manifest


def build_manifest(
    *,
    source_dir: Path = DERIVED,
    bundle_class: str,
    package_id: str,
    package_kind: str,
    package_date: str,
    build_number: int,
    release_tag: str,
    story: StoryFreshness,
    source_commit: str | None = None,
    generated_at: str | None = None,
) -> dict:
    if bundle_class not in {"pages-runtime", "dev-derived"}:
        raise ValueError(f"unsupported bundle class: {bundle_class}")
    if not PACKAGE_ID_RE.match(package_id):
        raise ValueError(f"unsafe package id: {package_id}")

    source_dir = source_dir.resolve()
    generated_at = generated_at or _utc_now()
    source_commit = source_commit or _git_commit()

    if bundle_class == "pages-runtime":
        file_names = [
            *(f"{name}.json" for name in RUNTIME_REQUIRED),
            *(f"{name}.json" for name in RUNTIME_OPTIONAL if (source_dir / f"{name}.json").exists()),
        ]
    else:
        file_names = [path.name for path in _top_level_json_files(source_dir)]

    files = {
        Path(name).stem: _file_meta(source_dir, source_dir / name)
        for name in file_names
    }
    missing_required = [
        name for name in RUNTIME_REQUIRED
        if name not in files and bundle_class == "pages-runtime"
    ]
    if missing_required:
        raise FileNotFoundError(f"missing runtime data files: {', '.join(missing_required)}")

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "package_id": package_id,
        "package_prefix": PACKAGE_PREFIX,
        "package_kind": package_kind,
        "package_date": package_date,
        "build_number": build_number,
        "generated_at": generated_at,
        "source_commit": source_commit,
        "release_tag": release_tag,
        "story_chapter_ordinal": story.chapter_ordinal,
        "story_chapter_num": story.chapter_num,
        "story_chapter_title": story.chapter_title,
        "version_label": _version_label(
            package_date=package_date,
            build_number=build_number,
            story=story,
        ),
        "contract": CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "bundle_class": bundle_class,
        "entrypoints": {
            "web": {
                "required": RUNTIME_REQUIRED if bundle_class == "pages-runtime" else [],
                "optional": [
                    name for name in RUNTIME_OPTIONAL
                    if name in files and bundle_class == "pages-runtime"
                ],
            }
        },
        "files": files,
    }


def write_current_runtime_manifest(
    *,
    source_dir: Path = DERIVED,
    package_date: str | None = None,
    build_number: int = 1,
    source_commit: str | None = None,
    generated_at: str | None = None,
) -> Path:
    package_date = package_date or _today()
    story = _story_freshness(source_dir)
    release_tag = _release_tag(
        package_date=package_date,
        build_number=build_number,
        story=story,
    )
    package_id = _package_id(
        package_kind="runtime",
        package_date=package_date,
        build_number=build_number,
        story=story,
    )
    manifest = build_manifest(
        source_dir=source_dir,
        bundle_class="pages-runtime",
        package_id=package_id,
        package_kind="runtime",
        package_date=package_date,
        build_number=build_number,
        release_tag=release_tag,
        story=story,
        source_commit=source_commit or "phase1-committed-derived-data",
        generated_at=generated_at,
    )
    out = source_dir / "data_package.json"
    _write_json(out, manifest)
    return out


def _copy_bundle_files(source_dir: Path, staging_dir: Path, manifest: dict) -> None:
    _write_json(staging_dir / "data_package.json", manifest)
    for meta in manifest["files"].values():
        src = source_dir / meta["path"]
        dst = staging_dir / meta["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _tar_directory(src_dir: Path, tar_path: Path) -> None:
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "w:gz") as tf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                tf.add(path, arcname=path.relative_to(src_dir).as_posix())


def _write_checksums(paths: Iterable[Path], out_path: Path) -> None:
    lines = [f"{_sha256(path)}  {path.name}" for path in paths]
    out_path.write_text("\n".join(lines) + "\n")


def build_packages(
    *,
    source_dir: Path = DERIVED,
    output_dir: Path = DIST,
    package_date: str | None = None,
    build_number: int = 1,
    source_commit: str | None = None,
    generated_at: str | None = None,
) -> PackageOutputs:
    package_date = package_date or _today()
    generated_at = generated_at or _utc_now()
    source_commit = source_commit or _git_commit()
    source_dir = source_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    story = _story_freshness(source_dir)
    release_tag = _release_tag(
        package_date=package_date,
        build_number=build_number,
        story=story,
    )
    runtime_id = _package_id(
        package_kind="runtime",
        package_date=package_date,
        build_number=build_number,
        story=story,
    )
    dev_id = _package_id(
        package_kind="data",
        package_date=package_date,
        build_number=build_number,
        story=story,
    )
    runtime_manifest = build_manifest(
        source_dir=source_dir,
        bundle_class="pages-runtime",
        package_id=runtime_id,
        package_kind="runtime",
        package_date=package_date,
        build_number=build_number,
        release_tag=release_tag,
        story=story,
        source_commit=source_commit,
        generated_at=generated_at,
    )
    dev_manifest = build_manifest(
        source_dir=source_dir,
        bundle_class="dev-derived",
        package_id=dev_id,
        package_kind="data",
        package_date=package_date,
        build_number=build_number,
        release_tag=release_tag,
        story=story,
        source_commit=source_commit,
        generated_at=generated_at,
    )

    runtime_tar = output_dir / f"{runtime_id}.tar.gz"
    dev_tar = output_dir / f"{dev_id}.tar.gz"
    checksums = output_dir / "SHA256SUMS"
    with tempfile.TemporaryDirectory(prefix="bcf-data-package-") as tmp:
        tmp_root = Path(tmp)
        runtime_stage = tmp_root / "runtime"
        dev_stage = tmp_root / "dev"
        _copy_bundle_files(source_dir, runtime_stage, runtime_manifest)
        _copy_bundle_files(source_dir, dev_stage, dev_manifest)
        _tar_directory(runtime_stage, runtime_tar)
        _tar_directory(dev_stage, dev_tar)
    _write_checksums([runtime_tar, dev_tar], checksums)
    return PackageOutputs(
        release_tag=release_tag,
        runtime_tar=runtime_tar,
        dev_tar=dev_tar,
        checksums_path=checksums,
    )


def build_release_tag(
    *,
    source_dir: Path = DERIVED,
    package_date: str | None = None,
    build_number: int = 1,
) -> str:
    package_date = package_date or _today()
    story = _story_freshness(source_dir.resolve())
    return _release_tag(
        package_date=package_date,
        build_number=build_number,
        story=story,
    )


def _safe_extract(tar_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"unsafe tar member type: {member.name}")
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"unsafe tar member path: {member.name}")
            target = (dest / member.name).resolve()
            if dest_resolved not in target.parents and target != dest_resolved:
                raise ValueError(f"unsafe tar member path: {member.name}")
        tf.extractall(dest)


def prepare_pages(
    *,
    runtime_tars: list[Path],
    site_dir: Path,
    default_package_id: str | None = None,
    max_site_mb: int = 900,
) -> Path:
    if not runtime_tars:
        raise ValueError("at least one runtime tar is required")
    data_dir = site_dir / "data"
    packages_dir = data_dir / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)

    packages: list[dict] = []
    for tar_path in runtime_tars:
        with tempfile.TemporaryDirectory(prefix="bcf-pages-package-") as tmp:
            tmp_dir = Path(tmp)
            _safe_extract(tar_path, tmp_dir)
            manifest = validate_package_dir(tmp_dir, expected_bundle_class="pages-runtime")
            package_id = manifest["package_id"]
            package_dir = packages_dir / package_id
            if package_dir.exists():
                shutil.rmtree(package_dir)
            shutil.copytree(tmp_dir, package_dir)
            packages.append({
                "package_id": package_id,
                "package_prefix": manifest.get("package_prefix"),
                "package_kind": manifest.get("package_kind"),
                "package_date": manifest.get("package_date"),
                "build_number": manifest.get("build_number"),
                "bundle_class": manifest["bundle_class"],
                "contract_version": manifest["contract_version"],
                "generated_at": manifest["generated_at"],
                "source_commit": manifest["source_commit"],
                "release_tag": manifest.get("release_tag"),
                "story_chapter_ordinal": manifest.get("story_chapter_ordinal"),
                "story_chapter_num": manifest.get("story_chapter_num"),
                "story_chapter_title": manifest.get("story_chapter_title"),
                "version_label": manifest.get("version_label", package_id),
                "path": f"data/packages/{package_id}",
            })

    default_package_id = default_package_id or packages[0]["package_id"]
    default_package = packages_dir / default_package_id
    if not default_package.exists():
        raise ValueError(f"default package was not provided: {default_package_id}")

    for mirror in (data_dir / "default", data_dir / "derived"):
        if mirror.exists():
            shutil.rmtree(mirror)
        shutil.copytree(default_package, mirror)

    index = {
        "schema_version": 1,
        "default_package_id": default_package_id,
        "packages": packages,
    }
    out = data_dir / "packages.json"
    _write_json(out, index)

    size_bytes = sum(path.stat().st_size for path in site_dir.rglob("*") if path.is_file())
    max_bytes = max_site_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise RuntimeError(
            f"Pages artifact is {size_bytes / 1024 / 1024:.1f} MiB, "
            f"over the {max_site_mb} MiB budget"
        )
    return out


def publish_release(*, tag: str, assets: list[Path], title: str | None, draft: bool) -> None:
    cmd = ["gh", "release", "create", tag, *[str(path) for path in assets]]
    cmd.extend(["--title", title or tag])
    cmd.extend(["--notes", f"Versioned BCF derived data bundle {tag}."])
    if draft:
        cmd.append("--draft")
    subprocess.run(cmd, cwd=ROOT, check=True)


def download_dev_bundle(*, tag: str, asset: str, output_dir: Path = DERIVED) -> None:
    with tempfile.TemporaryDirectory(prefix="bcf-dev-derived-") as tmp:
        tmp_dir = Path(tmp)
        subprocess.run(
            ["gh", "release", "download", tag, "--pattern", asset, "--dir", str(tmp_dir)],
            cwd=ROOT,
            check=True,
        )
        matches = list(tmp_dir.glob(asset))
        if not matches:
            raise FileNotFoundError(f"asset was not downloaded: {asset}")
        with tempfile.TemporaryDirectory(prefix="bcf-dev-derived-extract-") as extract_tmp:
            extract_dir = Path(extract_tmp)
            _safe_extract(matches[0], extract_dir)
            validate_package_dir(extract_dir, expected_bundle_class="dev-derived")
            for path in extract_dir.iterdir():
                dest = output_dir / path.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                if path.is_dir():
                    shutil.copytree(path, dest)
                else:
                    shutil.copy2(path, dest)


def cleanup_releases(*, keep_tags: set[str], limit: int, yes: bool) -> list[str]:
    raw = subprocess.check_output(
        ["gh", "release", "list", "--limit", str(limit), "--json", "tagName,isDraft,name"],
        cwd=ROOT,
        text=True,
    )
    releases = json.loads(raw)
    candidates = [
        rel["tagName"] for rel in releases
        if DATA_RELEASE_RE.match(rel["tagName"]) and rel["tagName"] not in keep_tags
    ]
    for tag in candidates:
        if yes:
            subprocess.run(["gh", "release", "delete", tag, "--yes"], cwd=ROOT, check=True)
        else:
            print(f"would delete {tag}")
    return candidates


def _path(value: str) -> Path:
    return Path(value).expanduser()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_manifest = sub.add_parser("manifest", help="write data/derived/data_package.json")
    p_manifest.add_argument("--source-dir", type=_path, default=DERIVED)
    p_manifest.add_argument("--date", default=_today())
    p_manifest.add_argument("--build-number", type=int, default=1)
    p_manifest.add_argument("--source-commit")

    p_package = sub.add_parser("package", help="build runtime and dev tar.gz bundles")
    p_package.add_argument("--source-dir", type=_path, default=DERIVED)
    p_package.add_argument("--output-dir", type=_path, default=DIST)
    p_package.add_argument("--date", default=_today())
    p_package.add_argument("--build-number", type=int, default=int(os.environ.get("GITHUB_RUN_NUMBER", "1")))
    p_package.add_argument("--source-commit")

    p_version = sub.add_parser("version-tag", help="print the release tag for current data")
    p_version.add_argument("--source-dir", type=_path, default=DERIVED)
    p_version.add_argument("--date", default=_today())
    p_version.add_argument("--build-number", type=int, default=int(os.environ.get("GITHUB_RUN_NUMBER", "1")))

    p_pages = sub.add_parser("prepare-pages", help="inject runtime bundles into a Pages artifact")
    p_pages.add_argument("--site-dir", type=_path, required=True)
    p_pages.add_argument("--runtime-tar", type=_path, action="append", required=True)
    p_pages.add_argument("--default-package-id")
    p_pages.add_argument("--max-site-mb", type=int, default=900)

    p_publish = sub.add_parser("publish", help="publish package assets as a GitHub Release")
    p_publish.add_argument("--tag", required=True)
    p_publish.add_argument("--asset", type=_path, action="append", required=True)
    p_publish.add_argument("--title")
    p_publish.add_argument("--draft", action="store_true")

    p_download = sub.add_parser("download-dev", help="download and unpack a dev-derived bundle")
    p_download.add_argument("--tag", required=True)
    p_download.add_argument("--asset", required=True)
    p_download.add_argument("--output-dir", type=_path, default=DERIVED)

    p_cleanup = sub.add_parser("cleanup", help="dry-run or delete old data releases")
    p_cleanup.add_argument("--keep-tag", action="append", default=[])
    p_cleanup.add_argument("--limit", type=int, default=100)
    p_cleanup.add_argument("--yes", action="store_true")

    args = parser.parse_args()
    if args.cmd == "manifest":
        out = write_current_runtime_manifest(
            source_dir=args.source_dir,
            package_date=args.date,
            build_number=args.build_number,
            source_commit=args.source_commit,
        )
        print(out.relative_to(ROOT))
    elif args.cmd == "package":
        outputs = build_packages(
            source_dir=args.source_dir,
            output_dir=args.output_dir,
            package_date=args.date,
            build_number=args.build_number,
            source_commit=args.source_commit,
        )
        print(outputs.runtime_tar)
        print(outputs.dev_tar)
        print(outputs.checksums_path)
    elif args.cmd == "version-tag":
        print(build_release_tag(
            source_dir=args.source_dir,
            package_date=args.date,
            build_number=args.build_number,
        ))
    elif args.cmd == "prepare-pages":
        out = prepare_pages(
            runtime_tars=args.runtime_tar,
            site_dir=args.site_dir,
            default_package_id=args.default_package_id,
            max_site_mb=args.max_site_mb,
        )
        print(out)
    elif args.cmd == "publish":
        publish_release(tag=args.tag, assets=args.asset, title=args.title, draft=args.draft)
    elif args.cmd == "download-dev":
        download_dev_bundle(tag=args.tag, asset=args.asset, output_dir=args.output_dir)
    elif args.cmd == "cleanup":
        cleanup_releases(keep_tags=set(args.keep_tag), limit=args.limit, yes=args.yes)


if __name__ == "__main__":
    main()
