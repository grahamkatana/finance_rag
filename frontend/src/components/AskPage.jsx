import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Landmark, Copy, Check, ShieldCheck, Loader2, FileText, Search } from "lucide-react";
import { Button } from "./ui/Button";
import ScoreBadge from "./ScoreBadge";
import SourcePanel from "./SourcePanel";
import { cn } from "../lib/utils";
import { streamAnswer, fetchChat, evaluateAnswer, UnauthorizedError } from "../api/client";

const SUGGESTIONS = [
  "What was total net sales in the most recent fiscal year?",
  "What are the main risk factors disclosed?",
  "How did gross margin change, and what drove it?",
];
const TOP_N_OPTIONS = [3, 5, 8, 10];

let nextId = -1; // negative ids for messages not yet saved by the API; saved ones keep their own

// The API stores each saved answer with the passages it was built from.
function toMessages(saved) {
  return saved.map((m, i) =>
    m.role === "user"
      ? { id: m.id, role: "user", content: m.content }
      : {
          id: m.id, serverId: m.id, role: "assistant", content: m.content, done: true, scores: null,
          sources: m.sources || [],
          searchQuery: m.search_query,
          query: saved[i - 1]?.content ?? "", // the question it answered, for "Check answer"
          topN: m.sources?.length || 5,
        }
  );
}

export default function AskPage({ hidden, chatId, onChatCreated, onChatsChanged, onChatMissing, onSessionExpired, onNavigate }) {
  const [messages, setMessages] = useState([]);
  const [value, setValue] = useState("");
  const [topN, setTopN] = useState(5);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [selectedSource, setSelectedSource] = useState(null);
  const bottomRef = useRef(null);
  const createdHere = useRef(null); // a chat this page just created: its messages are already on screen
  const turn = useRef(0); // bumped whenever the visible chat changes, so a stale answer can't touch the new one

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Opening a chat (sidebar, a /chats/12 link, back/forward) or starting a new one.
  useEffect(() => {
    if (chatId !== null && chatId === createdHere.current) {
      createdHere.current = null;
      return;
    }
    turn.current += 1;
    setIsStreaming(false);
    setSelectedSource(null);
    if (chatId === null) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    setMessages([]);
    setIsLoadingChat(true);
    fetchChat(chatId)
      .then((chat) => !cancelled && setMessages(toMessages(chat.messages)))
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof UnauthorizedError) onSessionExpired();
        else if (err.status === 404) onChatMissing(); // deleted, or not yours
      })
      .finally(() => !cancelled && setIsLoadingChat(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId]);

  const patch = (id, changes) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...(typeof changes === "function" ? changes(m) : changes) } : m)));

  const send = (question) => {
    const query = question.trim();
    if (!query || isStreaming || isLoadingChat) return;
    const id = nextId--;
    const mine = turn.current;
    const current = () => turn.current === mine; // false once the person has moved to another chat
    let activeChat = chatId;
    setMessages((prev) => [
      ...prev,
      { id: nextId--, role: "user", content: query },
      { id, role: "assistant", query, topN, content: "", sources: null, scores: null, done: false },
    ]);
    setValue("");
    setIsStreaming(true);

    streamAnswer(query, topN, chatId, {
      onChat: (newId) => {
        activeChat = newId;
        if (current() && chatId === null) {
          createdHere.current = newId;
          onChatCreated(newId);
          onChatsChanged();
        }
      },
      onToken: (piece) => patch(id, (m) => ({ content: m.content + piece })),
    })
      .then(async () => {
        patch(id, { done: true });
        // The saved answer carries the exact passages the model saw as "Source 1..N".
        try {
          const saved = await fetchChat(activeChat);
          const last = [...saved.messages].reverse().find((m) => m.role === "assistant");
          patch(id, { serverId: last?.id, sources: last?.sources || [], searchQuery: last?.search_query });
        } catch {
          patch(id, { sources: [] });
        }
        onChatsChanged();
      })
      .catch((err) => {
        if (err instanceof UnauthorizedError) return onSessionExpired();
        patch(id, (m) => ({
          done: true,
          error: err.status === 429
            ? "You're asking faster than the rate limit allows. Give it a minute and try again."
            : err.status === 503 ? err.message // the API's own explanation (e.g. the search service is rate limited)
            : err.status === 404 ? "This chat no longer exists. Start a new chat to keep going."
            : m.content ? "The answer was cut off. Please try again." : "Sorry, I couldn't get an answer. Please try again.",
        }));
      })
      .finally(() => current() && setIsStreaming(false));
  };

  const checkAnswer = async (m) => {
    patch(m.id, { scores: "loading" });
    try {
      patch(m.id, { scores: await evaluateAnswer(m.query, m.content, m.topN, m.serverId) });
    } catch (err) {
      if (err instanceof UnauthorizedError) return onSessionExpired();
      patch(m.id, { scores: { error: err.status === 429 ? "Rate limit reached, try again in a minute." : err.message } });
    }
  };

  return (
    <div className={cn("min-h-0 min-w-0 flex-1", hidden ? "hidden" : "flex")}>
      <div className="flex min-w-0 flex-1 flex-col bg-background">
        <div className="thin-scrollbar flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-2xl space-y-6">
            {isLoadingChat && <p className="mt-10 text-center text-sm text-muted-foreground">Loading chat…</p>}
            {messages.length === 0 && !isLoadingChat && (
              <div className="mt-10 text-center md:mt-20">
                <p className="text-lg font-medium text-foreground/80">Ask your financial documents something</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Answers are drawn only from documents you can access.{" "}
                  <button onClick={() => onNavigate("documents")} className="text-accent-foreground hover:underline">Upload a PDF</button> to get started.
                </p>
                <div className="mt-6 flex flex-col items-stretch gap-2 sm:items-center">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-lg border border-border bg-card px-4 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-accent/60 sm:w-96"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex justify-end">
                  <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-primary px-4 py-3 text-[15px] leading-relaxed text-primary-foreground md:max-w-[75%]">
                    {m.content}
                  </div>
                </div>
              ) : (
                <AssistantMessage key={m.id} message={m} onSourceClick={setSelectedSource} onCheck={() => checkAnswer(m)} />
              )
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <form
          onSubmit={(e) => { e.preventDefault(); send(value); }}
          className="border-t border-border bg-background px-3 py-3 md:px-4"
        >
          <div className="mx-auto mb-2 flex max-w-2xl items-center gap-2 text-xs text-muted-foreground">
            <label htmlFor="top-n">Passages to retrieve</label>
            <select
              id="top-n"
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              title="How many passages are retrieved and given to the model for each answer"
              className="h-8 rounded-md border border-input bg-background px-2 text-foreground shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {TOP_N_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div className="mx-auto flex max-w-2xl items-end gap-2">
            <textarea
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(value);
                }
              }}
              placeholder="Ask about your documents..."
              rows={1}
              className="min-w-0 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-[15px] shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button type="submit" disabled={isStreaming || isLoadingChat || !value.trim()}>Send</Button>
          </div>
          <p className="mx-auto mt-2 max-w-2xl text-xs text-muted-foreground">
            Follow-up questions work: the last few messages in this chat are used to understand what you mean.
          </p>
        </form>
      </div>

      <SourcePanel source={selectedSource} onClose={() => setSelectedSource(null)} />
    </div>
  );
}

