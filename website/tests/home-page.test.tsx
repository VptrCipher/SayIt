import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import HomePage from "@/app/page";
import { site } from "@/lib/site";

describe("Home page (landing redesign)", () => {
  it("renders the product headline", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { level: 1, name: /your voice/i })).toBeInTheDocument();
  });

  it("anchors every download CTA to the download center and the secondary to how-it-works", () => {
    render(<HomePage />);
    const downloadLinks = screen.getAllByRole("link", { name: "Download SayIt" });
    expect(downloadLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of downloadLinks) {
      expect(link).toHaveAttribute("href", "/download");
    }
    expect(screen.getByRole("link", { name: "See how it works" })).toHaveAttribute(
      "href",
      "#how-it-works",
    );
  });

  it("links only to real destinations", () => {
    render(<HomePage />);
    const downloadCenterLinks = screen.getAllByRole("link", { name: "download center" });
    expect(downloadCenterLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of downloadCenterLinks) {
      expect(link).toHaveAttribute("href", "/download");
    }
    expect(screen.getByRole("link", { name: "Explore all features →" })).toHaveAttribute(
      "href",
      "/features",
    );
    expect(screen.getByRole("link", { name: /read the privacy notes/i })).toHaveAttribute(
      "href",
      "/privacy",
    );
    expect(screen.getAllByRole("link", { name: /source/i }).length).toBeGreaterThan(0);
  });

  it("shows the live release announcement and official artifact links", () => {
    render(<HomePage />);
    expect(
      screen.getByText("The latest SayIt release is live for Windows and Linux."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download SayIt" })).toHaveAttribute(
      "href",
      "/download",
    );
  });

  it("credits GitHub as the artifact home", () => {
    render(<HomePage />);
    expect(screen.getByRole("link", { name: "source" })).toHaveAttribute(
      "href",
      site.repositoryUrl,
    );
    expect(screen.getByRole("link", { name: /release artifacts/i })).toHaveAttribute(
      "href",
      site.releasesUrl,
    );
  });

  it("shows the four how-it-works steps in order", () => {
    render(<HomePage />);
    const section = document.getElementById("how-it-works");
    expect(section).not.toBeNull();
    const steps = within(section as HTMLElement).getAllByRole("listitem");
    expect(steps).toHaveLength(4);
    expect(steps[0].textContent).toMatch(/hold the hotkey/i);
    expect(steps[3].textContent).toMatch(/text at your cursor/i);
  });

  it("reports platform support honestly", () => {
    render(<HomePage />);
    const section = document.getElementById("platforms");
    expect(section).not.toBeNull();
    const items = within(section as HTMLElement).getAllByRole("listitem").map(
      (item) => item.textContent ?? "",
    );
    const windows = items.find((text) => text.startsWith("Windows"));
    const linux = items.find((text) => text.startsWith("Linux"));
    const macos = items.find((text) => text.startsWith("macOS"));

    expect(windows).toMatch(/supported/i);
    expect(linux).toMatch(/partially supported/i);
    expect(linux).toMatch(/wayland/i);
    expect(macos).toMatch(/not supported/i);
    expect(macos).toMatch(/no macos build/i);
  });

  it("routes download intent to the download center, without per-platform artifact buttons", () => {
    render(<HomePage />);
    expect(screen.queryByText(/download for (windows|linux)/i)).not.toBeInTheDocument();
  });

  it("does not hardcode a version number in the homepage", () => {
    const { container } = render(<HomePage />);
    expect(container.textContent ?? "").not.toMatch(/v?\d+\.\d+\.\d+/);
  });

  it("the hero demo resolves to the three documented corrections", () => {
    const { container } = render(<HomePage />);
    const result = container.querySelector(".demo-phase-result");
    expect(result).not.toBeNull();
    const text = result?.textContent ?? "";
    expect(text).toContain("GitHub");
    expect(text).toContain("Next.js");
    expect(text).toContain("getUserById");
    expect(text).toContain("Inserted at your cursor");
    // Transient phases stay decorative — the raw utterance must not read as page copy.
    expect(container.querySelector(".demo-phase-record")).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector(".demo-phase-transcribe")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("the FAQ renders as native disclosure elements", () => {
    const { container } = render(<HomePage />);
    const items = container.querySelectorAll("details");
    expect(items.length).toBeGreaterThanOrEqual(6);
    const first = items[0]?.querySelector("summary");
    expect(first?.textContent).toMatch(/audio leave my computer/i);
  });

  it("the profile tabs switch panels after hydration and keep all content in the DOM", () => {
    render(<HomePage />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(3);

    // All three panels exist in the DOM. Hidden panels carry no computed
    // accessible name, so identify them by their stable aria-labelledby
    // suffix rather than by name.
    const panels = screen.getAllByRole("tabpanel", { hidden: true });
    expect(panels).toHaveLength(3);
    const panelFor = (profile: string) =>
      panels.find((panel) =>
        panel.getAttribute("aria-labelledby")?.endsWith(`-tab-${profile}`),
      );
    const developerPanel = panelFor("developer");
    const emailPanel = panelFor("email");
    const chatPanel = panelFor("chat");
    expect(developerPanel).toBeDefined();
    expect(emailPanel).toBeDefined();
    expect(chatPanel).toBeDefined();

    // After hydration exactly one panel is visible.
    expect(developerPanel).not.toHaveAttribute("hidden");
    expect(emailPanel).toHaveAttribute("hidden");
    expect(chatPanel).toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("tab", { name: "Email client" }));

    expect(emailPanel).not.toHaveAttribute("hidden");
    expect(developerPanel).toHaveAttribute("hidden");
    expect(chatPanel).toHaveAttribute("hidden");
    expect(screen.getByRole("tab", { name: "Email client" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(emailPanel).toHaveTextContent("I'll arrive at six.");
  });
});
