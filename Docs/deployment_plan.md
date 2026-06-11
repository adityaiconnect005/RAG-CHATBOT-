# Deployment Plan

This document outlines the deployment strategy and platforms chosen for the RAG Chatbot application.

## 1. Frontend: Vercel
- **Platform:** Vercel
- **Why Vercel?** Vercel provides seamless deployment for modern web frameworks (like Next.js, React, or Vite). It offers edge network delivery, automatic CI/CD from Git, and preview deployments for every pull request.
- **Deployment Workflow:** 
  - Connect the repository to Vercel.
  - Pushes to the `main` branch will automatically trigger production deployments.
  - Pull requests will generate preview URLs for testing before merging.

## 2. Backend: Render
- **Platform:** Render
- **Why Render?** Render is an excellent Platform as a Service (PaaS) for hosting backend applications (e.g., Python FastAPI/Flask or Node.js). It supports Docker-based deployments or native environments, manages TLS certificates automatically, and offers easy scaling.
- **Deployment Workflow:**
  - Create a "Web Service" on Render linked to the GitHub repository.
  - Specify the build command (e.g., `pip install -r requirements.txt`) and start command (e.g., `uvicorn main:app --host 0.0.0.0 --port 10000`).
  - Configure environment variables (API keys, database URIs) in the Render dashboard.
  - Auto-deployments can be enabled for pushes to the `main` branch.

## 3. Scheduler: GitHub Actions
- **Platform:** GitHub Actions
- **Why GitHub Actions?** For recurring tasks, cron jobs, and background maintenance, GitHub Actions provides a robust and free (for public/basic use) orchestration system directly integrated with the repository.
- **Deployment Workflow:**
  - Create workflow files (e.g., `.github/workflows/scheduler.yml`).
  - Define `schedule` events using standard cron syntax (e.g., `cron: '0 0 * * *'` for daily runs).
  - The actions will spin up a runner, set up the environment, run necessary scripts (like data ingestion or index updates), and log the output.

## Environment Variables & Secrets
Across all platforms, sensitive data should never be hardcoded. 
- **Vercel:** Store UI keys in the Vercel project settings.
- **Render:** Store backend secrets, DB credentials, and API keys in Render's Environment Variables section.
- **GitHub Actions:** Store any secrets required for scheduled tasks in GitHub Repository Secrets and inject them into the workflow steps.
