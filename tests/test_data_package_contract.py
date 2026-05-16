from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tarfile
import urllib.error
from pathlib import Path
import pytest

from scripts.data_paths import DERIVED

ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_tiny_package_source(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "chapter_facts.json").write_text(
        json.dumps({
            "schema_version": 1,
            "chapters": [
                {"chapter_num": "1", "full_title": "1 Fixture Start"},
                {"chapter_num": "2.5", "full_title": "2.5 Fixture Finale"},
            ],
        }) + "\n"
    )
    (path / "chapter_last_edited.json").write_text(
        json.dumps({"chapters": []}) + "\n"
    )
    return path


def test_web_runtime_manifest_matches_files_and_hashes() -> None:
    manifest = _load_json(DERIVED / "data_package.json")
    chapter_facts = _load_json(DERIVED / "chapter_facts.json")
    chapters = chapter_facts["chapters"]
    latest = chapters[-1]

    assert manifest["schema_version"] == 1
    assert manifest["package_prefix"] == "bcf-visualization"
    assert manifest["package_kind"] == "runtime"
    assert manifest["package_date"].isdigit()
    assert len(manifest["package_date"]) == 8
    assert manifest["story_chapter_ordinal"] == len(chapters)
    assert manifest["story_chapter_num"] == str(latest["chapter_num"])
    assert manifest["version_label"] == (
        f"BCF data {manifest['package_date']}.{manifest['build_number']}, "
        f"story ch {manifest['story_chapter_ordinal']} / {manifest['story_chapter_num']}"
    )
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
    ):
        schema = _load_json(DERIVED / "_schemas" / f"{schema_name}.schema.json")
        assert "schema_version" in schema["required"]
        assert schema["properties"]["schema_version"] == {"const": 1}


