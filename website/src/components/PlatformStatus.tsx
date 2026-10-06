type PlatformStatusProps = {
  className?: string;
};

type BadgeTone = "positive" | "neutral" | "off";

const BADGE_CLASSES: Record<BadgeTone, string> = {
  positive: "border-accent bg-accent text-on-accent",
  neutral: "border-line-strong bg-surface text-body",
  off: "border-line bg-subtle text-muted",
};

type Platform = {
  name: string;
  status: string;
  tone: BadgeTone;
  note: string;
};

// Evidence-backed statuses from the project README's platform-support table.
// The calm red is deliberately NOT used here — it is reserved for the
// recording state in both the desktop app and this site.
const PLATFORMS: Platform[] = [
  {
    name: "Windows",
    status: "Supported",
    tone: "positive",
    note: "Primary target. The automated test suite runs on Windows; packaged-install validation is still in progress.",
  },
  {
    name: "Linux",
    status: "Partially supported",
    tone: "neutral",
    note: "AppImage releases are packaged with a self-contained PortAudio runtime and verified by a packaged launch smoke test. Global hotkeys may require X11 and clipboard insertion needs xclip.",
  },
  {
    name: "macOS",
    status: "Not supported",
    tone: "off",
    note: "No macOS build exists today. If that changes, it will appear here alongside real download artifacts.",
  },
];

export function PlatformStatus({ className = "" }: PlatformStatusProps) {
  return (
    <ul className={`space-y-3 ${className}`.trim()}>
      {PLATFORMS.map((platform) => (
        <li
          key={platform.name}
          className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-5 shadow-card sm:flex-row sm:items-center sm:justify-between sm:gap-6"
        >
          <div className="flex shrink-0 items-center gap-3">
            <span className="text-base font-semibold text-strong">{platform.name}</span>
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${BADGE_CLASSES[platform.tone]}`}
            >
              {platform.status}
            </span>
          </div>
          <p className="text-sm leading-relaxed text-muted sm:max-w-md sm:text-right">
            {platform.note}
          </p>
        </li>
      ))}
    </ul>
  );
}
