# docker/

Reserved by the repo layout in `docs/original-prompt.docx` §32. The actual
Dockerfiles live next to the code they build — `backend/Dockerfile`,
`frontend/Dockerfile` (which also owns `frontend/docker-nginx.conf`, the
Nginx config that serves the built SPA and proxies `/api/*` to the backend
container) — and are orchestrated by the root `docker-compose.yml`.

This directory is where a shared reverse-proxy config (e.g. a Caddyfile or
an Nginx config fronting both services with TLS, per the root README's
"Production notes") would go if/when one is added — nothing here yet because
the `frontend` container's own Nginx already covers the dev/single-host case.
