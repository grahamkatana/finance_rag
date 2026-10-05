import { useCallback, useEffect, useState } from "react";
import { UserPlus, ShieldCheck, ShieldOff } from "lucide-react";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "./ui/Table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/Dialog";
import CreateUserDialog from "./CreateUserDialog";
import { formatDate } from "../lib/format";
import { fetchUsers, setUserAdmin, UnauthorizedError } from "../api/client";

export default function UsersPage({ currentUser, onSessionExpired }) {
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [roleTarget, setRoleTarget] = useState(null); // the user whose role is about to change
  const [isSaving, setIsSaving] = useState(false);

  const handleError = useCallback((err) => {
    if (err instanceof UnauthorizedError) onSessionExpired();
    else setError(err.message);
  }, [onSessionExpired]);

  const load = useCallback(async () => {
    setError(null);
    try {
      setUsers(await fetchUsers());
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleError]);

  useEffect(() => {
    load();
  }, [load]);

  const confirmRoleChange = async () => {
    setIsSaving(true);
    try {
      await setUserAdmin(roleTarget.id, !roleTarget.is_admin);
      await load();
    } catch (err) {
      handleError(err);
    } finally {
      setIsSaving(false);
      setRoleTarget(null);
    }
  };

  const adminCount = users.filter((u) => u.is_admin).length;

  return (
    <div className="thin-scrollbar min-h-0 min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-xl font-semibold text-foreground">Users</h1>
          <p className="text-sm text-muted-foreground">
            {users.length > 0 ? `${users.length} account${users.length === 1 ? "" : "s"}, ${adminCount} admin${adminCount === 1 ? "" : "s"}. ` : ""}
            Admins can see every document and all activity, and manage accounts.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="shrink-0 gap-1.5">
          <UserPlus className="h-3.5 w-3.5" /> Add user
        </Button>
      </div>

      {error && <p className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead className="w-40" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => {
              const isSelf = u.id === currentUser.id;
              return (
                <TableRow key={u.id}>
                  <TableCell className="font-medium text-foreground">
                    {u.username}
                    {isSelf && <span className="ml-2 text-xs font-normal text-muted-foreground">you</span>}
                    {!u.is_active && <Badge variant="outline" className="ml-2">Inactive</Badge>}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{u.email}</TableCell>
                  <TableCell>
                    <Badge variant={u.is_admin ? "accent" : "secondary"}>{u.is_admin ? "Admin" : "Member"}</Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(u.created_at)}</TableCell>
                  <TableCell>
                    {/* Your own admin access can't be removed here: with one admin that would lock everyone out. */}
                    {!isSelf && (
                      <Button variant="outline" size="sm" className="w-full gap-1.5" onClick={() => setRoleTarget(u)}>
                        {u.is_admin ? <ShieldOff className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                        {u.is_admin ? "Remove admin" : "Make admin"}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={load} onSessionExpired={onSessionExpired} />

      <Dialog open={!!roleTarget} onOpenChange={(o) => !o && setRoleTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{roleTarget?.is_admin ? "Remove admin access" : "Make admin"}</DialogTitle>
            <DialogDescription>
              {roleTarget?.is_admin
                ? `${roleTarget?.username} will go back to seeing only their own documents and activity.`
                : `${roleTarget?.username} will be able to see every user's documents and activity, and manage accounts.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRoleTarget(null)}>Cancel</Button>
            <Button variant={roleTarget?.is_admin ? "destructive" : "default"} disabled={isSaving} onClick={confirmRoleChange}>
              {isSaving ? "Saving..." : roleTarget?.is_admin ? "Remove admin" : "Make admin"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
