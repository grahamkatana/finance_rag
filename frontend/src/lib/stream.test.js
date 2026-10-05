import test from "node:test";
import assert from "node:assert/strict";
import { parseSSE, errorMessage } from "./stream.js";

async function collect(pieces) {
  const out = [];
  for await (const e of parseSSE((async function* () { yield* pieces; })())) out.push(e);
  return out;
}

test("parseSSE: events split across pieces, several in one piece, junk skipped", async () => {
  const events = await collect([
    'data: {"status":"extr', 'acting"}\n\ndata: {"status":"chunking"}\n\n',
    "data: not json\n\n", ": comment\n\n",
    'data: {"status":"done","chunks_ingested":12}\n\n', 'data: {"status":"never terminated"}',
  ]);
  assert.deepEqual(events, [{ status: "extracting" }, { status: "chunking" }, { status: "done", chunks_ingested: 12 }]);
});

test("errorMessage: string detail, validation list, and neither", () => {
  assert.equal(errorMessage({ detail: "Rate limit exceeded. Try again later." }, 429), "Rate limit exceeded. Try again later.");
  assert.equal(errorMessage({ detail: [{ msg: "Field required" }, { msg: "Too short" }] }, 422), "Field required; Too short");
  assert.equal(errorMessage({}, 500), "Request failed (500)");
});
