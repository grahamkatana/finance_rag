import { MessageSquareText, FileText, Activity, Users, LogOut, Landmark } from "lucide-react";
import { cn } from "../lib/utils";

const NAV_ITEMS = [
  { key: "ask", label: "Ask", icon: MessageSquareText },
  { key: "documents", label: "Documents", icon: FileText },
  { key: "activity", label: "Activity", icon: Activity },
];

export default function Sidebar({ user, onLogout, activePage, onNavigate, open }) {
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

      <nav className="flex-1 space-y-0.5 px-2 py-3">
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
