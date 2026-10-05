// Helpers for the API's two streaming shapes. Kept free of browser-only
// APIs beyond ReadableStream/TextDecoder so `npm test` can run them in Node.

/** Yields decoded text pieces from a fetch Response body as they arrive. */
export async function* readText(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    yield decoder.decode(value, { stream: true });
  }
  const tail = decoder.decode();
  if (tail) yield tail;
}

/**
 * Turns a stream of text pieces into parsed `data: {...}` server-sent
 * events. An event can be split across pieces (or several can arrive in
 * one), so text is buffered until its blank-line terminator shows up.
 */
export async function* parseSSE(pieces) {
  let buffer = "";
  for await (const piece of pieces) {
    buffer += piece;
    let end;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const data = raw.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("\n");
      if (!data) continue;
      try {
        yield JSON.parse(data);
      } catch {
        // a malformed event shouldn't abort the whole upload's progress
      }
    }
  }
}

/** FastAPI errors: `detail` is a string, or a list of validation issues. */
export function errorMessage(body, status) {
  const d = body?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((i) => i.msg).filter(Boolean).join("; ") || `Request failed (${status})`;
  return `Request failed (${status})`;
}
