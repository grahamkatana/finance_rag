import { cn } from "../lib/utils";

// Scores are 0..1 from the LLM judge. The bands are a reading aid, not a
// guarantee: below 0.5 is the API's own "potential hallucination" cut-off.
export default function ScoreBadge({ label, value }) {
  if (value == null) {
    return <span className="text-xs text-muted-foreground">{label ? `${label}: ` : ""}pending</span>;
  }
  const tone = value >= 0.8 ? "bg-emerald-500/15 text-emerald-300" : value >= 0.5 ? "bg-amber-500/15 text-amber-300" : "bg-red-500/15 text-red-300";
  return (
    <span className={cn("inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium tabular-nums", tone)}>
      {label ? `${label} ` : ""}{Math.round(value * 100)}%
    </span>
  );
}
