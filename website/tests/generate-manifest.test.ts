import { createHash } from "node:crypto";
import { mkdtemp, rm, writeFile, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { afterAll, describe, expect, it } from "vitest";
import { validateReleaseManifest } from "@/lib/release";

// The generator is a dependency-free Node script (it runs in CI); import it
// dynamically so the site's TypeScript toolchain doesn't need to type it.
const { generateReleaseManifest, stripTagPrefix, toReleaseDate } = (await import(
  "../scripts/generate-manifest.mjs"
)) as {
  generateReleaseManifest: (options: {
    tag: string;
    repo: string;
    releaseDate?: string;
    releaseFilesDir: string;
    outDir: string;
  }) => Promise<{
    manifest: {
      version: string;
      release_date: string;
      stable: boolean;
      platforms: Record<string, { url: string; sha256: string; size_bytes: number }>;
    };
    manifestPath: string;
    checksumsPath: string;
  }>;
  stripTagPrefix: (tag: string) => string;
  toReleaseDate: (iso?: string) => string;
};

const execFileAsync = promisify(execFile);
const tempDirs: string[] = [];

afterAll(async () => {
  await Promise.all(tempDirs.map((dir) => rm(dir, { recursive: true, force: true })));
});

async function makeFixtureDir(): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "sayit-manifest-"));
  tempDirs.push(dir);
  return dir;
}

async function writeArtifact(dir: string, name: string, content: string, sidecar = true) {
  await writeFile(join(dir, name), content);
  if (sidecar) {
    const hash = createHash("sha256").update(content).digest("hex");
    await writeFile(join(dir, `${name}.sha256`), `${hash.toUpperCase()}  ${name}\n`, "utf8");
  }
}

const FAKE_EXE = "fake installer bytes";
const FAKE_APPIMAGE = "fake appimage bytes";

async function writeValidFixtures(dir: string) {
  await writeArtifact(dir, "SayIt-Setup-x64.exe", FAKE_EXE);
  await writeArtifact(dir, "SayIt-v0.1.2-Linux-x86_64.AppImage", FAKE_APPIMAGE);
}

describe("release manifest generator", () => {
  it("produces a manifest the website's own validator accepts", async () => {
    const dir = await makeFixtureDir();
    const out = await makeFixtureDir();
    await writeValidFixtures(dir);

    const { manifest, manifestPath, checksumsPath } = await generateReleaseManifest({
      tag: "v0.1.2",
      repo: "VptrCipher/SayIt",
      releaseDate: "2026-10-05T12:00:00Z",
      releaseFilesDir: dir,
      outDir: out,
    });

    // The lock between CI-side generation and site-side consumption:
    expect(validateReleaseManifest(manifest)).toEqual(manifest);

    expect(manifest.version).toBe("0.1.2");
    expect(manifest.release_date).toBe("2026-10-05");
    expect(manifest.stable).toBe(true);

    const windows = manifest.platforms.windows;
    expect(windows.url).toBe(
      "https://github.com/VptrCipher/SayIt/releases/download/v0.1.2/SayIt-Setup-x64.exe",
    );
    expect(windows.size_bytes).toBe(FAKE_EXE.length);
    expect(windows.sha256).toMatch(/^[a-f0-9]{64}$/);

    const linux = manifest.platforms.linux;
    expect(linux.url).toBe(
      "https://github.com/VptrCipher/SayIt/releases/download/v0.1.2/SayIt-v0.1.2-Linux-x86_64.AppImage",
    );
    expect(linux.size_bytes).toBe(FAKE_APPIMAGE.length);

    // The written file round-trips through the validator as well.
    const fromDisk = JSON.parse(await readFile(manifestPath, "utf8"));
    expect(validateReleaseManifest(fromDisk)).not.toBeNull();

    // checksums.txt is sha256sum-compatible and matches the artifacts.
    const checksums = await readFile(checksumsPath, "utf8");
    const lines = checksums.trim().split("\n");
    expect(lines).toHaveLength(2);
    const exeHash = createHash("sha256").update(FAKE_EXE).digest("hex");
    expect(lines[0]).toBe(`${exeHash}  SayIt-Setup-x64.exe`);
  });

  it("fails when a platform artifact is missing (no partial releases)", async () => {
    const dir = await makeFixtureDir();
    const out = await makeFixtureDir();
    await writeArtifact(dir, "SayIt-Setup-x64.exe", FAKE_EXE);

    await expect(
      generateReleaseManifest({
        tag: "v0.1.2",
        repo: "VptrCipher/SayIt",
        releaseFilesDir: dir,
        outDir: out,
      }),
    ).rejects.toThrow(/AppImage artifact missing/i);
  });

  it("fails when an artifact does not match its own .sha256 sidecar", async () => {
    const dir = await makeFixtureDir();
    const out = await makeFixtureDir();
    await writeArtifact(dir, "SayIt-Setup-x64.exe", FAKE_EXE, false);
    await writeFile(
      join(dir, "SayIt-Setup-x64.exe.sha256"),
      `${"0".repeat(64)}  SayIt-Setup-x64.exe\n`,
      "utf8",
    );
    await writeArtifact(dir, "SayIt-v0.1.2-Linux-x86_64.AppImage", FAKE_APPIMAGE);

    await expect(
      generateReleaseManifest({
        tag: "v0.1.2",
        repo: "VptrCipher/SayIt",
        releaseFilesDir: dir,
        outDir: out,
      }),
    ).rejects.toThrow(/SHA-256 mismatch/i);
  });

  it("fails on a version mismatch between tag and artifact name", async () => {
    const dir = await makeFixtureDir();
    const out = await makeFixtureDir();
    await writeArtifact(dir, "SayIt-Setup-x64.exe", FAKE_EXE);
    await writeArtifact(dir, "SayIt-v9.9.9-Linux-x86_64.AppImage", FAKE_APPIMAGE);

    await expect(
      generateReleaseManifest({
        tag: "v0.1.2",
        repo: "VptrCipher/SayIt",
        releaseFilesDir: dir,
        outDir: out,
      }),
    ).rejects.toThrow(/Version mismatch/i);
  });

  it("exits nonzero from the CLI on failure — CI gates on this", async () => {
    const dir = await makeFixtureDir();
    const out = await makeFixtureDir();
    await writeArtifact(dir, "SayIt-Setup-x64.exe", FAKE_EXE); // no AppImage

    const scriptPath = join(process.cwd(), "scripts", "generate-manifest.mjs");
    await expect(
      execFileAsync(process.execPath, [
        scriptPath,
        "--tag",
        "v0.1.2",
        "--repo",
        "VptrCipher/SayIt",
        "--release-files",
        dir,
        "--out",
        out,
      ]),
    ).rejects.toMatchObject({ code: 1 });
  });
});

describe("manifest helper functions", () => {
  it("strips the v prefix from tags", () => {
    expect(stripTagPrefix("v0.1.2")).toBe("0.1.2");
    expect(stripTagPrefix("0.2.0")).toBe("0.2.0");
  });

  it("normalizes release dates and defaults to today", () => {
    expect(toReleaseDate("2026-10-05T12:00:00Z")).toBe("2026-10-05");
    expect(toReleaseDate("2026-10-05")).toBe("2026-10-05");
    expect(toReleaseDate(undefined)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(() => toReleaseDate("October 3rd")).toThrow(/Unrecognized release date/);
  });
});