/** Groups retrieved passages by file, keeping each one's rank (the "Source N" the model cites). */
function groupByFile(sources) {
  const groups = new Map();
  sources.forEach((chunk, i) => {
    if (!groups.has(chunk.file_name)) groups.set(chunk.file_name, []);
    groups.get(chunk.file_name).push({ index: i + 1, chunk });
  });
  return [...groups].map(([fileName, passages]) => ({ fileName, passages }));
}

function AssistantMessage({ message: m, onSourceClick, onCheck }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(m.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable -- not worth an error
    }
  };

  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
        <Landmark className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1 break-words text-[15px] leading-relaxed text-foreground">
        {!m.content && !m.error && <span className="text-muted-foreground">Searching your documents…</span>}
        {m.content && (
          <div className="prose prose-sm prose-invert max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-headings:my-2 prose-headings:font-semibold prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          </div>
        )}
        {m.error && <p className="mt-1 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{m.error}</p>}

        {/* For a follow-up, show what was actually searched for, so a misread question is easy to spot. */}
        {m.searchQuery && m.searchQuery.trim() !== m.query?.trim() && (
          <p className="mt-3 flex items-start gap-1.5 text-xs text-muted-foreground">
            <Search className="mt-0.5 h-3 w-3 shrink-0" />
            <span>Searched for: <span className="text-foreground/80">{m.searchQuery}</span></span>
          </p>
        )}

        {m.sources?.length > 0 && (
          <div className="mt-3">
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground/70">
              Sources · {groupByFile(m.sources).length === 1 ? "1 document" : `${groupByFile(m.sources).length} documents`}, {m.sources.length} passage{m.sources.length === 1 ? "" : "s"}
            </p>
            {/* Several retrieved passages usually come from the same file, so
                each file is named once, followed by its passages. The numbers
                are the ones the answer cites as "Source N". */}
            <ul className="space-y-1.5">
              {groupByFile(m.sources).map(({ fileName, passages }) => (
                <li key={fileName} className="flex flex-wrap items-center gap-1.5 rounded-md border border-border bg-card px-2 py-1.5">
                  <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span className="mr-1 min-w-0 break-all text-xs text-foreground">{fileName}</span>
                  {passages.map(({ index, chunk }) => (
                    <button
                      key={index}
                      onClick={() => onSourceClick({ index, chunk })}
                      title={`Source ${index}: passage ${chunk.chunk_index} of this document`}
                      className="flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1.5 text-[11px] font-semibold text-accent-foreground transition-colors hover:bg-primary hover:text-primary-foreground"
                    >
                      {index}
                    </button>
                  ))}
                </li>
              ))}
            </ul>
          </div>
        )}
        {m.done && m.sources?.length === 0 && !m.error && (
          <p className="mt-2 text-xs text-muted-foreground">No matching passages were found in your documents.</p>
        )}

        {m.done && m.content && !m.error && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button onClick={copy} className="flex items-center gap-1 rounded-sm px-1.5 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground">
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
            {m.scores === null && (
              <button onClick={onCheck} title="Have a second model score this answer against the retrieved passages" className="flex items-center gap-1 rounded-sm px-1.5 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground">
                <ShieldCheck className="h-3.5 w-3.5" /> Check answer
              </button>
            )}
            {m.scores === "loading" && (
              <span className="flex items-center gap-1 px-1.5 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Checking…</span>
            )}
            {m.scores?.error && <span className="text-xs text-destructive">{m.scores.error}</span>}
            {m.scores?.faithfulness != null && (
              <>
                <ScoreBadge label="Faithful to sources" value={m.scores.faithfulness} />
                <ScoreBadge label="Sources relevant" value={m.scores.relevance} />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
