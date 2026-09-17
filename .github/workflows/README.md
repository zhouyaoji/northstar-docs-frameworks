# GitHub Pages workflow

`pages.yml` performs the publishing pipeline:

1. Install pinned Node.js and Python dependencies with dependency caching.
2. Validate manifest coverage, titles, AIPP source metadata, reviewed sidecars,
   and citations.
3. Build all seven deployable renderers for pull requests and pushes.
4. Compile the approved AIPP object and its provenance report, then generate
   the versioned documentation quality scorecard and retrieval benchmark evidence.
5. Treat invalid OpenAPI, invalid AIPP input, strict-build warnings, blocking rubric failures, and broken local links or
   assets as build failures.
6. Retain pull-request output as a seven-day preview artifact and the JSON and Markdown scorecards for 30 days.
7. Assemble static outputs beneath their public subpaths.
8. Deploy one GitHub Pages artifact only from `main` and only after the build
   job succeeds.

See the root `README.md` for the detailed trigger behavior, stage descriptions,
failure gates, output layout, and local reproduction commands.
