# AutomateFlow

**A lightweight, self-hosted visual workflow automation studio.**

AutomateFlow is a portfolio project demonstrating Python/FastAPI backend development, graph execution, persistence, a drag-and-drop React Flow editor, automated testing and containerized deployment.

## Current MVP

- Visual workflow editor: add, connect, reposition, configure and remove steps
- Steps: Start, Set text, Uppercase, Append text, HTTP GET, Extract JSON field, **Open page, Click element, Fill input, Press key, Read page text**, End
- Save workflows in PostgreSQL
- Execute linear workflows and inspect step-by-step input/output
- Browse success and failure traces, including the input/output of every step
- Duplicate and delete workflows
- Dark dashboard interface built with Next.js and React Flow
- Docker Compose deployment suitable for Dokploy

This is an intentionally small **functional MVP**, not an n8n replacement. Scheduling, durable workers and AI blocks are future enhancements.

## Quick start

1. Copy the environment example: `cp .env.example .env`
2. Set a unique strong `DB_PASSWORD` in `.env`.
3. Run `docker compose up --build -d`.
4. Open http://localhost:3000. A sample workflow is added automatically.
5. Connect the blocks, edit step inputs, click **Save** and then **Run workflow**.

Stop it with `docker compose down`.

### Dokploy

Deploy this repository as a **Docker Compose** project. Configure a domain routing to the `web` service on port **3000**, with HTTPS enabled. Provide `DB_PASSWORD` via the Compose environment. The API and database are internal services; only expose the web service. If port 3000 is taken on your VPS, change `WEB_PORT`, or remove the public port mapping and let Dokploy route internally.

**Security:** This MVP has no login or user isolation. Restrict access to your demo using Dokploy/reverse-proxy authentication. Do not expose an unrestricted editor publicly. The HTTP GET node only accepts HTTPS URLs from an exact hostname allowlist (`HTTP_ALLOWED_HOSTS`), and blocks redirects, credential URLs, IP literals and non-standard ports. Browser actions are limited to exact HTTPS hosts in `BROWSER_ALLOWED_HOSTS` (default `demo.playwright.dev`), deny unsafe methods, WebSockets, redirects, and off-host resources. No arbitrary Python or JavaScript execution is supported.

### Local development (optional)

API:

```sh
cd apps/api
pip install -r requirements.txt
python -m playwright install --with-deps chromium
uvicorn app.main:app --reload
```

Without `DATABASE_URL`, local API development uses SQLite. Frontend:

```sh
cd apps/web
npm install
npm run dev
```

The Next.js dev server proxies `/api/*` to http://localhost:8000.

## Architecture

- `apps/web` — Next.js, TypeScript, React Flow
- `apps/api` — FastAPI, SQLAlchemy, deterministic linear graph executor
- `docker-compose.yml` — web, API and PostgreSQL
- `.github/workflows/ci.yml` — Python tests and frontend build

## Scope and limitations

The executor currently supports a **single connected chain** with one Start node and one End node. It validates node types, connection counts, disconnected steps, cycles and text size. Execution is synchronous and intentionally short; don't put slow/batch jobs into this engine. The next iteration can introduce durable background workers, proper permissions and a run queue.

## License

MIT.


## HTTP / JSON walkthrough

Create a workflow: **Start → HTTP GET → Extract JSON field → Uppercase → End**.

- HTTP GET URL: `https://jsonplaceholder.typicode.com/todos/1`
- Extract JSON field: `title` (nested paths like `user.name` and `items.0.id` also work)
- Run and inspect the trace to see the response body and extracted data.

Only `jsonplaceholder.typicode.com` is allowlisted by default. To use other domains, configure `HTTP_ALLOWED_HOSTS` as a comma-separated list on the API container. The demo HTTP node supports GET requests without authentication, with 6-second timeout and maximum 4 KB responses. Keep the platform behind reverse-proxy access control in Dokploy.


## Browser RPA (Playwright) walkthrough

1. Click **Create browser demo** in the sidebar.
2. The template connects **Start → Open page → Fill input → Press key → Read page text → End**.
3. Click **Run workflow**. The engine launches headless Chromium, opens TodoMVC, fills the `.new-todo` input, presses **Enter**, reads `.todo-list li`, and closes the browser.
4. Inspect the run trace for each step and the text extracted from the page.

Also available: **Click element** (CSS selector). Click and fill actions run in a single fresh browser session per workflow, so browser state persists between steps but never between runs.

### Browser safety and Dokploy

- **Configure:** `BROWSER_ALLOWED_HOSTS=demo.playwright.dev` (comma-separated *exact* domains if you control additional testing domains).
- **Network controls:** each browser request is intercepted. Only GET/HEAD requests to allowed HTTPS hosts are fetched with redirects disabled; WebSockets, service workers, non-standard ports, unknown origins and unsupported actions are blocked.
- **Isolation:** Chromium runs as a non-root user in the API container with a bounded shared-memory size. This is a demonstration safety boundary, not robust multi-tenant or hostile-website sandboxing. Restrict users and use a separate egress-isolated worker for any wider deployment.
- **Infrastructure:** install Chromium with dependencies in the provided API Dockerfile. Playwright makes the Docker image notably larger and browser steps consume more memory than text/HTTP steps.
- **Limits:** synchronous execution; short demo flows only. CSS selectors, no cookies persisted between runs, no authenticated login flows, no files/uploads/downloads, no custom JavaScript. For public demos, use reverse-proxy authentication and **never** allow arbitrary internal/external hosts.
