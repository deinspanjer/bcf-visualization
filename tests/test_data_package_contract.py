from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
import urllib.error
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_web_runtime_manifest_matches_files_and_hashes() -> None:
    manifest = _load_json(DERIVED / "data_package.json")

    assert manifest["schema_version"] == 1
    assert manifest["package_prefix"] == "bcf-visualization"
    assert manifest["package_kind"] == "runtime"
    assert manifest["package_date"] == "20260509"
    assert manifest["story_chapter_ordinal"] == 194
    assert manifest["story_chapter_num"] == "120.1"
    assert manifest["version_label"] == "BCF data 20260509.1, story ch 194 / 120.1"
    assert manifest["contract"] == "bcf-visualization-data"
    assert manifest["contract_version"] == 1
    assert manifest["bundle_class"] == "pages-runtime"
    assert manifest["entrypoints"]["web"]["required"] == ["chapter_facts"]

    for name, meta in manifest["files"].items():
        path = DERIVED / meta["path"]
        assert path.exists(), name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert meta["sha256"] == digest
        assert meta["size_bytes"] == path.stat().st_size
        doc = _load_json(path)
        assert doc["schema_version"] == meta["schema_version"]


def test_web_consumed_schemas_pin_contract_versions() -> None:
    for schema_name in (
        "chapter_facts",
        "perk_directory",
        "constellation_wireframes",
        "roll_resolutions",
    ):
        schema = _load_json(DERIVED / "_schemas" / f"{schema_name}.schema.json")
        assert "schema_version" in schema["required"]
        assert schema["properties"]["schema_version"] == {"const": 1}


def test_package_command_builds_runtime_and_dev_bundles(tmp_path: Path) -> None:
    from scripts import data_release

    outputs = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path,
        package_date="20260509",
        build_number=7,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )

    assert outputs.release_tag == "bcf-visualization-data-v20260509.7-ch194-120.1"
    assert outputs.runtime_tar.name == (
        "bcf-visualization-runtime-v20260509.7-ch194-120.1.tar.gz"
    )
    assert outputs.dev_tar.name == (
        "bcf-visualization-data-v20260509.7-ch194-120.1.tar.gz"
    )
    assert outputs.checksums_path.name == "SHA256SUMS"

    with tarfile.open(outputs.runtime_tar, "r:gz") as tf:
        runtime_names = set(tf.getnames())
    assert "data_package.json" in runtime_names
    assert "chapter_facts.json" in runtime_names
    assert "perk_directory.json" not in runtime_names
    assert "roll_text_evidence.json" not in runtime_names

    with tarfile.open(outputs.runtime_tar, "r:gz") as tf:
        manifest = json.loads(tf.extractfile("data_package.json").read())
    assert manifest["package_id"] == "bcf-visualization-runtime-v20260509.7-ch194-120.1"
    assert manifest["release_tag"] == outputs.release_tag
    assert manifest["story_chapter_ordinal"] == 194
    assert manifest["story_chapter_num"] == "120.1"
    assert manifest["version_label"] == "BCF data 20260509.7, story ch 194 / 120.1"

    with tarfile.open(outputs.dev_tar, "r:gz") as tf:
        dev_names = set(tf.getnames())
    assert "data_package.json" in dev_names
    assert "roll_text_evidence.json" in dev_names
    assert "_schemas/chapter_facts.schema.json" not in dev_names

    extracted_dev = tmp_path / "extracted-dev"
    data_release._safe_extract(outputs.dev_tar, extracted_dev)
    dev_manifest = data_release.validate_package_dir(
        extracted_dev,
        expected_bundle_class="dev-derived",
    )
    assert dev_manifest["files"]["chapter_last_edited"]["schema_version"] is None


