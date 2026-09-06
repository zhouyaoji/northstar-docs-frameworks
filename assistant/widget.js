(() => {
  const current = document.currentScript;
  const root = document.createElement("div");
  root.id = "northstar-assistant";
  document.body.append(root);
  const shadow = root.attachShadow({ mode: "open" });
  shadow.innerHTML = `<style>
    button{font:inherit}.launch{position:fixed;right:1rem;bottom:1rem;z-index:9999;border:0;border-radius:999px;padding:.8rem 1rem;background:#146ef5;color:#fff;box-shadow:0 4px 18px #0005;cursor:pointer;font-weight:700}.panel{position:fixed;right:1rem;bottom:4.7rem;z-index:9999;width:min(390px,calc(100vw - 2rem));max-height:70vh;overflow:auto;background:#fff;color:#172033;border:1px solid #cad3df;border-radius:14px;box-shadow:0 12px 40px #0005;padding:1rem;font:15px/1.45 system-ui,sans-serif}.hidden{display:none}h2{font-size:1.05rem;margin:0 0 .35rem}p{margin:.45rem 0}form{display:flex;gap:.5rem;margin-top:.8rem}input{min-width:0;flex:1;padding:.65rem;border:1px solid #9ba8b8;border-radius:8px}form button{border:0;border-radius:8px;padding:.6rem .8rem;background:#146ef5;color:#fff;cursor:pointer}.answer{white-space:pre-wrap}.source{display:inline-block;background:#e8f2ff;color:#064da7;border-radius:999px;padding:.15rem .5rem;font-size:.78rem;font-weight:700}ul{padding-left:1.2rem}a{color:#075fbd}
  </style><button class="launch" aria-expanded="false">Ask Northstar</button><section class="panel hidden" role="dialog" aria-label="Northstar documentation assistant"><h2>Ask the docs</h2><p>Answers are grounded in this renderer’s published documentation.</p><form><input aria-label="Question" maxlength="500" placeholder="How do I create an API key?" required><button>Ask</button></form><div class="result" aria-live="polite"></div></section>`;
  const launch = shadow.querySelector(".launch");
  const panel = shadow.querySelector(".panel");
  const form = shadow.querySelector("form");
  const input = shadow.querySelector("input");
  const result = shadow.querySelector(".result");
  const known = ["docusaurus", "mkdocs", "sphinx-rest", "sphinx-myst", "antora", "redocly"];
  const renderer = location.pathname.split("/").find((part) => known.includes(part));
  const siteRoot = new URL("../", current.src);

  launch.addEventListener("click", () => {
    panel.classList.toggle("hidden");
    launch.setAttribute("aria-expanded", String(!panel.classList.contains("hidden")));
    if (!panel.classList.contains("hidden")) input.focus();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const endpoint = window.NORTHSTAR_ASSISTANT_API_URL || "";
    if (!endpoint) {
      result.textContent = "Searching the published documentation…";
      try { renderLocalResults(await localSearch(input.value)); }
      catch { result.textContent = "The published documentation index could not be loaded."; }
      return;
    }
    result.textContent = "Checking the documentation…";
    try {
      const response = await fetch(`${endpoint.replace(/\/$/, "")}/api/ask`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question: input.value, renderer: renderer || "docusaurus" }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Request failed.");
      const citations = data.citations.map((item) => `<li><a target="_blank" rel="noopener" href="${escapeHtml(item.url)}">${escapeHtml(item.title)}</a></li>`).join("");
      result.innerHTML = `<p><span class="source">${escapeHtml(data.sourceType)}</span></p><p class="answer">${escapeHtml(data.answer)}</p>${citations ? `<p><strong>Sources</strong></p><ul>${citations}</ul>` : ""}`;
    } catch (error) { result.textContent = error.message; }
  });
  function escapeHtml(value) {
    const node = document.createElement("span");
    node.textContent = String(value);
    return node.innerHTML;
  }

  async function localSearch(question) {
    const corpusBase = new URL(renderer ? `${renderer}/` : "", siteRoot);
    const [indexResponse, fullResponse] = await Promise.all([
      fetch(new URL("llms.txt", corpusBase)),
      fetch(new URL("llms-full.txt", corpusBase)),
    ]);
    if (!indexResponse.ok || !fullResponse.ok) throw new Error("Corpus unavailable");
    const terms = [...new Set(question.toLowerCase().match(/[a-z0-9]+/g) || [])].filter((term) => term.length > 2);
    const links = new Map([...((await indexResponse.text()).matchAll(/\[([^\]]+)]\((https?:\/\/[^)]+)\)/g))].map((match) => [match[1].toLowerCase(), match[2]]));
    return (await fullResponse.text()).split(/\n---\n/).map((section) => {
      const title = section.match(/^#\s+(.+)$/m)?.[1] || "Northstar documentation";
      const plain = section.replace(/^---[\s\S]*?---\s*/, "").replace(/[#*`>|\[\]()_-]/g, " ").replace(/\s+/g, " ").trim();
      const lower = `${title} ${plain}`.toLowerCase();
      const score = terms.reduce((total, term) => total + (lower.split(term).length - 1), 0);
      const url = [...links].find(([name]) => title.toLowerCase().includes(name) || name.includes(title.toLowerCase()))?.[1];
      return { title, excerpt: plain.slice(0, 360), score, url };
    }).filter((item) => item.score > 0).sort((a, b) => b.score - a.score).slice(0, 3);
  }

  function renderLocalResults(items) {
    if (!items.length) {
      result.innerHTML = '<p><span class="source">Local search · Unsupported</span></p><p>No matching passage was found in the published documentation.</p>';
      return;
    }
    const passages = items.map((item) => `<li><strong>${escapeHtml(item.title)}</strong><br>${escapeHtml(item.excerpt)}${item.excerpt.length >= 360 ? "…" : ""}${item.url ? `<br><a target="_blank" rel="noopener" href="${escapeHtml(item.url)}">Open source</a>` : ""}</li>`).join("");
    result.innerHTML = `<p><span class="source">Local search · Documentation</span></p><p>These are matching passages, not an AI-generated answer:</p><ul>${passages}</ul>`;
  }
})();
