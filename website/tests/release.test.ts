import { describe, expect, it, vi } from "vitest";
import {
  fetchReleaseManifest,
  formatBytes,
  validateReleaseManifest,
  type ReleaseManifest,
} from "@/lib/release";

const VALID_MANIFEST: ReleaseManifest = {
  version: "0.1.2",
  release_date: "2026-10-05",
  stable: true,
  platforms: {
    windows: {
      architecture: "x64",
      format: "exe",
      url: "https://github.com/VptrCipher/SayIt/releases/download/v0.1.2/SayIt-Setup-x64.exe",
      sha256: "a".repeat(64),
      size_bytes: 503316480,
    },
    linux: {
      architecture: "x86_64",
      format: "AppImage",
      url: "https://github.com/VptrCipher/SayIt/releases/download/v0.1.2/SayIt-0.1.2-Linux-x86_64.AppImage",
    },
  },
};

describe("validateReleaseManifest", () => {
  it("accepts a well-formed manifest", () => {
    expect(validateReleaseManifest(VALID_MANIFEST)).toEqual(VALID_MANIFEST);
  });

  it("allows an empty platforms object (release exists, cards degrade honestly)", () => {
    const manifest = { ...VALID_MANIFEST, platforms: {} };
    expect(validateReleaseManifest(manifest)).toMatchObject({ version: "0.1.2" });
  });

  it("allows unknown extra keys for forward compatibility", () => {
    const manifest = { ...VALID_MANIFEST, beta_channel: { version: "0.2.0-rc1" } };
    expect(validateReleaseManifest(manifest)).not.toBeNull();
  });

  it.each([
    ["missing version", { ...VALID_MANIFEST, version: undefined }],
    ["bad version", { ...VALID_MANIFEST, version: "not-a-version" }],
    ["missing release date", { ...VALID_MANIFEST, release_date: undefined }],
    ["bad release date", { ...VALID_MANIFEST, release_date: "October 3rd" }],
    ["missing stable flag", { ...VALID_MANIFEST, stable: undefined }],
    ["non-boolean stable", { ...VALID_MANIFEST, stable: "yes" }],
    ["missing platforms", { ...VALID_MANIFEST, platforms: undefined }],
    ["null platforms", { ...VALID_MANIFEST, platforms: null }],
  ])("rejects %s", (_label, bad) => {
    expect(validateReleaseManifest(bad)).toBeNull();
  });

  it.each([
    ["http asset url", { windows: { ...VALID_MANIFEST.platforms.windows, url: "http://example.com/x.exe" } }],
    ["unknown format", { windows: { ...VALID_MANIFEST.platforms.windows, format: "msi" } }],
    ["empty architecture", { windows: { ...VALID_MANIFEST.platforms.windows, architecture: "" } }],
    [
      "bad sha256",
      { windows: { ...VALID_MANIFEST.platforms.windows, sha256: "deadbeef" } },
    ],
    ["negative size", { windows: { ...VALID_MANIFEST.platforms.windows, size_bytes: -1 } }],
    [
      "non-numeric size",
      { windows: { ...VALID_MANIFEST.platforms.windows, size_bytes: "480 MB" } },
    ],
  ])("rejects a platform asset with %s", (label, platforms) => {
    expect(validateReleaseManifest({ ...VALID_MANIFEST, platforms })).toBeNull();
    void label;
  });

  it("rejects non-objects and garbage", () => {
    expect(validateReleaseManifest(null)).toBeNull();
    expect(validateReleaseManifest("0.1.2")).toBeNull();
    expect(validateReleaseManifest(42)).toBeNull();
  });

  it("rejects non-https notes/changelog urls", () => {
    expect(validateReleaseManifest({ ...VALID_MANIFEST, notes_url: "http://x.example" })).toBeNull();
    expect(
      validateReleaseManifest({ ...VALID_MANIFEST, changelog_url: "not a url" }),
    ).toBeNull();
  });
});

describe("fetchReleaseManifest", () => {
  it("returns ok with the validated manifest", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => VALID_MANIFEST,
    })) as unknown as typeof fetch;
    const result = await fetchReleaseManifest(fetchImpl);
    expect(result).toEqual({ status: "ok", manifest: VALID_MANIFEST });
  });

  it("treats a missing file as the no-release state", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false })) as unknown as typeof fetch;
    expect(await fetchReleaseManifest(fetchImpl)).toEqual({
      status: "unavailable",
      reason: "missing",
    });
  });

  it("treats malformed JSON as invalid rather than crashing", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => {
        throw new Error("Unexpected token");
      },
    })) as unknown as typeof fetch;
    expect(await fetchReleaseManifest(fetchImpl)).toEqual({
      status: "unavailable",
      reason: "invalid",
    });
  });

  it("treats an invalid manifest as invalid rather than rendering it", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => ({ version: "nope" }),
    })) as unknown as typeof fetch;
    expect(await fetchReleaseManifest(fetchImpl)).toEqual({
      status: "unavailable",
      reason: "invalid",
    });
  });

  it("maps network failures to the network reason", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    }) as unknown as typeof fetch;
    expect(await fetchReleaseManifest(fetchImpl)).toEqual({
      status: "unavailable",
      reason: "network",
    });
  });
});

describe("formatBytes", () => {
  it("formats megabytes with one decimal under 100 MB", () => {
    expect(formatBytes(157286400)).toBe("150 MB");
    expect(formatBytes(52_428_800)).toBe("50 MB");
    expect(formatBytes(47_185_920)).toBe("45 MB");
  });

  it("rounds large installers to whole megabytes", () => {
    expect(formatBytes(503316480)).toBe("480 MB");
    expect(formatBytes(1_073_741_824)).toBe("1024 MB");
  });
});