def test_prepare_pages_index_carries_display_version_metadata(tmp_path: Path) -> None:
    from scripts import data_release

    outputs = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist",
        package_date="20260509",
        build_number=10,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )

    index_path = data_release.prepare_pages(
        runtime_tars=[outputs.runtime_tar],
        site_dir=tmp_path / "site",
    )

    index = _load_json(index_path)
    package = index["packages"][0]
    assert index["default_package_id"] == (
        "bcf-visualization-runtime-v20260509.10-ch194-120.1"
    )
    assert package["package_prefix"] == "bcf-visualization"
    assert package["package_kind"] == "runtime"
    assert package["release_tag"] == (
        "bcf-visualization-data-v20260509.10-ch194-120.1"
    )
    assert package["story_chapter_ordinal"] == 194
    assert package["story_chapter_num"] == "120.1"
    assert package["version_label"] == "BCF data 20260509.10, story ch 194 / 120.1"


def test_prepare_pages_supports_multiple_runtime_packages(tmp_path: Path) -> None:
    from scripts import data_release

    outputs_a = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist-a",
        package_date="20260509",
        build_number=10,
        source_commit="test-commit-a",
        generated_at="2026-05-09T12:00:00Z",
    )
    outputs_b = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist-b",
        package_date="20260509",
        build_number=11,
        source_commit="test-commit-b",
        generated_at="2026-05-09T13:00:00Z",
    )

    index_path = data_release.prepare_pages(
        runtime_tars=[outputs_a.runtime_tar, outputs_b.runtime_tar],
        site_dir=tmp_path / "site",
        default_package_id="bcf-visualization-runtime-v20260509.11-ch194-120.1",
    )

    index = _load_json(index_path)
    assert index["default_package_id"] == (
        "bcf-visualization-runtime-v20260509.11-ch194-120.1"
    )
    assert [pkg["package_id"] for pkg in index["packages"]] == [
        "bcf-visualization-runtime-v20260509.10-ch194-120.1",
        "bcf-visualization-runtime-v20260509.11-ch194-120.1",
    ]
    assert (tmp_path / "site" / "data" / "default" / "data_package.json").is_file()
    assert (
        tmp_path
        / "site"
        / "data"
        / "packages"
        / "bcf-visualization-runtime-v20260509.10-ch194-120.1"
        / "data_package.json"
    ).is_file()


def test_prepare_pages_records_smoke_status_for_each_package(tmp_path: Path) -> None:
    from scripts import data_release

    outputs_a = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist-a",
        package_date="20260509",
        build_number=10,
        source_commit="test-commit-a",
        generated_at="2026-05-09T12:00:00Z",
    )
    outputs_b = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist-b",
        package_date="20260509",
        build_number=11,
        source_commit="test-commit-b",
        generated_at="2026-05-09T13:00:00Z",
    )

    index_path = data_release.prepare_pages(
        runtime_tars=[outputs_a.runtime_tar, outputs_b.runtime_tar],
        site_dir=tmp_path / "site",
        default_package_id="bcf-visualization-runtime-v20260509.10-ch194-120.1",
        smoke_status_by_package_id={
            "bcf-visualization-runtime-v20260509.10-ch194-120.1": "passed",
            "bcf-visualization-runtime-v20260509.11-ch194-120.1": "failed",
        },
        smoke_run_url="https://github.com/deinspanjer/bcf-visualization/actions/runs/1",
    )

    index = _load_json(index_path)
    assert [
        (pkg["package_id"], pkg["smoke_status"], pkg["smoke_run_url"])
        for pkg in index["packages"]
    ] == [
        (
            "bcf-visualization-runtime-v20260509.10-ch194-120.1",
            "passed",
            "https://github.com/deinspanjer/bcf-visualization/actions/runs/1",
        ),
        (
            "bcf-visualization-runtime-v20260509.11-ch194-120.1",
            "failed",
            "https://github.com/deinspanjer/bcf-visualization/actions/runs/1",
        ),
    ]


def test_prepare_pages_rejects_invalid_smoke_status(tmp_path: Path) -> None:
    from scripts import data_release

    outputs = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist",
        package_date="20260509",
        build_number=10,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )

    with pytest.raises(ValueError, match="unsupported smoke_status"):
        data_release.prepare_pages(
            runtime_tars=[outputs.runtime_tar],
            site_dir=tmp_path / "site",
            smoke_status_by_package_id={
                "bcf-visualization-runtime-v20260509.10-ch194-120.1": "burning",
            },
        )


