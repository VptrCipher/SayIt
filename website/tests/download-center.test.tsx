import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { DownloadCenter } from "@/components/DownloadCenter";
import type { ReleaseManifest } from "@/lib/release";
import { site } from "@/lib/site";

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

function stubFetch(implementation: () => Promise<unknown>) {
  vi.stubGlobal("fetch", vi.fn(implementation));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DownloadCenter — no published manifest available", () => {
  it("shows the honest no-release state with working GitHub fallbacks", async () => {
    stubFetch(async () => ({ ok: false }));

    render(<DownloadCenter platform="windows" />);

    await waitFor(() => {
      expect(
        screen.getByText(/no published release manifest is available right now/i),
      ).toBeInTheDocument();
    });

    const cards = screen.getAllByRole("heading", { level: 3 });
    expect(cards.map((card) => card.textContent)).toEqual(["Windows", "Linux"]);
    expect(screen.getAllByRole("link", { name: "View GitHub releases" })).toHaveLength(2);
    for (const link of screen.getAllByRole("link", { name: "View GitHub releases" })) {
      expect(link).toHaveAttribute("href", site.releasesUrl);
    }
  });

  it("orders the detected platform first and marks it", async () => {
    stubFetch(async () => ({ ok: false }));

    const { container } = render(<DownloadCenter platform="linux" />);

    await waitFor(() => {
      expect(container.querySelectorAll("h3").length).toBe(2);
    });
    const headings = [...container.querySelectorAll("h3")].map((h) => h.textContent);
    expect(headings).toEqual(["Linux", "Windows"]);
    expect(screen.getAllByText("For your system")).toHaveLength(1);
  });

  it("shows no version numbers when nothing is released", async () => {
    stubFetch(async () => ({ ok: false }));

    const { container } = render(<DownloadCenter platform="windows" />);

    await waitFor(() => {
      expect(container.querySelectorAll("h3").length).toBe(2);
    });
    expect(container.textContent ?? "").not.toMatch(/v?\d+\.\d+\.\d+/);
  });

  it("never renders a macOS download card, and says macOS is unsupported", async () => {
    stubFetch(async () => ({ ok: false }));

    render(<DownloadCenter platform="macos" />);

    await waitFor(() => {
      expect(screen.getByText(/macOS support is not currently available/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "View supported platforms" })).toHaveAttribute(
      "href",
      "/#platforms",
    );
    expect(screen.queryByText(/download for macos/i)).not.toBeInTheDocument();
    const cards = screen.getAllByRole("heading", { level: 3 });
    expect(cards.map((card) => card.textContent)).not.toContain("macOS");
  });
});

describe("DownloadCenter — release available", () => {
  it("renders cards from the manifest with real data", async () => {
    stubFetch(async () => ({ ok: true, json: async () => VALID_MANIFEST }));

    render(<DownloadCenter platform="windows" />);

    await waitFor(() => {
      expect(screen.getByText("v0.1.2")).toBeInTheDocument();
    });

    const windowsDownload = screen.getByRole("link", { name: "Download for Windows" });
    expect(windowsDownload).toHaveAttribute("href", VALID_MANIFEST.platforms.windows?.url);
    const linuxDownload = screen.getByRole("link", { name: "Download for Linux" });
    expect(linuxDownload).toHaveAttribute("href", VALID_MANIFEST.platforms.linux?.url);

    // The banner and both cards each show the release date.
    expect(screen.getAllByText(/Released 2026-10-05/)).toHaveLength(3);

    expect(screen.getByText("Download size: 480 MB")).toBeInTheDocument();
    expect(screen.getByText(/SHA-256/i)).toBeInTheDocument();
    expect(screen.getByText("a".repeat(64))).toBeInTheDocument();
  });

  it("shows no size line for assets without a measured size", async () => {
    stubFetch(async () => ({ ok: true, json: async () => VALID_MANIFEST }));

    render(<DownloadCenter platform="linux" />);

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Download for Linux" })).toBeInTheDocument();
    });
    expect(screen.getByText("Download size: 480 MB")).toBeInTheDocument();
    expect(screen.queryByText(/Download size: 150 MB/)).not.toBeInTheDocument();
  });

  it("degrades a missing platform asset to the unavailable card instead of a broken button", async () => {
    const partial = { ...VALID_MANIFEST, platforms: { linux: VALID_MANIFEST.platforms.linux } };
    stubFetch(async () => ({ ok: true, json: async () => partial }));

    render(<DownloadCenter platform="windows" />);

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Download for Linux" })).toBeInTheDocument();
    });
    expect(screen.getAllByText(/temporarily unavailable/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Download for Windows" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View GitHub releases" })).toHaveAttribute(
      "href",
      site.releasesUrl,
    );
  });
});

describe("DownloadCenter — failure states", () => {
  it("offers retry and GitHub on network failure", async () => {
    stubFetch(async () => {
      throw new Error("ECONNREFUSED");
    });

    render(<DownloadCenter platform="windows" />);

    await waitFor(() => {
      expect(screen.getByText(/couldn.t check for releases right now/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "GitHub Releases" })).toHaveAttribute(
      "href",
      site.releasesUrl,
    );
  });

  it("falls back instead of rendering an invalid manifest", async () => {
    stubFetch(async () => ({ ok: true, json: async () => ({ version: "garbage" }) }));

    render(<DownloadCenter platform="windows" />);

    await waitFor(() => {
      expect(
        screen.getByText(/release information is temporarily unavailable/i),
      ).toBeInTheDocument();
    });
  });
});
