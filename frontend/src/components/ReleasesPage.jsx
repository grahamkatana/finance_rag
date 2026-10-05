import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Upload, Trash2, Smartphone, Loader2, AlertCircle, Copy, Check } from "lucide-react";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { Input } from "./ui/Input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "./ui/Table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/Dialog";
import { formatDate, formatBytes } from "../lib/format";
import { fetchReleases, uploadRelease, deleteRelease, downloadRelease, UnauthorizedError } from "../api/client";

export default function ReleasesPage({ user, onSessionExpired }) {
  const [releases, setReleases] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const handleError = useCallback((err) => {
    if (err instanceof UnauthorizedError) onSessionExpired();
    else setError(err.message);
  }, [onSessionExpired]);

  const load = useCallback(async () => {
    setError(null);
    try {
      setReleases(await fetchReleases());
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleError]);

  useEffect(() => {
    load();
  }, [load]);

  const download = async (release) => {
    setBusyId(release.id);
    setError(null);
    try {
      await downloadRelease(release.id);
    } catch (err) {
      handleError(err);
    } finally {
      setTimeout(() => setBusyId(null), 1500);
    }
  };

  const confirmDelete = async () => {
    try {
      await deleteRelease(deleteTarget.id);
      setDeleteTarget(null);
      await load();
    } catch (err) {
      setDeleteTarget(null);
      handleError(err);
    }
  };

  const latest = releases.find((r) => r.is_latest);
  const earlier = releases.filter((r) => !r.is_latest);

  return (
    <div className="thin-scrollbar min-h-0 min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-xl font-semibold text-foreground">Android app</h1>
          <p className="text-sm text-muted-foreground">Install Finance RAG on an Android phone. Open this page on the phone to download it directly.</p>
        </div>
        {user?.is_admin && (
          <Button onClick={() => setUploadOpen(true)} className="shrink-0 gap-1.5">
            <Upload className="h-3.5 w-3.5" /> Publish a version
          </Button>
        )}
      </div>

      {error && <p className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : !latest ? (
        <div className="rounded-lg border border-dashed border-border px-6 py-12 text-center">
          <Smartphone className="mx-auto h-8 w-8 text-muted-foreground/60" />
          <p className="mt-3 text-sm font-medium text-foreground">No Android app has been published yet</p>
          <p className="mt-1 text-sm text-muted-foreground">{user?.is_admin ? "Use “Publish a version” to upload the first APK." : "Ask an administrator to publish it."}</p>
        </div>
      ) : (
        <>
          <section className="rounded-xl border border-border bg-card p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-display text-2xl font-semibold text-foreground">Version {latest.version_name}</h2>
                  <Badge variant="accent">Latest</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{formatBytes(latest.size_bytes)} · published {formatDate(latest.created_at)}</p>
              </div>
              <Button onClick={() => download(latest)} disabled={busyId === latest.id} className="gap-2">
                {busyId === latest.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Download APK
              </Button>
            </div>
            {latest.notes && <p className="mt-4 whitespace-pre-wrap text-sm text-foreground">{latest.notes}</p>}
            <Checksum sha256={latest.sha256} />
          </section>

          <section className="mt-6 rounded-xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground">How to install</h2>
            <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-muted-foreground">
              <li>On your phone, open this page and tap <span className="text-foreground">Download APK</span>.</li>
              <li>Open the downloaded file. If Android asks, allow your browser to <span className="text-foreground">install unknown apps</span>, then go back and tap <span className="text-foreground">Install</span>.</li>
              <li>If Play Protect warns about an unknown developer, choose <span className="text-foreground">Install anyway</span>. The app is signed by its author rather than the Play Store.</li>
              <li>Open Finance RAG and log in with the same username and password as here.</li>
            </ol>
            <p className="mt-3 text-xs text-muted-foreground">Updating? Install the newer file over the old one; you stay logged in.</p>
          </section>

          {earlier.length > 0 && (
            <section className="mt-6">
              <h2 className="mb-2 text-sm font-semibold text-foreground">Earlier versions</h2>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Version</TableHead>
                    <TableHead>Published</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead className="w-24" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {earlier.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium text-foreground">
                        {r.version_name}
                        {r.notes && <p className="mt-0.5 max-w-md truncate text-xs font-normal text-muted-foreground" title={r.notes}>{r.notes}</p>}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(r.created_at)}</TableCell>
                      <TableCell className="whitespace-nowrap tabular-nums text-muted-foreground">{formatBytes(r.size_bytes)}</TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" className="h-8 w-8" title={`Download ${r.version_name}`} disabled={busyId === r.id} onClick={() => download(r)}>
                            <Download className="h-3.5 w-3.5" />
                          </Button>
                          {user?.is_admin && (
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" title="Delete this version" onClick={() => setDeleteTarget(r)}>
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </section>
          )}

          {user?.is_admin && latest && (
            <p className="mt-4 text-xs text-muted-foreground">
              Administrators can also remove the latest version:{" "}
              <button className="text-destructive hover:underline" onClick={() => setDeleteTarget(latest)}>delete version {latest.version_name}</button>.
            </p>
          )}
        </>
      )}

      <PublishDialog open={uploadOpen} onOpenChange={setUploadOpen} nextCode={(releases[0]?.version_code ?? 0) + 1} onPublished={load} onSessionExpired={onSessionExpired} />

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete version {deleteTarget?.version_name}</DialogTitle>
            <DialogDescription>It can no longer be downloaded. Phones that already have it keep working. This can't be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={confirmDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Checksum({ sha256 }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sha256);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable
    }
  };
  return (
    <div className="mt-4 border-t border-border pt-3">
      <p className="text-xs text-muted-foreground">SHA-256, to check the file you received is the one published:</p>
      <div className="mt-1 flex items-start gap-2">
        <code className="min-w-0 flex-1 break-all font-mono text-xs text-foreground/80">{sha256}</code>
        <button onClick={copy} title="Copy" className="shrink-0 rounded-sm p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground">
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  );
}

function PublishDialog({ open, onOpenChange, nextCode, onPublished, onSessionExpired }) {
  const [file, setFile] = useState(null);
  const [versionName, setVersionName] = useState("");
  const [versionCode, setVersionCode] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const fileInput = useRef(null);

  const reset = () => {
    setFile(null); setVersionName(""); setVersionCode(""); setNotes(""); setError(null);
  };

  const pick = (picked) => {
    setFile(picked);
    // finance-rag-0.2.0.apk -> 0.2.0 (only a suggestion; it can be edited)
    const guess = picked?.name.match(/(\d+(?:\.\d+)+[0-9A-Za-z.+-]*)\.apk$/i)?.[1];
    if (guess && !versionName) setVersionName(guess);
    if (!versionCode) setVersionCode(String(nextCode));
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsSaving(true);
    try {
      await uploadRelease({ file, versionName: versionName.trim(), versionCode, notes });
      reset();
      onOpenChange(false);
      await onPublished();
    } catch (err) {
      if (err instanceof UnauthorizedError) return onSessionExpired();
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (isSaving) return; if (!o) reset(); onOpenChange(o); }}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-3">
          <DialogHeader>
            <DialogTitle>Publish a version</DialogTitle>
            <DialogDescription>Earlier versions are kept. Every version needs a higher version code than the last: Android uses it to tell which is newer.</DialogDescription>
          </DialogHeader>
          {error && (
            <p className="flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
            </p>
          )}
          <input ref={fileInput} type="file" accept=".apk,application/vnd.android.package-archive" className="hidden" onChange={(e) => pick(e.target.files?.[0] || null)} />
          <button type="button" onClick={() => fileInput.current?.click()} className="flex w-full items-center gap-3 rounded-lg border border-dashed border-border px-4 py-3 text-left transition-colors hover:bg-accent/40">
            <Smartphone className="h-5 w-5 shrink-0 text-muted-foreground" />
            <span className="min-w-0 break-all text-sm">{file ? <span className="font-medium text-foreground">{file.name} <span className="font-normal text-muted-foreground">({formatBytes(file.size)})</span></span> : <span className="text-muted-foreground">Choose the .apk file…</span>}</span>
          </button>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="vname" className="text-sm font-medium text-foreground">Version name</label>
              <Input id="vname" value={versionName} onChange={(e) => setVersionName(e.target.value)} placeholder="0.2.0" required />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="vcode" className="text-sm font-medium text-foreground">Version code</label>
              <Input id="vcode" type="number" min={1} value={versionCode} onChange={(e) => setVersionCode(e.target.value)} placeholder={String(nextCode)} required />
            </div>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="notes" className="text-sm font-medium text-foreground">What's new <span className="font-normal text-muted-foreground">(optional)</span></label>
            <textarea id="notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>Cancel</Button>
            <Button type="submit" disabled={!file || !versionName.trim() || !versionCode || isSaving}>
              {isSaving ? <><Loader2 className="h-4 w-4 animate-spin" /> Publishing…</> : "Publish"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
