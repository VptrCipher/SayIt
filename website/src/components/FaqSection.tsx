import Link from "next/link";
import { SectionHeading } from "./SectionHeading";
import { PlusIcon } from "./icons";

/**
 * FAQ as native <details>/<summary> — keyboard- and screen-reader-friendly
 * with zero JavaScript. Questions and answers state only documented behavior
 * (src/lib/features.ts, platform support, release process).
 */

const FAQ_ITEMS: Array<{ question: string; answer: React.ReactNode }> = [
  {
    question: "Does my audio leave my computer?",
    answer:
      "Core dictation runs on your device via Sherpa-ONNX — no account and no API key. Optional LLM enhancement is a separate, off-by-default feature; nothing is uploaded by core dictation.",
  },
  {
    question: "Is it streaming dictation?",
    answer:
      "No. SayIt records while you hold the hotkey and transcribes once, after you release. Nothing is transcribed mid-word while you speak.",
  },
  {
    question: "Which platforms does it run on?",
    answer:
      "Windows is the primary target. Linux builds exist as AppImages but are less validated — global hotkeys may require X11 and may not work under Wayland. There is no macOS build.",
  },
  {
    question: "How large are the speech models?",
    answer:
      "Models are separate downloads, roughly 100 MB to 1 GB depending on the model you pick.",
  },
  {
    question: "Does an AI rewrite my words?",
    answer:
      "No. Corrections are deterministic local rules — no LLM, no network. Identical input, context, and settings produce identical output, and every rule can be turned off.",
  },
  {
    question: "What if text insertion fails?",
    answer:
      "The transcript stays recoverable instead of being lost, and Esc cancels while recording or transcribing.",
  },
  {
    question: "Can I see the source code?",
    answer:
      "Yes — SayIt is developed in the open under the MIT License, with the full source on GitHub.",
  },
  {
    question: "Where do downloads come from?",
    answer: (
      <>
        GitHub Releases, with published checksums. The download center reflects the latest
        published release — the{" "}
        <Link
          href="/download"
          className="font-medium text-strong underline decoration-line-strong underline-offset-2 hover:text-accent-text"
        >
          download center
        </Link>{" "}
        says exactly what exists today.
      </>
    ),
  },
];

export function FaqSection() {
  return (
    <section id="faq" aria-labelledby="faq-heading" className="scroll-mt-20">
      <SectionHeading
        center
        eyebrow="FAQ"
        title="Fair questions, straight answers"
        description="If a question is missing, the issue tracker takes it."
      />
      <div className="mt-8 grid items-start gap-3 lg:grid-cols-2">
        {FAQ_ITEMS.map((item) => (
          <details
            key={item.question}
            className="group rounded-xl border border-line bg-surface px-5 py-4 shadow-card"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-semibold text-strong [&::-webkit-details-marker]:hidden">
              {item.question}
              <span
                aria-hidden="true"
                className="text-muted transition-transform duration-[var(--motion-base)] ease-soft group-open:rotate-45"
              >
                <PlusIcon size={16} />
              </span>
            </summary>
            <p className="faq-body mt-3 text-sm leading-relaxed text-body">{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