def test_package_command_builds_runtime_and_dev_bundles(tmp_path: Path) -> None:
    from scripts import data_release
    source = _write_tiny_package_source(tmp_path / "source")

    outputs = data_release.build_packages(
        source_dir=source,
        output_dir=tmp_path,
        package_date="20260509",
        build_number=7,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )

    assert outputs.release_tag == "bcf-visualization-data-v20260509.7-ch2-2.5"
    assert outputs.runtime_tar.name == (
        "bcf-visualization-runtime-v20260509.7-ch2-2.5.tar.gz"
    )
    assert outputs.dev_tar.name == (
        "bcf-visualization-data-v20260509.7-ch2-2.5.tar.gz"
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
    assert manifest["package_id"] == "bcf-visualization-runtime-v20260509.7-ch2-2.5"
    assert manifest["release_tag"] == outputs.release_tag
    assert manifest["story_chapter_ordinal"] == 2
    assert manifest["story_chapter_num"] == "2.5"
    assert manifest["version_label"] == "BCF data 20260509.7, story ch 2 / 2.5"

    with tarfile.open(outputs.dev_tar, "r:gz") as tf:
        dev_names = set(tf.getnames())
    assert "data_package.json" in dev_names
    assert "chapter_last_edited.json" in dev_names
    assert "_schemas/chapter_facts.schema.json" not in dev_names

    extracted_dev = tmp_path / "extracted-dev"
    data_release._safe_extract(outputs.dev_tar, extracted_dev)
    dev_manifest = data_release.validate_package_dir(
        extracted_dev,
        expected_bundle_class="dev-derived",
    )
    assert dev_manifest["files"]["chapter_last_edited"]["schema_version"] is None


def test_refresh_runtime_manifest_preserves_version_and_updates_hashes(tmp_path: Path) -> None:
    from scripts import data_release

    derived = tmp_path / "derived"
    derived.mkdir()
    chapter_facts = {
        "schema_version": 1,
        "chapters": [
            {"chapter_num": "1", "full_title": "1 Opening"},
        ],
    }
    (derived / "chapter_facts.json").write_text(json.dumps(chapter_facts) + "\n")
    data_release.write_current_runtime_manifest(
        source_dir=derived,
        package_date="20260509",
        build_number=7,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )
    stale_manifest = _load_json(derived / "data_package.json")

    chapter_facts["chapters"][0]["full_title"] = "1 Updated"
    (derived / "chapter_facts.json").write_text(json.dumps(chapter_facts) + "\n")

    data_release.refresh_current_runtime_manifest(source_dir=derived)

    manifest = _load_json(derived / "data_package.json")
    assert manifest["package_date"] == "20260509"
    assert manifest["build_number"] == 7
    assert manifest["source_commit"] == "test-commit"
    assert manifest["files"]["chapter_facts"]["sha256"] != (
        stale_manifest["files"]["chapter_facts"]["sha256"]
    )
    assert manifest["files"]["chapter_facts"]["sha256"] == hashlib.sha256(
        (derived / "chapter_facts.json").read_bytes()
    ).hexdigest()


def test_download_dev_keeps_dev_manifest_separate_and_writes_runtime_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import data_release

    source = tmp_path / "source"
    dist = tmp_path / "dist"
    output = tmp_path / "derived"
    source.mkdir()
    chapter_facts = {
        "schema_version": 1,
        "chapters": [
            {"chapter_num": "1", "full_title": "1 Opening"},
        ],
    }
    (source / "chapter_facts.json").write_text(json.dumps(chapter_facts) + "\n")
    outputs = data_release.build_packages(
        source_dir=source,
        output_dir=dist,
        package_date="20260509",
        build_number=7,
        source_commit="test-commit",
        generated_at="2026-05-09T12:00:00Z",
    )

    def fake_run(cmd: list[str], **kwargs) -> None:
        assert cmd[:3] == ["gh", "release", "download"]
        target_dir = Path(cmd[-1])
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(outputs.dev_tar, target_dir / outputs.dev_tar.name)

    monkeypatch.setattr(data_release.subprocess, "run", fake_run)

    data_release.download_dev_bundle(
        tag=outputs.release_tag,
        asset=outputs.dev_tar.name,
        output_dir=output,
    )

    runtime_manifest = _load_json(output / "data_package.json")
    dev_manifest = _load_json(output / data_release.DEV_BUNDLE_MANIFEST_NAME)
    assert runtime_manifest["package_kind"] == "runtime"
    assert runtime_manifest["bundle_class"] == "pages-runtime"
    assert dev_manifest["package_kind"] == "data"
    assert dev_manifest["bundle_class"] == "dev-derived"
    assert runtime_manifest["source_commit"] == "test-commit"
    assert data_release.check_local_derived_coherence(output) == []


def test_local_derived_coherence_flags_dev_manifest_in_runtime_slot(
    tmp_path: Path,
) -> None:
    from scripts import data_release

    derived = tmp_path / "derived"
    derived.mkdir()
    (derived / "chapter_facts.json").write_text(
        json.dumps({"schema_version": 1, "chapters": []}) + "\n"
    )
    (derived / "data_package.json").write_text(
        json.dumps({
            "bundle_class": "dev-derived",
            "package_kind": "data",
            "files": {},
        }) + "\n"
    )

    problems = data_release.check_local_derived_coherence(derived)

    assert any("pages-runtime manifest" in problem for problem in problems)
    assert any("package_kind is not runtime" in problem for problem in problems)


def test_local_derived_coherence_flags_stale_predicted_rolls(
    tmp_path: Path,
) -> None:
    from scripts import data_release

    derived = tmp_path / "derived"
    derived.mkdir()
    (derived / "data_package.json").write_text(
        json.dumps({
            "bundle_class": "pages-runtime",
            "package_kind": "runtime",
            "files": {},
        }) + "\n"
    )
    (derived / "chapters.json").write_text(
        json.dumps({
            "chapters": [{
                "chapter_num": "91.9",
                "full_title": "91.9 Test",
                "sort_key": [91, 9],
            }],
        }) + "\n"
    )
    (derived / "chapter_sections.json").write_text(
        json.dumps({
            "chapters": [{
                "chapter_num": "91.9",
                "full_title": "91.9 Test",
                "sections": [{"word_count": 2000, "counts_for_cp": True}],
            }],
        }) + "\n"
    )
    (derived / "obtained_perks.json").write_text(
        json.dumps({"perks": []}) + "\n"
    )
    (derived / "predicted_rolls.json").write_text(
        json.dumps({"_total_words_epub_exact": 0, "predicted": []}) + "\n"
    )

    problems = data_release.check_local_derived_coherence(derived)

    assert any("predicted_rolls.json" in problem for problem in problems)


def test_download_dev_defaults_to_latest_data_release(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import data_release

    releases = [
        {"tagName": "not-a-data-release", "isDraft": False},
        {
            "tagName": "bcf-visualization-data-v20260510.6-ch194-120.1",
            "isDraft": False,
        },
        {
            "tagName": "bcf-visualization-data-v20260510.5-ch194-120.1",
            "isDraft": False,
        },
    ]

    def fake_check_output(cmd: list[str], **kwargs) -> str:
        assert cmd[:3] == ["gh", "release", "list"]
        assert "--exclude-drafts" in cmd
        assert "--order" in cmd
        assert "desc" in cmd
        assert kwargs["cwd"] == data_release.ROOT
        return json.dumps(releases)

    monkeypatch.setattr(data_release.subprocess, "check_output", fake_check_output)

    tag, asset = data_release.resolve_dev_bundle_selection(None, None)

    assert tag == "bcf-visualization-data-v20260510.6-ch194-120.1"
    assert asset == "bcf-visualization-data-v20260510.6-ch194-120.1.tar.gz"


def test_download_dev_derives_asset_from_explicit_tag() -> None:
    from scripts import data_release

    tag, asset = data_release.resolve_dev_bundle_selection(
        "bcf-visualization-data-v20260510.6-ch194-120.1",
        None,
    )

    assert tag == "bcf-visualization-data-v20260510.6-ch194-120.1"
    assert asset == "bcf-visualization-data-v20260510.6-ch194-120.1.tar.gz"


def test_download_dev_latest_fails_when_no_data_release_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import data_release

    monkeypatch.setattr(
        data_release.subprocess,
        "check_output",
        lambda *args, **kwargs: json.dumps([
            {"tagName": "unrelated-v1", "isDraft": False},
            {
                "tagName": "bcf-visualization-data-v20260510.6-ch194-120.1",
                "isDraft": True,
            },
        ]),
    )

    with pytest.raises(RuntimeError, match="no published bcf-visualization data release"):
        data_release.resolve_dev_bundle_selection(None, None)


def test_prepare_pages_index_carries_display_version_metadata(tmp_path: Path) -> None:
    from scripts import data_release
    source = _write_tiny_package_source(tmp_path / "source")

    outputs = data_release.build_packages(
        source_dir=source,
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
        "bcf-visualization-runtime-v20260509.10-ch2-2.5"
    )
    assert package["package_prefix"] == "bcf-visualization"
    assert package["package_kind"] == "runtime"
    assert package["release_tag"] == (
        "bcf-visualization-data-v20260509.10-ch2-2.5"
    )
    assert package["story_chapter_ordinal"] == 2
    assert package["story_chapter_num"] == "2.5"
    assert package["version_label"] == "BCF data 20260509.10, story ch 2 / 2.5"


def test_prepare_pages_supports_multiple_runtime_packages(tmp_path: Path) -> None:
    from scripts import data_release
    source = _write_tiny_package_source(tmp_path / "source")

    outputs_a = data_release.build_packages(
        source_dir=source,
        output_dir=tmp_path / "dist-a",
        package_date="20260509",
        build_number=10,
        source_commit="test-commit-a",
        generated_at="2026-05-09T12:00:00Z",
    )
    outputs_b = data_release.build_packages(
        source_dir=source,
        output_dir=tmp_path / "dist-b",
        package_date="20260509",
        build_number=11,
        source_commit="test-commit-b",
        generated_at="2026-05-09T13:00:00Z",
    )

    index_path = data_release.prepare_pages(
        runtime_tars=[outputs_a.runtime_tar, outputs_b.runtime_tar],
        site_dir=tmp_path / "site",
        default_package_id="bcf-visualization-runtime-v20260509.11-ch2-2.5",
    )

    index = _load_json(index_path)
    assert index["default_package_id"] == (
        "bcf-visualization-runtime-v20260509.11-ch2-2.5"
    )
    assert [pkg["package_id"] for pkg in index["packages"]] == [
        "bcf-visualization-runtime-v20260509.10-ch2-2.5",
        "bcf-visualization-runtime-v20260509.11-ch2-2.5",
    ]
    assert (tmp_path / "site" / "data" / "default" / "data_package.json").is_file()
    assert (
        tmp_path
        / "site"
        / "data"
        / "packages"
        / "bcf-visualization-runtime-v20260509.10-ch2-2.5"
        / "data_package.json"
    ).is_file()


def test_prepare_pages_records_smoke_status_for_each_package(tmp_path: Path) -> None:
    from scripts import data_release
    source = _write_tiny_package_source(tmp_path / "source")

    outputs_a = data_release.build_packages(
        source_dir=source,
        output_dir=tmp_path / "dist-a",
        package_date="20260509",
        build_number=10,
        source_commit="test-commit-a",
        generated_at="2026-05-09T12:00:00Z",
    )
    outputs_b = data_release.build_packages(
        source_dir=source,
        output_dir=tmp_path / "dist-b",
        package_date="20260509",
        build_number=11,
        source_commit="test-commit-b",
        generated_at="2026-05-09T13:00:00Z",
    )

    index_path = data_release.prepare_pages(
        runtime_tars=[outputs_a.runtime_tar, outputs_b.runtime_tar],
        site_dir=tmp_path / "site",
        default_package_id="bcf-visualization-runtime-v20260509.10-ch2-2.5",
        smoke_status_by_package_id={
            "bcf-visualization-runtime-v20260509.10-ch2-2.5": "passed",
            "bcf-visualization-runtime-v20260509.11-ch2-2.5": "failed",
        },
        smoke_run_url="https://github.com/deinspanjer/bcf-visualization/actions/runs/1",
    )

    index = _load_json(index_path)
    assert [
        (pkg["package_id"], pkg["smoke_status"], pkg["smoke_run_url"])
        for pkg in index["packages"]
    ] == [
        (
            "bcf-visualization-runtime-v20260509.10-ch2-2.5",
            "passed",
            "https://github.com/deinspanjer/bcf-visualization/actions/runs/1",
        ),
        (
            "bcf-visualization-runtime-v20260509.11-ch2-2.5",
            "failed",
            "https://github.com/deinspanjer/bcf-visualization/actions/runs/1",
        ),
    ]


def test_prepare_pages_rejects_invalid_smoke_status(tmp_path: Path) -> None:
    from scripts import data_release
    source = _write_tiny_package_source(tmp_path / "source")

    outputs = data_release.build_packages(
        source_dir=source,
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
                "bcf-visualization-runtime-v20260509.10-ch2-2.5": "burning",
            },
        )


def test_prepare_pages_preserves_existing_package_smoke_metadata(tmp_path: Path) -> None:
    from scripts import data_release
    source = _write_tiny_package_source(tmp_path / "source")

    outputs = data_release.build_packages(
        source_dir=source,
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
            "bcf-visualization-runtime-v20260509.10-ch2-2.5": {
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
    source = _write_tiny_package_source(tmp_path / "source")

    outputs = data_release.build_packages(
        source_dir=source,
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
    source = _write_tiny_package_source(tmp_path / "source")

    outputs = data_release.build_packages(
        source_dir=source,
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
