import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/Dialog";
import { formatDate } from "../lib/format";
import { fetchShares, shareDocument, unshareDocument, UnauthorizedError } from "../api/client";

export default function ShareDialog({ document: doc, onClose, onSessionExpired }) {
  const [shares, setShares] = useState(null); // null = loading
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const fileName = doc?.file_name;

  const run = async (action) => {
    setError(null);
    try {
      await action();
      setShares(await fetchShares(fileName));
    } catch (err) {
      if (err instanceof UnauthorizedError) return onSessionExpired();
      setShares((s) => s ?? []);
      setError(err.status === 403 ? "Only the document's owner can manage sharing." : err.message);
    }
  };

  useEffect(() => {
    if (!fileName) return;
    setShares(null);
    setEmail("");
    run(async () => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileName]);

  const add = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    await run(() => shareDocument(fileName, email.trim()));
    setEmail("");
    setIsSaving(false);
  };

  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Share document</DialogTitle>
          <DialogDescription className="break-all">
            People you add can ask questions of "{fileName}". They can't delete or re-share it.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={add} className="mt-4 flex gap-2">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="colleague@example.com" required />
          <Button type="submit" disabled={isSaving || !email.trim()} className="shrink-0">Share</Button>
        </form>

        {error && <p className="mt-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

        <div className="mt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground/70">Shared with</p>
          {shares === null ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : shares.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nobody yet.</p>
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border">
              {shares.map((s) => (
                <li key={s.granted_to_user_id} className="flex items-center justify-between gap-2 px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-foreground">{s.email || `User #${s.granted_to_user_id}`}</p>
                    <p className="text-xs text-muted-foreground">since {formatDate(s.created_at)}</p>
                  </div>
                  {s.email && (
                    <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" title="Stop sharing" onClick={() => run(() => unshareDocument(fileName, s.email))}>
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
