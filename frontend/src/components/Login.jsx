import { useState } from "react";
import { Landmark } from "lucide-react";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { login } from "../api/client";

export default function Login({ onSuccess }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(username, password);
      onSuccess();
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-backdrop flex h-dvh w-full items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="mb-2 flex flex-col items-center gap-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-black/40">
            <Landmark className="h-5 w-5" />
          </div>
          <h1 className="font-display text-2xl font-semibold text-foreground">Finance RAG</h1>
          <p className="text-center text-xs text-muted-foreground">Ask questions of your financial documents</p>
        </div>

        {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

        <div className="space-y-1.5">
          <label htmlFor="username" className="text-sm font-medium text-foreground">Username</label>
          <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required autoFocus />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="password" className="text-sm font-medium text-foreground">Password</label>
          <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </div>

        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Logging in..." : "Log in"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">Accounts are created by an administrator.</p>
      </form>
    </div>
  );
}
