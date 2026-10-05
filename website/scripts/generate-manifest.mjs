/**
 * Release manifest generator (master plan §11, §38, §40, §41, §83).
 *
 * Turns actual release artifacts into the machine-readable manifest the
 * website's download center consumes (`/release-manifest.json`), plus a
 * combined `checksums.txt`. Runs in CI (release job) and locally against
 * fixture files.
 *
 * Fail-fast rules (§40 — no partial releases are ever described):
 *   - both a Windows installer and a Linux AppImage must be present
 *   - computed SHA-256 must match any existing `<artifact>.sha256` sidecar
 *   - version must be valid semver and, when the AppImage name encodes a
 *     version (SayIt-v<version>-Linux-x86_64.AppImage), it must match
 *   - asset URLs must be https
 *
 * Output files are written to --out and are meant to be uploaded as release
 * assets; the site deployment (Stage F) serves the manifest at its root.
 */

import { createHash } from "node:crypto";
import { createReadStream, realpathSync } from "node:fs";
import { mkdir, readdir, readFile, stat, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { fileURLToPath } from "node:url";
import { pipeline } from "node:stream/promises";

const VERSION_PATTERN = /^\d+\.\d+\.\d+(?:[-+][\w.-]+)?$/;
const SHA256_PATTERN = /^[a-f0-9]{64}$/i;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export function stripTagPrefix(tag) {
  return tag.startsWith("v") ? tag.slice(1) : tag;
}

/** Accepts an ISO timestamp or YYYY-MM-DD; falls back to today (UTC). */
export function toReleaseDate(iso) {
  if (!iso) return new Date().toISOString().slice(0, 10);
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(iso.trim());
  if (!match) throw new Error(`Unrecognized release date: "${iso}"`);
  return match[1];
}

async function sha256File(filePath) {
  const hash = createHash("sha256");
  await pipeline(createReadStream(filePath), hash);
  return hash.digest("hex");
}

async function verifySidecar(filePath, computed) {
  const sidecarPath = `${filePath}.sha256`;
  let sidecar;
  try {
    sidecar = await readFile(sidecarPath, "utf8");
  } catch {
    return; // no sidecar — nothing to cross-check
  }
  const match = /([a-f0-9]{64})/i.exec(sidecar);
  if (!match) throw new Error(`Sidecar ${basename(sidecarPath)} contains no SHA-256 hash`);
  if (match[1].toLowerCase() !== computed) {
    throw new Error(
      `SHA-256 mismatch for ${basename(filePath)}: sidecar says ${match[1].toLowerCase()}, computed ${computed}. ` +
        "Refusing to describe a release that does not match its own checksums.",
    );
  }
}

function findSingleFile(files, extension) {
  const matches = files.filter((name) => name.toLowerCase().endsWith(extension));
  if (matches.length === 0) {
    throw new Error(`Required ${extension} artifact missing from release files (§40: no partial releases)`);
  }
  if (matches.length > 1) {
    throw new Error(`Expected exactly one ${extension} artifact, found ${matches.length}`);
  }
  return matches[0];
}

/**
 * @param {{
 *   tag: string,
 *   repo: string,
 *   releaseDate?: string,
 *   releaseFilesDir: string,
 *   outDir: string,
 * }} options
 */
export async function generateReleaseManifest(options) {
  const { tag, repo, releaseDate, releaseFilesDir, outDir } = options;

  if (!tag || typeof tag !== "string") throw new Error("--tag is required (e.g. v0.1.2)");
  const version = stripTagPrefix(tag);
  if (!VERSION_PATTERN.test(version)) {
    throw new Error(`Tag "${tag}" does not yield a valid semver version ("${version}")`);
  }
  if (!repo || typeof repo !== "string") throw new Error("--repo is required (e.g. owner/name)");
  const date = toReleaseDate(releaseDate);
  if (!DATE_PATTERN.test(date)) throw new Error(`Invalid release date: "${date}"`);

  const files = (await readdir(releaseFilesDir)).filter((name) => !name.startsWith("."));
  const exeName = findSingleFile(files, ".exe");
  const appImageName = findSingleFile(files, ".appimage");

  // §41 — version consistency where the artifact name encodes it.
  const appImageVersion = /^SayIt-(.+)-Linux-x86_64\.AppImage$/i.exec(appImageName);
  if (appImageVersion && appImageVersion[1] !== `v${version}` && appImageVersion[1] !== version) {
    throw new Error(
      `Version mismatch: tag ${tag} but artifact is named ${appImageName} (§41)`,
    );
  }

  const assets = [
    { key: "windows", file: exeName, architecture: "x64", format: "exe" },
    { key: "linux", file: appImageName, architecture: "x86_64", format: "AppImage" },
  ];

  const platforms = {};
  const checksumLines = [];

  for (const asset of assets) {
    const filePath = join(releaseFilesDir, asset.file);
    const info = await stat(filePath);
    if (!info.isFile()) throw new Error(`${asset.file} is not a file`);
    if (info.size <= 0) throw new Error(`${asset.file} is empty`);

    const sha256 = await sha256File(filePath);
    await verifySidecar(filePath, sha256);
    if (!SHA256_PATTERN.test(sha256)) throw new Error(`Computed hash for ${asset.file} is malformed`);

    const url = `https://github.com/${repo}/releases/download/${tag}/${asset.file}`;
    if (!url.startsWith("https://")) throw new Error(`Refusing non-https asset URL: ${url}`);

    platforms[asset.key] = {
      architecture: asset.architecture,
      format: asset.format,
      url,
      sha256,
      size_bytes: info.size,
    };
    checksumLines.push(`${sha256}  ${asset.file}`);
  }

  const manifest = {
    version,
    release_date: date,
    stable: true,
    platforms,
  };

  await mkdir(outDir, { recursive: true });
  const manifestPath = join(outDir, "release-manifest.json");
  const checksumsPath = join(outDir, "checksums.txt");
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  await writeFile(checksumsPath, `${checksumLines.join("\n")}\n`, "utf8");

  return { manifest, manifestPath, checksumsPath };
}

function parseArgs(argv) {
  const args = {};
  for (let index = 2; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag.startsWith("--") || value === undefined) {
      throw new Error(`Invalid arguments. Usage: generate-manifest.mjs --tag v0.1.0 --repo owner/name --release-date 2026-10-03 --release-files <dir> --out <dir>`);
    }
    args[flag.slice(2)] = value;
  }
  return args;
}

async function main() {  let args;
  try {
    args = parseArgs(process.argv);
  } catch (error) {
    console.error(String(error.message ?? error));
    process.exitCode = 1;
    return;
  }

  try {
    const result = await generateReleaseManifest({
      tag: args.tag,
      repo: args.repo,
      releaseDate: args["release-date"],
      releaseFilesDir: args["release-files"],
      outDir: args.out,
    });
    console.log(`Wrote ${result.manifestPath}`);
    console.log(`Wrote ${result.checksumsPath}`);
    console.log(JSON.stringify(result.manifest, null, 2));
  } catch (error) {
    console.error(`generate-manifest: ${String(error.message ?? error)}`);
    process.exitCode = 1;
  }
}

// Entry-point detection: only run the CLI when executed directly.
const isMain = (() => {
  try {
    return realpathSync(process.argv[1]) === fileURLToPath(import.meta.url);
  } catch {
    return false;
  }
})();

if (isMain) {
  await main();
}
