# Deploying MCP Project Manager to Azure

A step-by-step guide to deploy this FastAPI application on Azure App Service — the fastest, cheapest path with minimal Azure resources.

---

## Architecture on Azure

```
Browser (your users)
    |
    v
Azure App Service (B1 tier, ~$13/month)
    |  gunicorn + uvicorn workers
    v
app.py  (FastAPI)
    |
    +-- mcp/context.py      (Layer 1: load project data)
    +-- mcp/processor.py    (Layer 2: compute metrics)
    +-- mcp/responder.py    (Layer 3: answer questions)
    +-- connectors/sync.py  (fetch from Jira Cloud API)
    +-- src/llm_interface.py (LLM routing)
```

Single resource. No containers, no Kubernetes, no database.

---

## Prerequisites

| What | How to get it |
|------|---------------|
| Azure account | https://azure.microsoft.com/free (free tier available) |
| Azure CLI | `brew install azure-cli` (macOS) or https://learn.microsoft.com/en-us/cli/azure/install-azure-cli |
| This project | Working locally with `python app.py` confirmed |

---

## Step 1: Login to Azure

```bash
az login
```

This opens your browser for authentication. Once logged in, the CLI confirms your subscription.

---

## Step 2: Add Production Dependencies

Add `gunicorn` to `requirements.txt` (if not already present):

```
gunicorn>=21.0.0
```

Azure App Service uses gunicorn as the production ASGI server (replaces the `uvicorn` CLI command you use locally).

---

## Step 3: Deploy with One Command

From your project root directory:

```bash
az webapp up \
  --name mcp-jira-yourname \
  --resource-group mcp-rg \
  --runtime "PYTHON:3.11" \
  --sku B1 \
  --location eastus
```

Replace `mcp-jira-yourname` with a globally unique name (this becomes your URL).

