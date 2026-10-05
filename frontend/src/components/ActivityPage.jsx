import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "./ui/Table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/Dialog";
import ScoreBadge from "./ScoreBadge";
import { cn } from "../lib/utils";
import { formatDate, formatDuration, formatBytes } from "../lib/format";
import { fetchQueryEvents, fetchIngestionEvents, UnauthorizedError } from "../api/client";

const PAGE_SIZE = 25;
const TABS = [
  { key: "queries", label: "Questions" },
  { key: "ingestions", label: "Uploads" },
];

export default function ActivityPage({ user, onSessionExpired }) {
  const [tab, setTab] = useState("queries");
  const [filter, setFilter] = useState(""); // queries: "low" | "" ; ingestions: "success" | "error" | ""
  const [offset, setOffset] = useState(0);
  const [events, setEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const page = { limit: PAGE_SIZE, offset };
      setEvents(
        tab === "queries"
          ? await fetchQueryEvents({ ...page, max_faithfulness: filter === "low" ? 0.5 : null })
          : await fetchIngestionEvents({ ...page, status: filter })
      );
    } catch (err) {
      if (err instanceof UnauthorizedError) return onSessionExpired();
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [tab, filter, offset, onSessionExpired]);

  useEffect(() => {
    load();
  }, [load]);

  const switchTab = (key) => {
    setTab(key);
    setFilter("");
    setOffset(0);
    setEvents([]);
  };
  const changeFilter = (value) => {
    setFilter(value);
    setOffset(0);
  };

  return (
    <div className="thin-scrollbar min-h-0 min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
      <div className="mb-6">
        <h1 className="font-display text-xl font-semibold text-foreground">Activity</h1>
        <p className="text-sm text-muted-foreground">
          {user?.is_admin ? "Every question and upload across all users, " : "Your questions and uploads, "}
          with the quality scores a second model gave each answer.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-lg border border-border bg-muted/50 p-0.5">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => switchTab(t.key)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                tab === t.key ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <select
          value={filter}
          onChange={(e) => changeFilter(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {tab === "queries" ? (
            <>
              <option value="">All answers</option>
              <option value="low">Low faithfulness (50% or less)</option>
            </>
          ) : (
            <>
              <option value="">All uploads</option>
              <option value="success">Succeeded</option>
              <option value="error">Failed</option>
            </>
          )}
        </select>
      </div>

      {error && <p className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      {tab === "queries" ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Question</TableHead>
              <TableHead>Faithfulness</TableHead>
              <TableHead>Relevance</TableHead>
              <TableHead>Took</TableHead>
              {user?.is_admin && <TableHead>User</TableHead>}
              <TableHead>When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((e) => (
              <TableRow key={e.id} className="cursor-pointer" onClick={() => setSelected(e)}>
                <TableCell className="max-w-sm truncate font-medium text-foreground" title={e.query}>{e.query}</TableCell>
                <TableCell><ScoreBadge value={e.faithfulness_score} /></TableCell>
                <TableCell><ScoreBadge value={e.relevance_score} /></TableCell>
                <TableCell className="whitespace-nowrap tabular-nums text-muted-foreground">{formatDuration(e.duration_ms)}</TableCell>
                {user?.is_admin && <TableCell className="tabular-nums text-muted-foreground">#{e.client_id}</TableCell>}
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(e.created_at)}</TableCell>
              </TableRow>
            ))}
            <EmptyRow show={!isLoading && events.length === 0} colSpan={user?.is_admin ? 6 : 5} />
          </TableBody>
        </Table>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Chunks</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Took</TableHead>
              {user?.is_admin && <TableHead>User</TableHead>}
              <TableHead>When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="font-medium text-foreground">
                  <span className="break-all">{e.file_name}</span>
                  {e.error_message && <p className="mt-0.5 text-xs font-normal text-destructive">{e.error_message}</p>}
                </TableCell>
                <TableCell>
                  <Badge variant={e.status === "success" ? "accent" : "destructive"}>{e.status === "success" ? "Succeeded" : "Failed"}</Badge>
                </TableCell>
                <TableCell className="tabular-nums text-muted-foreground">{e.chunks_ingested}</TableCell>
                <TableCell className="whitespace-nowrap tabular-nums text-muted-foreground">{formatBytes(e.file_size_bytes)}</TableCell>
                <TableCell className="whitespace-nowrap tabular-nums text-muted-foreground">{formatDuration(e.duration_ms)}</TableCell>
                {user?.is_admin && <TableCell className="tabular-nums text-muted-foreground">#{e.client_id}</TableCell>}
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(e.created_at)}</TableCell>
              </TableRow>
            ))}
            <EmptyRow show={!isLoading && events.length === 0} colSpan={user?.is_admin ? 7 : 6} />
          </TableBody>
        </Table>
      )}

      <div className="mt-4 flex items-center justify-end gap-2">
        <span className="text-xs text-muted-foreground">
          {events.length > 0 ? `${offset + 1}–${offset + events.length}` : ""}
        </span>
        <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
          <ChevronLeft className="h-3.5 w-3.5" />
        </Button>
        {/* The API returns no overall count, so a full page is the only sign there may be more. */}
        <Button variant="outline" size="sm" disabled={events.length < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}>
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle className="pr-6">{selected?.query}</DialogTitle>
            <DialogDescription>
              {formatDate(selected?.created_at)} · {selected?.model_used} · {formatDuration(selected?.duration_ms)}
            </DialogDescription>
          </DialogHeader>
          <div className="mt-3 flex flex-wrap gap-2">
            <ScoreBadge label="Faithful to sources" value={selected?.faithfulness_score} />
            <ScoreBadge label="Sources relevant" value={selected?.relevance_score} />
          </div>
          <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground">{selected?.answer}</p>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function EmptyRow({ show, colSpan }) {
  if (!show) return null;
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="py-8 text-center text-muted-foreground">Nothing here yet.</TableCell>
    </TableRow>
  );
}
