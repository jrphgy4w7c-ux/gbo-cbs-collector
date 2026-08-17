# Grant Baseball Operations collector

This directory contains the CBS acquisition layer for Grant Baseball Operations.

- `collector.js` — canonical production CBS collector.
- The browser bookmarklet does not depend on the repository name. It loads the stable root `gbo-launcher.js` through immutable repository ID `1337389940`; the launcher resolves this canonical collector path.
- The legacy root `collector.js` is retained only as a rollback path during migration and should be retired after post-migration browser validation.
