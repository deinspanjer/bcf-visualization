export const SUPPORTED_DATA_CONTRACT_VERSION = 1;
export const DATA_CONTRACT = "bcf-visualization-data";

function foundValue(value) {
  return value == null ? "missing" : String(value);
}

export function validateDataPackageManifest(manifest) {
  if (!manifest || typeof manifest !== "object") {
    throw new Error("Data package manifest is missing or malformed.");
  }
  if (manifest.contract !== DATA_CONTRACT) {
    throw new Error(`Unsupported data package contract: expected ${DATA_CONTRACT}, found ${foundValue(manifest.contract)}.`);
  }
  if (manifest.contract_version !== SUPPORTED_DATA_CONTRACT_VERSION) {
    throw new Error(`Unsupported data package contract: expected ${SUPPORTED_DATA_CONTRACT_VERSION}, found ${foundValue(manifest.contract_version)}.`);
  }
  const web = manifest.entrypoints && manifest.entrypoints.web;
  if (!web || !Array.isArray(web.required)) {
    throw new Error("Data package manifest does not define web entrypoints.");
  }
  const files = manifest.files || {};
  for (const name of web.required) {
    if (!files[name] || !files[name].path || files[name].schema_version == null) {
      throw new Error(`Data package manifest is missing required file metadata: ${name}.`);
    }
  }
  return {
    required: web.required,
    optional: Array.isArray(web.optional) ? web.optional : [],
    files,
  };
}

export function validateDataDocument(name, doc, meta, options = {}) {
  const expected = meta && meta.schema_version;
  const found = doc && doc.schema_version;
  if (expected == null || found !== expected) {
    const reason = `Unsupported ${name} schema_version: expected ${foundValue(expected)}, found ${foundValue(found)}`;
    if (options.optional) return { ok: false, reason };
    throw new Error(reason);
  }
  return { ok: true };
}

export function dataVersionLabel(pkg) {
  if (!pkg || typeof pkg !== "object") return "Data version unknown";
  if (pkg.version_label) return String(pkg.version_label);

  const date = pkg.package_date;
  const build = pkg.build_number;
  const ordinal = pkg.story_chapter_ordinal;
  const chapterNum = pkg.story_chapter_num;
  if (date && build != null && ordinal != null && chapterNum) {
    return `BCF data ${date}.${build}, story ch ${ordinal} / ${chapterNum}`;
  }

  return pkg.package_id || "Data version unknown";
}

export function dataVersionOptionLabel(pkg, isDefault = false) {
  const suffixes = [];
  const smokeStatus = pkg && typeof pkg === "object" ? pkg.smoke_status : null;
  if (smokeStatus === "failed") suffixes.push("smoke failed");
  else if (smokeStatus === "passed") suffixes.push("smoke passed");
  if (isDefault) suffixes.push("default");

  const label = dataVersionLabel(pkg);
  return suffixes.length ? `${label} (${suffixes.join(", ")})` : label;
}