This single command:
- Creates resource group `mcp-rg` (if it doesn't exist)
- Creates an App Service plan (B1 tier)
- Creates the web app
- Zips and uploads your code
- Installs dependencies from `requirements.txt`

---

## Step 4: Set the Startup Command

```bash
az webapp config set \
  --name mcp-jira-yourname \
  --resource-group mcp-rg \
  --startup-file "gunicorn app:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"
```

This tells Azure how to start your FastAPI application.

---

## Step 5: Set Environment Variables

These replace your local `.env` file. Azure injects them as real environment variables at runtime — `python-dotenv` gracefully falls back to these.

```bash
az webapp config appsettings set \
  --name mcp-jira-yourname \
  --resource-group mcp-rg \
  --settings \
    ATLASSIAN_DOMAIN="https://yourcompany.atlassian.net" \
    ATLASSIAN_EMAIL="you@yourcompany.com" \
    ATLASSIAN_API_TOKEN="your-api-token-here" \
    JIRA_PROJECT_KEY="KAN" \
    JIRA_DEADLINE="2026-06-30" \
    JIRA_HOURS_PER_WEEK="40"
```

For multiple projects:

```bash
az webapp config appsettings set \
  --name mcp-jira-yourname \
  --resource-group mcp-rg \
  --settings JIRA_PROJECT_KEYS="KAN,MOB,CRM"
```

> **Security note:** App Settings in Azure are encrypted at rest and injected securely. Never commit real credentials to `.env` in your git repo.

---

## Step 6: Open Your App

```bash
az webapp browse --name mcp-jira-yourname --resource-group mcp-rg
```

Your app is live at:

```
https://mcp-jira-yourname.azurewebsites.net
```

---

## LLM Backend on Azure

On Azure App Service, Ollama and llama.cpp are **not available** (no local GPU). The app handles this automatically:

| Scenario | What happens | Action needed |
|----------|-------------|---------------|
| No LLM configured | Falls back to rule-based responder | None — works out of the box |
| Claude API key set | Routes to Claude API | Set the env var (see below) |

To enable Claude API answers on Azure:

```bash
az webapp config appsettings set \
  --name mcp-jira-yourname \
  --resource-group mcp-rg \
  --settings ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

The app's `src/llm_interface.py` detects this automatically and routes questions to Claude.

---

## Project Data Persistence

The `data/` folder (containing `project_*.json` files) is deployed with your code. The "Sync Jira" button in the UI writes new files to `data/` on the App Service filesystem.

**Important:** Files on App Service's local filesystem may not survive restarts on the B1 tier.

### Option A: Sync on Startup (Recommended — Simple)

Add this to `app.py` so data is always fresh:

```python
@app.on_event("startup")
async def startup_sync():
    """Fetch fresh Jira data if data/ is empty."""
    from mcp.context import ContextStore
    if not ContextStore.list_all():
        from connectors.sync import run_sync
        try:
            run_sync(verbose=False)
        except Exception:
            pass
```

### Option B: Azure Blob Storage (For Scale)

Only needed if you have many projects or need guaranteed persistence across restarts. Mount an Azure Blob container as a filesystem path — see [Azure docs on custom storage](https://learn.microsoft.com/en-us/azure/app-service/configure-connect-to-azure-storage).

---

## Redeploying After Code Changes

After making local changes, redeploy with:

```bash
az webapp up --name mcp-jira-yourname --resource-group mcp-rg
```

That's it — Azure detects the changes, reinstalls dependencies if needed, and restarts.

---

## Useful Commands

```bash
# View live logs
az webapp log tail --name mcp-jira-yourname --resource-group mcp-rg

# Restart the app
az webapp restart --name mcp-jira-yourname --resource-group mcp-rg

# Check app status
az webapp show --name mcp-jira-yourname --resource-group mcp-rg --query "state"

# View current environment variables
az webapp config appsettings list --name mcp-jira-yourname --resource-group mcp-rg

# Scale up (if you need more power)
az appservice plan update --name mcp-jira-yourname --resource-group mcp-rg --sku B2

# SSH into the app (for debugging)
az webapp ssh --name mcp-jira-yourname --resource-group mcp-rg
```

---

## Cost Summary

| Resource | Tier | Monthly Cost |
|----------|------|-------------|
| App Service Plan | **F1 (Free)** | $0 (60 min CPU/day limit — good for testing) |
| App Service Plan | **B1 (Basic)** | ~$13/month (recommended for real use) |
| App Service Plan | **B2 (Basic)** | ~$26/month (if you need more RAM) |

No database, no storage account, no container registry needed.

---

## Tear Down (Delete Everything)

When you're done and want to stop all charges:

```bash
az group delete --name mcp-rg --yes
```

This deletes the resource group and everything inside it.

---

## Quick Reference: Full Deploy Script

Copy and run this block (replace placeholder values first):

```bash
# 1. Login
az login

# 2. Deploy
az webapp up \
  --name mcp-jira-yourname \
  --resource-group mcp-rg \
  --runtime "PYTHON:3.11" \
  --sku B1 \
  --location eastus

# 3. Configure startup
az webapp config set \
  --name mcp-jira-yourname \
  --resource-group mcp-rg \
  --startup-file "gunicorn app:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"

# 4. Set credentials
az webapp config appsettings set \
  --name mcp-jira-yourname \
  --resource-group mcp-rg \
  --settings \
    ATLASSIAN_DOMAIN="https://yourcompany.atlassian.net" \
    ATLASSIAN_EMAIL="you@yourcompany.com" \
    ATLASSIAN_API_TOKEN="your-token" \
    JIRA_PROJECT_KEY="KAN"

# 5. Open in browser
az webapp browse --name mcp-jira-yourname --resource-group mcp-rg
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App shows "Application Error" | Check logs: `az webapp log tail --name mcp-jira-yourname --resource-group mcp-rg` |
| 500 errors on all pages | Verify startup command is set correctly (Step 4) |
| Jira sync fails on Azure | Check env vars: `az webapp config appsettings list --name mcp-jira-yourname --resource-group mcp-rg` |
| App is slow to start | First request after deploy takes ~30s (cold start). Subsequent requests are fast |
| "No projects found" after deploy | Click "Sync Jira" in the UI, or add the startup sync code (see Persistence section) |
| Need HTTPS | Azure App Service provides HTTPS by default at `https://mcp-jira-yourname.azurewebsites.net` |
| Custom domain | `az webapp config hostname add --webapp-name mcp-jira-yourname --resource-group mcp-rg --hostname yourdomain.com` |
