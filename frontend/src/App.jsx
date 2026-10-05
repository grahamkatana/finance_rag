import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import Login from "./components/Login";
import Sidebar from "./components/Sidebar";
import AskPage, { clearSavedConversation } from "./components/AskPage";
import DocumentsPage from "./components/DocumentsPage";
import ActivityPage from "./components/ActivityPage";
import UsersPage from "./components/UsersPage";
import { fetchMe, hasSession, logout as apiLogout } from "./api/client";

// Each page has its own URL, so refresh, back/forward and shared links work.
// (nginx serves index.html for any path that isn't a file.)
const PATHS = { ask: "/", documents: "/documents", activity: "/activity", users: "/users" };
const pageFromLocation = () => {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  return Object.keys(PATHS).find((page) => PATHS[page] === path) || "ask";
};

export default function App() {
  const [authState, setAuthState] = useState("checking"); // checking | authed | anon
  const [user, setUser] = useState(null);
  const [activePage, setActivePage] = useState(pageFromLocation);
  const [navOpen, setNavOpen] = useState(false); // mobile only: the sidebar is a slide-in drawer below md

  const checkAuth = async () => {
    if (!hasSession()) {
      setAuthState("anon");
      return;
    }
    try {
      setUser(await fetchMe());
      setAuthState("authed");
    } catch {
      setAuthState("anon");
    }
  };

  useEffect(() => {
    checkAuth();
    const onPopState = () => setActivePage(pageFromLocation());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (page) => {
    if (PATHS[page] !== window.location.pathname) window.history.pushState(null, "", PATHS[page]);
    setActivePage(page);
  };

  // signedOut = the person chose to log out (as opposed to the session
  // expiring): only then is this browser's saved conversation removed.
  const handleLogout = ({ signedOut = false } = {}) => {
    if (signedOut && user) clearSavedConversation(user.id);
    apiLogout();
    setUser(null);
    window.history.replaceState(null, "", PATHS.ask);
    setActivePage("ask");
    setAuthState("anon");
  };

  if (authState === "checking") {
    return (
      <div className="flex h-dvh w-full items-center justify-center text-sm text-muted-foreground">Loading…</div>
    );
  }

  if (authState === "anon") {
    return <Login onSuccess={checkAuth} />;
  }

  // A non-admin who lands on /users (a shared link, an old bookmark) gets the default page.
  const page = activePage === "users" && !user.is_admin ? "ask" : activePage;

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-background md:flex-row">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-2 md:hidden">
        <button onClick={() => setNavOpen(true)} title="Menu" className="rounded-md p-2 text-muted-foreground hover:bg-accent">
          <Menu className="h-5 w-5" />
        </button>
        <span className="font-display text-base font-semibold text-foreground">Finance RAG</span>
      </div>
      {navOpen && <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={() => setNavOpen(false)} />}
      <Sidebar
        open={navOpen}
        user={user}
        onLogout={() => handleLogout({ signedOut: true })}
        activePage={page}
        onNavigate={(page) => {
          setNavOpen(false);
          navigate(page);
        }}
      />
      {/* Ask stays mounted while hidden so a conversation (and an answer
          still streaming) survives a visit to another page. */}
      <AskPage user={user} hidden={page !== "ask"} onSessionExpired={() => handleLogout()} onNavigate={navigate} />
      {page === "documents" && <DocumentsPage user={user} onSessionExpired={() => handleLogout()} />}
      {page === "activity" && <ActivityPage user={user} onSessionExpired={() => handleLogout()} />}
      {page === "users" && <UsersPage currentUser={user} onSessionExpired={() => handleLogout()} />}
    </div>
  );
}
