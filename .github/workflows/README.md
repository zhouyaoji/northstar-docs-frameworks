# GitHub Pages workflow

`pages.yml` performs the initial publishing pipeline:

1. Build all four supported renderers for pull requests and pushes.
2. Treat broken links and Sphinx warnings as build failures.
3. Assemble static outputs beneath their public subpaths.
4. Deploy one GitHub Pages artifact from `main`.

Redocly and Mintlify may use their native hosted deployments if their static
outputs cannot be included cleanly in the common artifact.
