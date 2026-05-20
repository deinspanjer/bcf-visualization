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
- creates a date/build ordinal exact-rebuild tag such as `source-vYYYYMMDD.N`
- pushes the private repo branch and tag

To fetch a fresh EPUB through FicHub locally instead of copying the existing
local EPUB:

```sh
.venv/bin/python scripts/sync_private_source_repo.py --download
```

Use `--no-push` to update the local private clone without committing or
pushing. The normal maintainer release path follows the private repo default
branch (`main`); tags are only pins for exact rebuilds.

After the private repo has the desired EPUB, hydrate the public checkout:

```sh
.venv/bin/python scripts/hydrate_source_epub.py
```

The hydration script copies `data/private-source/Brocktons_Celestial_Forge.epub`
to `data/raw/Brocktons_Celestial_Forge.epub` and writes
`data/raw/Brocktons_Celestial_Forge.source.json`. It is non-networked; if the
private checkout is unavailable, contributors can place a compatible EPUB at
`data/raw/Brocktons_Celestial_Forge.epub` and run the same command.

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
- max last-modification timestamp from `data/manual/chapter_publication_dates.json`

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

The workflow input `private_source_ref` defaults to the private repo default
branch:

```text
main
```

Override it only for exact rebuilds from a tag or commit SHA. The release
workflow no longer downloads from FicHub; if private source is unavailable, an
already-present `data/raw/Brocktons_Celestial_Forge.epub` is the fallback.

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
   the default `private_source_ref=main`, or with a tag/commit only for a pinned
   rebuild.

Do not use a broad personal access token unless deploy keys are not viable.
Deploy keys keep access scoped to exactly one private source repository.
