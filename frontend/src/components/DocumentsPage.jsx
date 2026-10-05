import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, Trash2, Share2, FileText, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { Input } from "./ui/Input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "./ui/Table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/Dialog";
import ShareDialog from "./ShareDialog";
import { formatDate } from "../lib/format";
import { fetchDocuments, uploadDocument, deleteDocument, UnauthorizedError } from "../api/client";

export default function DocumentsPage({ user, onSessionExpired }) {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [shareTarget, setShareTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleError = useCallback((err) => {
    if (err instanceof UnauthorizedError) onSessionExpired();
    else setError(err.message);
  }, [onSessionExpired]);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDocuments(await fetchDocuments());
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleError]);

  useEffect(() => {
    load();
  }, [load]);

  const confirmDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteDocument(deleteTarget.file_name);
      setDeleteTarget(null);
      await load();
    } catch (err) {
      setDeleteTarget(null);
      handleError(err);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="thin-scrollbar min-h-0 min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-xl font-semibold text-foreground">Documents</h1>
          <p className="text-sm text-muted-foreground">PDFs you've uploaded or that have been shared with you. Answers draw only on these.</p>
        </div>
        <Button onClick={() => setUploadOpen(true)} className="shrink-0 gap-1.5">
          <Upload className="h-3.5 w-3.5" /> Upload PDF
        </Button>
      </div>

      {error && <p className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : documents.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-6 py-12 text-center">
          <FileText className="mx-auto h-8 w-8 text-muted-foreground/60" />
          <p className="mt-3 text-sm font-medium text-foreground">No documents yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Upload an annual report, 10-K or other financial PDF to start asking questions.</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Chunks</TableHead>
              <TableHead>Added</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((d) => {
              // Sharing is the owner's call; deleting is the owner's or an
              // admin's. (An older API without the flag is treated as "yours".)
              const isOwner = d.is_owner !== false;
              const canDelete = isOwner || user?.is_admin;
              return (
              <TableRow key={d.file_name}>
                <TableCell className="min-w-56 font-medium text-foreground">
                  <span className="flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <span className="break-all">{d.file_name}</span>
                    {!isOwner && (
                      <Badge variant="secondary" className="shrink-0 whitespace-nowrap">
                        {user?.is_admin ? "Another user's" : "Shared with you"}
                      </Badge>
                    )}
                  </span>
                </TableCell>
                <TableCell className="max-w-xs truncate text-muted-foreground" title={d.source}>{d.source}</TableCell>
                <TableCell className="tabular-nums text-muted-foreground">{d.chunk_count}</TableCell>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(d.created_at)}</TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    {isOwner && (
                      <Button variant="ghost" size="icon" className="h-8 w-8" title="Share" onClick={() => setShareTarget(d)}>
                        <Share2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {canDelete && (
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" title="Delete" onClick={() => setDeleteTarget(d)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} onUploaded={load} onSessionExpired={onSessionExpired} />
      <ShareDialog document={shareTarget} onClose={() => setShareTarget(null)} onSessionExpired={onSessionExpired} />

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete document</DialogTitle>
            <DialogDescription>
              This permanently removes "{deleteTarget?.file_name}" and everything indexed from it. This can't be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" disabled={isDeleting} onClick={confirmDelete}>{isDeleting ? "Deleting..." : "Delete"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// The upload response is a stream of these stages, in this order.
const STAGES = [
  { key: "extracting", label: "Extracting text" },
  { key: "chunking", label: "Splitting into chunks" },
  { key: "embedding", label: "Embedding" },
  { key: "storing", label: "Storing vectors" },
  { key: "saving", label: "Saving metadata" },
];

function UploadDialog({ open, onOpenChange, onUploaded, onSessionExpired }) {
  const [file, setFile] = useState(null);
  const [source, setSource] = useState("");
  const [progress, setProgress] = useState(null); // null | { stage, message, error?, done? }
  const fileInputRef = useRef(null);
  const isRunning = progress && !progress.done && !progress.error;

  const reset = () => {
    setFile(null);
    setSource("");
    setProgress(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    setProgress({ stage: "uploading", message: `Uploading ${file.name}...` });
    try {
      let finished = false;
      await uploadDocument(file, source.trim(), (event) => {
        if (event.status === "error") setProgress({ error: event.message });
        else if (event.status === "done") {
          finished = true;
          setProgress({ done: true, message: `${event.file_name} is ready: ${event.chunks_ingested} chunks indexed.` });
        } else setProgress({ stage: event.status, message: event.message });
      });
      if (finished) onUploaded();
      // The stream can end without a final event if the connection drops mid-ingest.
      else setProgress((p) => (p?.error ? p : { error: "The upload ended before it finished. Check the list, then try again." }));
    } catch (err) {
      if (err instanceof UnauthorizedError) return onSessionExpired();
      setProgress({ error: err.message });
    }
  };

  const stageIndex = STAGES.findIndex((s) => s.key === progress?.stage);

  return (
    <Dialog open={open} onOpenChange={(o) => { if (isRunning) return; if (!o) reset(); onOpenChange(o); }}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Upload a PDF</DialogTitle>
            <DialogDescription>The file is split into chunks and indexed so it can be searched and cited.</DialogDescription>
          </DialogHeader>

          {!progress && (
            <>
              <input ref={fileInputRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex w-full items-center gap-3 rounded-lg border border-dashed border-border px-4 py-4 text-left transition-colors hover:bg-accent/40"
              >
                <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
                <span className="min-w-0 text-sm">
                  {file ? <span className="block break-all font-medium text-foreground">{file.name}</span> : <span className="text-muted-foreground">Choose a PDF file…</span>}
                </span>
              </button>
              <div className="space-y-1.5">
                <label htmlFor="source" className="text-sm font-medium text-foreground">Where is it from?</label>
                <Input id="source" value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. https://investor.apple.com" required />
                <p className="text-xs text-muted-foreground">Recorded with the document so answers can be traced back.</p>
              </div>
            </>
          )}

          {isRunning && (
            <ol className="space-y-2">
              {STAGES.map((s, i) => (
                <li key={s.key} className="flex items-center gap-2 text-sm">
                  {i < stageIndex ? <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    : i === stageIndex ? <Loader2 className="h-4 w-4 animate-spin text-accent-foreground" />
                    : <span className="h-4 w-4 rounded-full border border-border" />}
                  <span className={i <= stageIndex ? "text-foreground" : "text-muted-foreground"}>{s.label}</span>
                </li>
              ))}
              <li className="pt-1 text-xs text-muted-foreground">{progress.message}</li>
            </ol>
          )}

          {progress?.done && (
            <p className="flex items-start gap-2 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {progress.message}
            </p>
          )}
          {progress?.error && (
            <p className="flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {progress.error}
            </p>
          )}

          <DialogFooter>
            {!progress && (
              <>
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                <Button type="submit" disabled={!file || !source.trim()}>Upload</Button>
              </>
            )}
            {(progress?.done || progress?.error) && (
              <>
                <Button type="button" variant="outline" onClick={reset}>Upload another</Button>
                <Button type="button" onClick={() => { reset(); onOpenChange(false); }}>Done</Button>
              </>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
