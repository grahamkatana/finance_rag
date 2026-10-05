import { X, FileText } from "lucide-react";
import { Button } from "./ui/Button";

export default function SourcePanel({ source, onClose }) {
  if (!source) return null;
  const { index, chunk } = source;

  return (
    <aside className="fixed inset-0 z-50 flex shrink-0 flex-col bg-card md:static md:z-auto md:h-full md:w-96 md:border-l md:border-border">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Source {index}</h2>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} title="Close">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="thin-scrollbar flex-1 space-y-3 overflow-y-auto p-4">
        <p className="flex items-start gap-2 text-sm font-medium text-foreground break-all">
          <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          {chunk.file_name}
        </p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <dt>Chunk</dt><dd className="tabular-nums">{chunk.chunk_index}</dd>
          <dt>From</dt><dd className="break-all">{chunk.source}</dd>
          <dt>Match score</dt><dd className="tabular-nums">{chunk.score.toFixed(4)}</dd>
        </dl>
        <p className="whitespace-pre-wrap border-t border-border pt-3 text-sm leading-relaxed text-foreground">{chunk.chunk_text}</p>
      </div>
    </aside>
  );
}
