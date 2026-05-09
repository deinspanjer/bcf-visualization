from __future__ import annotations

import json
from pathlib import Path


def test_copy_derived_json_copies_top_level_generated_files(tmp_path: Path) -> None:
    from scripts import copy_bcf_data_from_worktree

    source = tmp_path / "source" / "data" / "derived"
    output = tmp_path / "output" / "data" / "derived"
    source.mkdir(parents=True)
    (source / "chapter_facts.json").write_text("{}\n")
    (source / "data_package.json").write_text("{}\n")
    (source / "_schemas").mkdir()
    (source / "_schemas" / "chapter_facts.schema.json").write_text("{}\n")

    copied = copy_bcf_data_from_worktree.copy_derived_json(source, output)

    assert sorted(path.name for path in copied) == [
        "chapter_facts.json",
        "data_package.json",
    ]
    assert (output / "chapter_facts.json").is_file()
    assert not (output / "_schemas" / "chapter_facts.schema.json").exists()


def test_deployed_package_base_url_uses_default_package() -> None:
    from scripts import download_deployed_data_package

    index = {
        "default_package_id": "pkg-b",
        "packages": [
            {"package_id": "pkg-a", "path": "data/packages/pkg-a"},
            {"package_id": "pkg-b", "path": "data/packages/pkg-b"},
        ],
    }

    assert download_deployed_data_package.package_base_url(
        "https://example.test/bcf/data/packages.json",
        index,
    ) == "https://example.test/bcf/data/packages/pkg-b/"


def test_download_deployed_package_writes_manifest_and_runtime_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from scripts import download_deployed_data_package

    packages = {
        "default_package_id": "pkg-a",
        "packages": [{"package_id": "pkg-a", "path": "data/packages/pkg-a"}],
    }
    manifest = {
        "package_id": "pkg-a",
        "files": {
            "chapter_facts": {"path": "chapter_facts.json"},
            "roll_resolutions": {"path": "nested/roll_resolutions.json"},
        },
    }
    payloads = {
        "https://example.test/bcf/data/packages.json": packages,
        "https://example.test/bcf/data/packages/pkg-a/data_package.json": manifest,
        "https://example.test/bcf/data/packages/pkg-a/chapter_facts.json": {
            "schema_version": 1,
        },
        "https://example.test/bcf/data/packages/pkg-a/nested/roll_resolutions.json": {
            "schema_version": 1,
        },
    }

    def fake_load_json_url(url: str) -> dict:
        return payloads[url]

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    def fake_urlopen(request, timeout: int = 120):
        return FakeResponse(payloads[request.full_url])

    monkeypatch.setattr(download_deployed_data_package, "load_json_url", fake_load_json_url)
    monkeypatch.setattr(download_deployed_data_package.urllib.request, "urlopen", fake_urlopen)

    output = tmp_path / "data" / "derived"
    result = download_deployed_data_package.download_package(
        packages_url="https://example.test/bcf/data/packages.json",
        output_dir=output,
    )

    assert result == manifest
    assert json.loads((output / "data_package.json").read_text()) == manifest
    assert json.loads((output / "chapter_facts.json").read_text()) == {"schema_version": 1}
    assert json.loads((output / "nested" / "roll_resolutions.json").read_text()) == {
        "schema_version": 1,
    }
