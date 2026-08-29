# GitHub Pages workflow

`pages.yml` performs the publishing pipeline:

1. Install pinned Node.js and Python dependencies with dependency caching.
2. Validate manifest coverage and titles across the maintained source formats.
3. Build all six deployable renderers for pull requests and pushes.
4. Treat invalid OpenAPI, strict-build warnings, and broken local links or
   assets as build failures.
5. Retain pull-request output as a seven-day preview artifact.
6. Assemble static outputs beneath their public subpaths.
7. Deploy one GitHub Pages artifact only from `main` and only after the build
   job succeeds.

See the root `README.md` for the detailed trigger behavior, stage descriptions,
failure gates, output layout, and local reproduction commands.
