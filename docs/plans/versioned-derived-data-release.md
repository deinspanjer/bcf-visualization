# Versioned Derived Data Release Plan

This plan captures the recovered rollout for moving high-churn derived
data out of ordinary source commits while keeping the GitHub Pages app
served by GitHub-native artifacts.

## Constraints

- GitHub Pages should serve same-origin unpacked JSON. The browser
  should not fetch GitHub Release assets directly.
- GitHub Releases are the archival package surface. Pages deploys pin
  explicit release tags and unpack runtime bundles into the Pages
  artifact.
- `git-filter-repo` is a separate coordinated history rewrite, not part
  of the first migration.
- Derived JSON remains the runtime and Forge Curator source of truth.
  Removing it from source commits must not make local bootstrap,
  testing, or Pages deployment ambiguous.

## Phase 1: Prove Versioned Packages

Goal: add release-backed package mechanics while leaving committed
`data/derived/*.json` in place.

- Mark data JSON as generated in `.gitattributes` so GitHub collapses
  noisy generated diffs.
- Add a bundle-level `data_package.json` manifest with:
  - package prefix, package kind, package date, and build number
  - story chapter ordinal, chapter number, and chapter title
  - source commit and generated timestamp
  - contract name and contract version
  - bundle class: `pages-runtime` or `dev-derived`
  - file paths, schema names, schema versions, sizes, and SHA-256 hashes
- Add exact schema-version checks for web-consumed runtime files.
- Add release tooling that emits:
  - `bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER`
  - `bcf-visualization-runtime-vYYYYMMDD.N-chORDINAL-CHAPTER.tar.gz`
  - `bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER.tar.gz`
  - `SHA256SUMS`
- Update Pages deployment so it can either:
  - package committed Phase 1 derived data when no release is pinned, or
  - download a pinned published release runtime asset.
- Stage Pages data under:
  - `data/default/`
  - `data/packages/<package_id>/`
  - `data/packages.json`
- Keep `data/raw/` out of the Pages artifact.
- Load the package manifest before rendering the app, and fail clearly
  on unsupported contract versions or missing required runtime files.
- Validate local bootstrap by downloading the maintainer/data bundle
  into `data/derived/` or a scratch output directory.

Status: complete. The first fully validated release-backed Pages deploy
and local maintainer bootstrap used:

```text
bcf-visualization-data-v20260509.3-ch194-120.1
```

## Phase 2: Untrack High-Churn Derived JSON

Goal: remove top-level generated derived JSON from normal source
commits after Phase 1 is proven.

- Add `.gitignore` coverage for top-level `data/derived/*.json`.
- Remove selected top-level `data/derived/*.json` files from the Git
  index without deleting local working copies.
- Keep committed:
  - `data/derived/_schemas/**`
  - `data/manual/**`
  - scripts, docs, workflows, tests, raw source snapshots, and figures
- Preserve local generated JSON during the migration so active Forge
  Curator and derivation work can continue.
- Make GitHub workflows bootstrap from the validated maintainer bundle
  when checked-out derived JSON is absent.
- Document the fresh-checkout bootstrap command as the normal way to
  hydrate `data/derived/` for local TUI, derivation, and test work.
- Verify that release packaging, Pages deployment, and local tests still
  work from hydrated data.

Status: complete. After untracking top-level generated derived JSON,
the first validated release-backed Pages deploy from regenerated manual
inputs used:

```text
bcf-visualization-data-v20260509.4-ch194-120.1
```

## Phase 3: Release Maintenance And Multi-Package Pages

Goal: make long-lived release operations explicit and safe.

- Keep release cleanup dry-run by default.
- Require an explicit confirmation flag for deletion.
- Never mutate release assets in place.
- Protect the current/default Pages package and any release referenced
  by deployed `packages.json` or workflow defaults.
- Report immutable or protected releases rather than forcing deletion.
- If multiple runtime packages are injected into Pages, show a version
  selector only when `packages.json` contains more than one package.
- Keep Pages deploys pinned to explicit version tags, never `latest`.

## Phase 4: Optional History Rewrite

Goal: reduce historical repository size only if the operational benefit
justifies the coordination cost.

- Treat `git-filter-repo` as a migration event with a write freeze.
- Prepare branch, fork, and reclone guidance before rewriting history.
- Avoid history rewriting merely to reduce review noise; generated-file
  diff collapse and Phase 2 untracking address that separately.
- Ensure no active branch can recontaminate rewritten history with the
  removed derived blobs.
