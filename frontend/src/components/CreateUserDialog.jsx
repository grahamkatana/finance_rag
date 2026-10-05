import { useState } from "react";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/Dialog";
import { createUser, UnauthorizedError } from "../api/client";

const EMPTY = { email: "", username: "", password: "" };

export default function CreateUserDialog({ open, onOpenChange, onCreated, onSessionExpired }) {
  const [form, setForm] = useState(EMPTY);
  const [status, setStatus] = useState(null); // { ok, text }
  const [isSaving, setIsSaving] = useState(false);

  const field = (name) => ({ value: form[name], onChange: (e) => setForm({ ...form, [name]: e.target.value }) });

  const submit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setStatus(null);
    try {
      const user = await createUser(form);
      setStatus({ ok: true, text: `Created ${user.username}. Share the password with them directly.` });
      setForm(EMPTY);
      onCreated?.();
    } catch (err) {
      if (err instanceof UnauthorizedError) return onSessionExpired();
      setStatus({ ok: false, text: err.message });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) setStatus(null); onOpenChange(o); }}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-3">
          <DialogHeader>
            <DialogTitle>Add user</DialogTitle>
            <DialogDescription>Public sign-up is disabled, so accounts are created here.</DialogDescription>
          </DialogHeader>
          {status && (
            <p className={"rounded-md px-3 py-2 text-sm " + (status.ok ? "bg-emerald-500/15 text-emerald-300" : "bg-destructive/10 text-destructive")}>
              {status.text}
            </p>
          )}
          <Input type="email" placeholder="Email" required {...field("email")} />
          <Input placeholder="Username" required autoComplete="off" {...field("username")} />
          <Input type="password" placeholder="Password" required minLength={8} autoComplete="new-password" {...field("password")} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
            <Button type="submit" disabled={isSaving}>{isSaving ? "Creating..." : "Create user"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