def test_prepare_pages_preserves_existing_package_smoke_metadata(tmp_path: Path) -> None:
    from scripts import data_release

    outputs = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist",
        package_date="20260509",
        build_number=10,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )

    index_path = data_release.prepare_pages(
        runtime_tars=[outputs.runtime_tar],
        site_dir=tmp_path / "site",
        package_metadata_by_package_id={
            "bcf-visualization-runtime-v20260509.10-ch194-120.1": {
                "smoke_status": "failed",
                "smoke_run_url": "https://example.test/old-smoke",
            }
        },
    )

    package = _load_json(index_path)["packages"][0]
    assert package["smoke_status"] == "failed"
    assert package["smoke_run_url"] == "https://example.test/old-smoke"


def test_download_pages_runtime_tars_uses_deployed_packages_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import data_release

    payload = {
        "default_package_id": "bcf-visualization-runtime-v20260509.11-ch194-120.1",
        "packages": [
            {
                "package_id": "bcf-visualization-runtime-v20260509.10-ch194-120.1",
                "release_tag": "bcf-visualization-data-v20260509.10-ch194-120.1",
                "smoke_status": "failed",
                "smoke_run_url": "https://example.test/old-smoke",
            },
            {
                "package_id": "bcf-visualization-runtime-v20260509.11-ch194-120.1",
                "release_tag": "bcf-visualization-data-v20260509.11-ch194-120.1",
            },
        ],
    }
    calls: list[list[str]] = []

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        asset = cmd[5]
        (tmp_path / "downloads" / asset).write_text("runtime\n")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(data_release.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(data_release.subprocess, "run", fake_run)

    paths = data_release.download_pages_runtime_tars(
        packages_url="https://example.test/data/packages.json",
        output_dir=tmp_path / "downloads",
        metadata_output=tmp_path / "metadata.json",
    )

    assert [path.name for path in paths] == [
        "bcf-visualization-runtime-v20260509.10-ch194-120.1.tar.gz",
        "bcf-visualization-runtime-v20260509.11-ch194-120.1.tar.gz",
    ]
    assert [cmd[3] for cmd in calls] == [
        "bcf-visualization-data-v20260509.10-ch194-120.1",
        "bcf-visualization-data-v20260509.11-ch194-120.1",
    ]
    metadata = _load_json(tmp_path / "metadata.json")
    assert metadata["default_package_id"] == (
        "bcf-visualization-runtime-v20260509.11-ch194-120.1"
    )
    assert metadata["packages"][0]["smoke_status"] == "failed"
    assert metadata["packages"][0]["smoke_run_url"] == "https://example.test/old-smoke"


def test_download_pages_runtime_tars_can_fallback_when_pages_index_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import data_release

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        asset = cmd[5]
        (tmp_path / "downloads" / asset).write_text("runtime\n")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(
        data_release.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )
    monkeypatch.setattr(data_release.subprocess, "run", fake_run)

    paths = data_release.download_pages_runtime_tars(
        packages_url="https://example.test/data/packages.json",
        output_dir=tmp_path / "downloads",
        fallback_tag="bcf-visualization-data-v20260509.10-ch194-120.1",
        fallback_asset="bcf-visualization-runtime-v20260509.10-ch194-120.1.tar.gz",
        metadata_output=tmp_path / "metadata.json",
    )

    assert [path.name for path in paths] == [
        "bcf-visualization-runtime-v20260509.10-ch194-120.1.tar.gz"
    ]
    assert calls[0][3] == "bcf-visualization-data-v20260509.10-ch194-120.1"
    metadata = _load_json(tmp_path / "metadata.json")
    assert metadata["default_package_id"] == (
        "bcf-visualization-runtime-v20260509.10-ch194-120.1"
    )


def test_cleanup_release_dry_run_protects_workflow_and_deployed_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import data_release

    releases = [
        {
            "tagName": "bcf-visualization-data-v20260509.4-ch194-120.1",
            "isDraft": False,
            "name": "protected deployed",
        },
        {
            "tagName": "bcf-visualization-data-v20260509.5-ch194-120.1",
            "isDraft": False,
            "name": "candidate",
        },
    ]
    deleted: list[str] = []

    def fake_check_output(cmd: list[str], **_: object) -> str:
        assert cmd[:3] == ["gh", "release", "list"]
        return json.dumps(releases)

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        deleted.append(cmd[3])
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(data_release.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(data_release.subprocess, "run", fake_run)
    monkeypatch.setattr(
        data_release,
        "_deployed_packages_tags",
        lambda url: {
            "bcf-visualization-data-v20260509.4-ch194-120.1": ["deployed Pages"],
        },
    )

    plan = data_release.cleanup_releases(
        keep_tags=set(),
        limit=100,
        delete=False,
        protect_workflow_defaults=True,
        deployed_packages_url="https://example.test/packages.json",
    )

    assert plan.delete_candidates == [
        "bcf-visualization-data-v20260509.5-ch194-120.1"
    ]
    assert "bcf-visualization-data-v20260509.4-ch194-120.1" in plan.protected_tags
    assert deleted == []


def test_cleanup_release_delete_requires_explicit_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import data_release

    releases = [
        {
            "tagName": "bcf-visualization-data-v20260509.5-ch194-120.1",
            "isDraft": False,
            "name": "candidate",
        },
    ]
    deleted: list[str] = []

    monkeypatch.setattr(
        data_release.subprocess,
        "check_output",
        lambda *args, **kwargs: json.dumps(releases),
    )
    monkeypatch.setattr(
        data_release.subprocess,
        "run",
        lambda cmd, **kwargs: deleted.append(cmd[3]) or subprocess.CompletedProcess(cmd, 0),
    )

    data_release.cleanup_releases(
        keep_tags=set(),
        limit=100,
        delete=True,
        protect_workflow_defaults=False,
        deployed_packages_url=None,
    )

    assert deleted == ["bcf-visualization-data-v20260509.5-ch194-120.1"]


def test_safe_extract_rejects_symlink_members(tmp_path: Path) -> None:
    from scripts import data_release

    tar_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        info = tarfile.TarInfo("linked")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)

    with pytest.raises(ValueError, match="unsafe tar member type"):
        data_release._safe_extract(tar_path, tmp_path / "out")


def test_prepare_pages_rejects_tampered_runtime_bundle(tmp_path: Path) -> None:
    from scripts import data_release

    outputs = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist",
        package_date="20260509",
        build_number=8,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )
    extracted = tmp_path / "extracted"
    data_release._safe_extract(outputs.runtime_tar, extracted)
    chapter_facts = extracted / "chapter_facts.json"
    text = chapter_facts.read_text()
    replacement = "schema_versioN"
    assert "schema_version" in text
    assert len(replacement) == len("schema_version")
    chapter_facts.write_text(text.replace("schema_version", replacement, 1))
    tampered = tmp_path / "tampered.tar.gz"
    with tarfile.open(tampered, "w:gz") as tf:
        for path in sorted(extracted.rglob("*")):
            if path.is_file():
                tf.add(path, arcname=path.relative_to(extracted).as_posix())

    with pytest.raises(ValueError, match="package file hash mismatch"):
        data_release.prepare_pages(runtime_tars=[tampered], site_dir=tmp_path / "site")


def test_prepare_pages_rejects_unsupported_contract_version(tmp_path: Path) -> None:
    from scripts import data_release

    outputs = data_release.build_packages(
        source_dir=DERIVED,
        output_dir=tmp_path / "dist",
        package_date="20260509",
        build_number=9,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )
    extracted = tmp_path / "extracted_contract"
    data_release._safe_extract(outputs.runtime_tar, extracted)
    manifest_path = extracted / "data_package.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["contract_version"] = 99
    manifest_path.write_text(json.dumps(manifest) + "\n")
    tampered = tmp_path / "unsupported.tar.gz"
    with tarfile.open(tampered, "w:gz") as tf:
        for path in sorted(extracted.rglob("*")):
            if path.is_file():
                tf.add(path, arcname=path.relative_to(extracted).as_posix())

    with pytest.raises(ValueError, match="unsupported data package contract_version"):
        data_release.prepare_pages(runtime_tars=[tampered], site_dir=tmp_path / "site")
