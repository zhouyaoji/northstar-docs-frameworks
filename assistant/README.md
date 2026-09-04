# Northstar documentation assistant

This directory contains a framework-neutral assistant for every published
Northstar renderer. The browser widget is static; the model call runs in the
Node API so `OPENAI_API_KEY` is never exposed to GitHub Pages.

## Architecture

```text
docs page -> shared widget -> POST /api/ask -> renderer llms.txt + llms-full.txt
                                           -> OpenAI Responses API
                                           -> attributed JSON response
```

The request identifies the renderer currently being viewed. The API fetches
that renderer's generated AI-readable files, asks the model to answer only from
that material, and returns citations whose URLs occur in `llms.txt`. Responses
are labelled **Documentation** today. AIPP can later become a second selectable
source without changing the widget contract.

## Run locally

Node.js 22 or newer is required; the server has no package dependencies.

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="gpt-5-mini"
export NORTHSTAR_ALLOWED_ORIGIN="http://localhost:8000"
export NORTHSTAR_CORPUS_URL="http://localhost:8000"
node assistant/server.mjs
```

In another terminal, build and serve the static site with an API URL:

```bash
NORTHSTAR_ASSISTANT_API_URL="http://localhost:8787" ./tools/build-sites.sh
python3 -m http.server 8000 --directory public
```

Open `http://localhost:8000`. An empty `NORTHSTAR_ASSISTANT_API_URL` still
renders the widget, but it displays a configuration message instead of making a
request.

## Deploy

Deploy `assistant/server.mjs` to a server or Node-capable serverless platform,
set the four environment variables above, and set
`NORTHSTAR_ASSISTANT_API_URL` in the documentation build job. Restrict
`NORTHSTAR_ALLOWED_ORIGIN` to the public Pages origin. Never put the API key in
`config.js`, repository secrets rendered into `public/`, or other browser code.

The sample includes request-size checks, a renderer allowlist, citation URL
validation, a ten-minute in-memory rate limit, and a five-minute corpus cache.
Production deployments should replace the in-memory limiter with a shared
store when multiple instances are used and add platform monitoring and abuse
controls.

## Response contract

`POST /api/ask` accepts:

```json
{"question":"How do I create an API key?","renderer":"docusaurus"}
```

It returns `answer`, `supported`, `sourceType`, `citations`, and `meta`. The
stable contract is intentionally evaluation-ready: the same question can be
sent against each renderer now and against Documentation, AIPP, and Combined
sources later.
