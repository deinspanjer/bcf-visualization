# Private Source Repo Runbook

The public repo does not commit the source EPUB. Private source files live in a
separate private repository:

```text
deinspanjer/bcf-visualization-private-source
```

The local checkout is `data/private-source/`, which is ignored by the public
repo.

## Local Maintainer Workflow

From the public repo root:

```sh
.venv/bin/python scripts/sync_private_source_repo.py
```

That command:

- clones or fast-forwards `data/private-source/`
- copies `data/raw/Brocktons_Celestial_Forge.epub` into the private repo
- writes `Brocktons_Celestial_Forge.metadata.json`
- commits the private source update when content changed
- creates a date/build ordinal tag such as `source-v20260510.1`
- pushes the private repo branch and tag

To fetch a fresh EPUB through FicHub locally instead of copying the existing
local EPUB:

```sh
.venv/bin/python scripts/sync_private_source_repo.py --download
```

Use `--no-push` to update the local private clone without committing or
pushing.

## Metadata Sidecar

The sidecar is `Brocktons_Celestial_Forge.metadata.json`. It records:

- `version_tag`
- generation timestamp
- file size
- MD5
- SHA-256
- provenance story URL and FicHub export URL
- chapter count
- last chapter friendly number/title/href
- last chapter publish timestamp from `data/derived/chapters.json`
- max last-modification timestamp from `data/derived/chapter_last_edited.json`

SHA-256 is included alongside MD5 because MD5 is useful for legacy comparison
but should not be the only integrity check.

## GitHub Actions Access

The public repo's `Build data release` workflow can checkout the private source
repo with a read-only deploy key.

Required public repo secret:

```text
BCF_PRIVATE_SOURCE_DEPLOY_KEY
```

This secret must contain the private half of an SSH deploy key whose public
half is installed as a read-only deploy key on the private source repo.

The workflow input `private_source_repo` defaults to:

```text
deinspanjer/bcf-visualization-private-source
```

The workflow input `private_source_ref` defaults to the currently configured
source tag. Update it when intentionally building from a newer private source
tag, for example:

```text
source-v20260510.1
```

Set it to blank only if intentionally falling back to `scripts/download_bcf_epub.py`
and FicHub.

## Fork Setup

Someone forking the project should:

1. Create their own private source repo.
2. Add their EPUB as `Brocktons_Celestial_Forge.epub`.
3. Run `scripts/sync_private_source_repo.py --repo OWNER/PRIVATE-REPO`.
4. Create an SSH deploy key pair.
5. Add the public key as a read-only deploy key on the private source repo.
6. Add the private key as `BCF_PRIVATE_SOURCE_DEPLOY_KEY` in the public fork's
   Actions secrets.
7. Run `Build data release` with `private_source_repo=OWNER/PRIVATE-REPO` and
   `private_source_ref=source-vYYYYMMDD.N`.

Do not use a broad personal access token unless deploy keys are not viable.
Deploy keys keep access scoped to exactly one private source repository.
