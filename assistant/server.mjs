import { createServer } from "node:http";

const PORT = Number(process.env.PORT || 8787);
const API_KEY = process.env.OPENAI_API_KEY;
const MODEL = process.env.OPENAI_MODEL || "gpt-5-mini";
const CORPUS_URL = (process.env.NORTHSTAR_CORPUS_URL || "https://zhouyaoji.github.io/northstar-docs-frameworks").replace(/\/$/, "");
const ALLOWED_ORIGIN = process.env.NORTHSTAR_ALLOWED_ORIGIN || "https://zhouyaoji.github.io";
const RENDERERS = new Set(["docusaurus", "mkdocs", "sphinx-rest", "sphinx-myst", "antora", "redocly"]);
const cache = new Map();
const requests = new Map();

function send(response, status, body) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": ALLOWED_ORIGIN,
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type",
    vary: "Origin",
  });
  response.end(body === null ? "" : JSON.stringify(body));
}

function allowedOrigin(request) {
  const origin = request.headers.origin;
  return !origin || origin === ALLOWED_ORIGIN;
}

function withinRateLimit(request) {
  const key = request.headers["x-forwarded-for"]?.split(",")[0].trim() || request.socket.remoteAddress || "unknown";
  const now = Date.now();
  const recent = (requests.get(key) || []).filter((time) => now - time < 600_000);
  if (recent.length >= 20) return false;
  recent.push(now);
  requests.set(key, recent);
  return true;
}

async function readBody(request) {
  let body = "";
  for await (const chunk of request) {
    body += chunk;
    if (body.length > 4_096) throw new Error("Request is too large.");
  }
  return JSON.parse(body || "{}");
}

async function corpus(renderer) {
  const cached = cache.get(renderer);
  if (cached && Date.now() - cached.time < 300_000) return cached.value;
  const base = `${CORPUS_URL}/${renderer}`;
  const [indexResponse, fullResponse] = await Promise.all([fetch(`${base}/llms.txt`), fetch(`${base}/llms-full.txt`)]);
  if (!indexResponse.ok || !fullResponse.ok) throw new Error("The documentation corpus is unavailable.");
  const value = { index: await indexResponse.text(), full: await fullResponse.text() };
  cache.set(renderer, { time: Date.now(), value });
  return value;
}

function outputText(response) {
  for (const item of response.output || []) {
    for (const content of item.content || []) {
      if (content.type === "output_text") return content.text;
    }
  }
  throw new Error("The model returned no text.");
}

async function answer(question, renderer) {
  const docs = await corpus(renderer);
  const apiResponse = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: { authorization: `Bearer ${API_KEY}`, "content-type": "application/json" },
    body: JSON.stringify({
      model: MODEL,
      store: false,
      instructions: "Answer only from the supplied Northstar documentation. If it does not support the answer, say so and set supported=false. Cite only exact URLs from the supplied llms.txt index. Do not use outside knowledge.",
      input: `QUESTION:\n${question}\n\nLLMS INDEX:\n${docs.index}\n\nDOCUMENTATION:\n${docs.full}`,
      text: { format: { type: "json_schema", name: "northstar_docs_answer", strict: true, schema: {
        type: "object", additionalProperties: false,
        properties: {
          answer: { type: "string" }, supported: { type: "boolean" },
          citations: { type: "array", items: { type: "object", additionalProperties: false, properties: { title: { type: "string" }, url: { type: "string" } }, required: ["title", "url"] } }
        }, required: ["answer", "supported", "citations"]
      } } },
      max_output_tokens: 700,
    }),
  });
  if (!apiResponse.ok) throw new Error(`OpenAI request failed (${apiResponse.status}).`);
  const result = JSON.parse(outputText(await apiResponse.json()));
  const allowedUrls = new Set([...docs.index.matchAll(/\]\((https?:\/\/[^)]+)\)/g)].map((match) => match[1]));
  result.citations = result.citations.filter((citation) => allowedUrls.has(citation.url));
  return { ...result, sourceType: result.supported ? "Documentation" : "Unsupported", meta: { renderer, model: MODEL, corpus: `${CORPUS_URL}/${renderer}/llms-full.txt` } };
}

const server = createServer(async (request, response) => {
  if (!allowedOrigin(request)) return send(response, 403, { error: "Origin not allowed." });
  if (request.method === "OPTIONS") return send(response, 204, null);
  if (request.method === "GET" && request.url === "/health") return send(response, 200, { ok: true });
  if (request.method !== "POST" || request.url !== "/api/ask") return send(response, 404, { error: "Not found." });
  if (!API_KEY) return send(response, 503, { error: "OPENAI_API_KEY is not configured." });
  if (!withinRateLimit(request)) return send(response, 429, { error: "Rate limit exceeded. Try again later." });
  try {
    const { question, renderer } = await readBody(request);
    if (typeof question !== "string" || question.trim().length < 2 || question.length > 500) return send(response, 400, { error: "Question must contain 2–500 characters." });
    if (!RENDERERS.has(renderer)) return send(response, 400, { error: "Unknown renderer." });
    return send(response, 200, await answer(question.trim(), renderer));
  } catch (error) {
    console.error(error);
    return send(response, 500, { error: "The assistant could not answer this question." });
  }
});

server.listen(PORT, () => console.log(`Northstar assistant API listening on http://localhost:${PORT}`));
