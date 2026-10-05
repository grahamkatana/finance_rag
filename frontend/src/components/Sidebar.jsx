import { useState } from "react";
import { MessageSquareText, FileText, Activity, Users, LogOut, Landmark, Plus, MoreHorizontal, Trash2 } from "lucide-react";
import { Button } from "./ui/Button";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "./ui/DropdownMenu";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/Dialog";
import { cn } from "../lib/utils";

const NAV_ITEMS = [
  { key: "ask", label: "Ask", icon: MessageSquareText },
  { key: "documents", label: "Documents", icon: FileText },
  { key: "activity", label: "Activity", icon: Activity },
];

function groupChatsByDate(chats) {
  const startOfToday = new Date(); startOfToday.setHours(0, 0, 0, 0);
  const startOfYesterday = new Date(startOfToday); startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const sevenDaysAgo = new Date(startOfToday); sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const groups = { Today: [], Yesterday: [], "Previous 7 days": [], Older: [] };
  for (const chat of chats) {
    const t = new Date(chat.updated_at || chat.created_at);
    if (t >= startOfToday) groups.Today.push(chat);
    else if (t >= startOfYesterday) groups.Yesterday.push(chat);
    else if (t >= sevenDaysAgo) groups["Previous 7 days"].push(chat);
    else groups.Older.push(chat);
  }
  return Object.entries(groups).filter(([, list]) => list.length > 0);
}

export default function Sidebar({ user, onLogout, activePage, onNavigate, open, chats, activeChatId, onNewChat, onSelectChat, onDeleteChat }) {
  const [deleteTarget, setDeleteTarget] = useState(null);
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 w-56 max-w-[85vw] shrink-0 border-r border-border bg-card flex flex-col transition-transform",
        "md:static md:z-auto md:h-full md:translate-x-0 md:bg-muted/40",
        open ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Landmark className="h-4 w-4" />
        </span>
        <span className="font-display text-base font-semibold text-foreground">Finance RAG</span>
      </div>

      <nav className="shrink-0 space-y-0.5 px-2 py-3">
        {[...NAV_ITEMS, ...(user?.is_admin ? [{ key: "users", label: "Users", icon: Users }] : [])].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => onNavigate(key)}
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              activePage === key
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/60 hover:text-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </nav>

      <div className="flex min-h-0 flex-1 flex-col border-t border-border">
        <div className="flex items-center justify-between px-4 pb-1 pt-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">Chats</p>
          <button onClick={onNewChat} title="New chat" className="rounded-sm p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground">
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="thin-scrollbar min-h-0 flex-1 space-y-3 overflow-y-auto px-2 pb-3">
          {groupChatsByDate(chats).map(([label, list]) => (
            <div key={label}>
              <p className="px-2 pb-1 pt-1 text-[11px] text-muted-foreground/60">{label}</p>
              <div className="space-y-0.5">
                {list.map((chat) => (
                  <div
                    key={chat.id}
                    className={cn(
                      "group flex items-center rounded-md text-sm transition-colors",
                      chat.id === activeChatId ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent/60 hover:text-accent-foreground"
                    )}
                  >
                    <button onClick={() => onSelectChat(chat.id)} className="flex-1 truncate px-2 py-1.5 text-left" title={chat.title}>
                      {chat.title}
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button title="Chat options" className="mr-1 shrink-0 rounded-sm p-1 hover:bg-background/40 focus:opacity-100 md:opacity-0 md:group-hover:opacity-100">
                          <MoreHorizontal className="h-3.5 w-3.5" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem destructive onClick={() => setDeleteTarget(chat)}>
                          <Trash2 className="h-3.5 w-3.5" /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {chats.length === 0 && <p className="px-2 py-2 text-xs text-muted-foreground">Your chats will appear here.</p>}
        </div>
      </div>

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete chat</DialogTitle>
            <DialogDescription>
              This removes "{deleteTarget?.title}" and every answer in it. Your Activity history is not affected.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={() => { onDeleteChat(deleteTarget.id); setDeleteTarget(null); }}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {user && (
        <div className="flex items-center justify-between gap-2 border-t border-border p-3">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-foreground">{user.username}</p>
            <p className="truncate text-xs text-muted-foreground" title={user.email}>{user.email}</p>
          </div>
          <button onClick={onLogout} title="Log out" className="shrink-0 rounded-sm p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground">
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </aside>
  );
}
