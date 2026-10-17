# AutomateFlow

**A lightweight, self-hosted visual workflow automation studio.**

AutomateFlow is a portfolio project demonstrating Python/FastAPI backend development, graph execution, persistence, a drag-and-drop React Flow editor, automated testing and containerized deployment.

## Current MVP

- Visual workflow editor: add, connect, reposition, configure and remove steps
- Steps: Start, Set text, Uppercase, Append text, End
- Save workflows in PostgreSQL
- Execute linear workflows and inspect step-by-step input/output
- Browse execution history
- Dark dashboard interface built with Next.js and React Flow
- Docker Compose deployment suitable for Dokploy

This is an intentionally small **functional MVP**, not an n8n replacement. API calls, Playwright workers, scheduling and AI blocks are future enhancements.

## Quick start

1. Copy the environment example: \`cp .env.example .env\`
2. Set a unique strong \`DB_PASSWORD\` in \`.env\`.
3. Run \`docker compose up --build -d\`.
4. Open http://localhost:3000. A sample workflow is added automatically.
5. Connect the blocks, edit step inputs, click **Save** and then **Run workflow**.

Stop it with \`docker compose down\`.

### Dokploy

Deploy this repository as a **Docker Compose** project. Configure a domain routing to the \`web\` service on port **3000**, with HTTPS enabled. Provide \`DB_PASSWORD\` via the Compose environment. The API and database are internal services; only expose the web service. If port 3000 is taken on your VPS, change \`WEB_PORT\`, or remove the public port mapping and let Dokploy route internally.

**Security:** This MVP has no login or user isolation. Restrict access to your demo using Dokploy/reverse-proxy authentication. Do not expose an unrestricted editor publicly. The available nodes intentionally do not make arbitrary network calls or execute custom code.

### Local development (optional)

API:

\`\`\`sh
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload
\`\`\`

Without \`DATABASE_URL\`, local API development uses SQLite. Frontend:

\`\`\`sh
cd apps/web
npm install
npm run dev
\`\`\`

The Next.js dev server proxies \`/api/*\` to http://localhost:8000.

## Architecture

- \`apps/web\` — Next.js, TypeScript, React Flow
- \`apps/api\` — FastAPI, SQLAlchemy, deterministic linear graph executor
- \`docker-compose.yml\` — web, API and PostgreSQL
- \`.github/workflows/ci.yml\` — Python tests and frontend build

## Scope and limitations

The executor currently supports a **single connected chain** with one Start node and one End node. It validates node types, connection counts, disconnected steps, cycles and text size. Execution is synchronous and intentionally short; don't put slow/batch jobs into this engine. The next iteration can introduce durable background workers, API/Playwright steps, proper permissions and a run queue.

## License

MIT.
