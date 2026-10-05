import { useCallback, useEffect, useState } from "react";
import { Menu, Plus } from "lucide-react";
import Login from "./components/Login";
import Sidebar from "./components/Sidebar";
import AskPage from "./components/AskPage";
import DocumentsPage from "./components/DocumentsPage";
import ActivityPage from "./components/ActivityPage";
import UsersPage from "./components/UsersPage";
import { fetchMe, hasSession, logout as apiLogout, fetchChats, deleteChat, UnauthorizedError } from "./api/client";

// Each page has its own URL, so refresh, back/forward and shared links work.
// A chat has one too (/chats/12). nginx serves index.html for any path that isn't a file.
const PATHS = { ask: "/", documents: "/documents", activity: "/activity", users: "/users" };
const urlFor = (page, chatId) => (page === "ask" && chatId ? `/chats/${chatId}` : PATHS[page]);

function parseLocation() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const chat = path.match(/^\/chats\/(\d+)$/);
  if (chat) return { page: "ask", chatId: Number(chat[1]) };
  return { page: Object.keys(PATHS).find((page) => PATHS[page] === path) || "ask", chatId: null };
}

export default function App() {
  const [authState, setAuthState] = useState("checking"); // checking | authed | anon
  const [user, setUser] = useState(null);
  const [loc, setLoc] = useState(parseLocation); // { page, chatId }
  const [chats, setChats] = useState([]);
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
    const onPopState = () => setLoc(parseLocation());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (page, chatId = null, { replace = false } = {}) => {
    const url = urlFor(page, chatId);
    if (url !== window.location.pathname) window.history[replace ? "replaceState" : "pushState"](null, "", url);
    setLoc({ page, chatId });
  };

  const handleLogout = () => {
    apiLogout();
    setUser(null);
    setChats([]);
    window.history.replaceState(null, "", "/");
    setLoc({ page: "ask", chatId: null });
    setAuthState("anon");
  };

  const loadChats = useCallback(async () => {
    try {
      setChats(await fetchChats());
    } catch (err) {
      if (err instanceof UnauthorizedError) handleLogout();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (authState === "authed") loadChats();
  }, [authState, loadChats]);

  const removeChat = async (id) => {
    try {
      await deleteChat(id);
      setChats((prev) => prev.filter((c) => c.id !== id));
      if (loc.chatId === id) navigate("ask");
    } catch (err) {
      if (err instanceof UnauthorizedError) handleLogout();
    }
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
  const page = loc.page === "users" && !user.is_admin ? "ask" : loc.page;

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-background md:flex-row">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-border px-2 md:hidden">
        <button onClick={() => setNavOpen(true)} title="Menu" className="rounded-md p-2 text-muted-foreground hover:bg-accent">
          <Menu className="h-5 w-5" />
        </button>
        <span className="font-display text-base font-semibold text-foreground">Finance RAG</span>
        <button onClick={() => navigate("ask")} title="New chat" className="rounded-md p-2 text-muted-foreground hover:bg-accent">
          <Plus className="h-5 w-5" />
        </button>
      </div>
      {navOpen && <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={() => setNavOpen(false)} />}
      <Sidebar
        open={navOpen}
        user={user}
        onLogout={handleLogout}
        activePage={page}
        chats={chats}
        activeChatId={page === "ask" ? loc.chatId : null}
        onNavigate={(next) => {
          setNavOpen(false);
          navigate(next);
        }}
        onNewChat={() => {
          setNavOpen(false);
          navigate("ask");
        }}
        onSelectChat={(id) => {
          setNavOpen(false);
          navigate("ask", id);
        }}
        onDeleteChat={removeChat}
      />
      {/* Ask stays mounted while hidden so an answer still streaming survives a visit to another page. */}
      <AskPage
        hidden={page !== "ask"}
        chatId={loc.chatId}
        onChatCreated={(id) => navigate("ask", id, { replace: true })}
        onChatsChanged={loadChats}
        onChatMissing={() => navigate("ask", null, { replace: true })}
        onSessionExpired={handleLogout}
        onNavigate={navigate}
      />
      {page === "documents" && <DocumentsPage user={user} onSessionExpired={handleLogout} />}
      {page === "activity" && <ActivityPage user={user} onSessionExpired={handleLogout} />}
      {page === "users" && <UsersPage currentUser={user} onSessionExpired={handleLogout} />}
    </div>
  );
}
