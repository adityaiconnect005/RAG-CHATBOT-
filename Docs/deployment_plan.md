# Mutual Fund RAG Chatbot - Deployment Plan

This document outlines the architecture and deployment strategy for hosting the Mutual Fund RAG Chatbot completely on free-tier services.

## 1. Automation & Scheduler: GitHub Actions
**Platform:** GitHub Actions (Free)
**Purpose:** Daily automated data pipeline execution.
**How it works:**
- A cron job (`.github/workflows/ingest.yml`) runs automatically every day at 09:15 IST.
- It spins up a temporary cloud server that runs the Python scraper (`scrape.py`), normalizes the data to extract the JSON schema (`normalize.py`), and injects live API returns (`inject_returns.py`).
- It uploads the generated text chunks directly to your free ChromaDB cloud instance.
- It commits the updated `scheme_facts.json` database directly to your `main` branch.
- **Why this is best:** It requires zero server maintenance. GitHub provides 2,000 free action minutes per month, which is far more than enough to scrape this data once a day.

## 2. Backend API Deployment: Render
**Platform:** Render.com (Web Service Free Tier)
**Purpose:** Hosting the FastAPI Python Backend.
**How it works:**
- You connect your new GitHub repository to a new "Web Service" on Render.
- Set the Build Command to `pip install -r requirements.txt`.
- Set the Start Command to `uvicorn runtime.phase_9_api.main:app --host 0.0.0.0 --port $PORT`.
- Enable "Auto-Deploy".
- **The Deployment Trigger:** Every morning, when GitHub Actions commits the new data to the `main` branch, Render instantly detects the commit, spins up a new server build, and automatically deploys the updated JSON database so your API serves fresh data.
- **Why this is best:** Render natively supports Python and FastAPI with zero complex configuration. The free tier will automatically spin down to sleep when nobody is using it, saving resources, and will wake up immediately (taking ~30 seconds) when a user visits the dashboard.

## 3. Frontend Dashboard Deployment: Vercel
**Platform:** Vercel (Free Hobby Tier)
**Purpose:** Hosting the React/Vite User Interface.
**How it works:**
- You import the `frontend` folder from your GitHub repository into Vercel.
- Vercel automatically detects it is a Vite/React project and builds it.
- You provide the Render API URL as an Environment Variable (`VITE_API_URL`).
- **Why this is best:** Vercel was built specifically for React frameworks. It serves static files instantly on a global CDN (Content Delivery Network). This means your website will load in milliseconds from anywhere in the world. Since the frontend makes dynamic HTTP requests to your Render API, the frontend *does not* need to be re-deployed daily. It simply reads whatever fresh data Render is outputting.

## 4. Vector Database Deployment: ChromaDB Cloud
**Platform:** ChromaDB Cloud Serverless
**Purpose:** Hosting the semantic vector embeddings for the RAG Chatbot.
**How it works:**
- The database is hosted off-site on ChromaDB's servers.
- The GitHub Action updates this database remotely during the daily cron job.
- The Render backend queries this database remotely when a user asks a question to the Chatbot.

## Summary of the Daily Cycle
1. **09:15 AM:** GitHub Actions begins execution.
2. **09:20 AM:** GitHub Actions successfully pushes the fresh data to the `main` branch.
3. **09:21 AM:** Render detects the commit and begins deploying the updated backend.
4. **09:25 AM:** Render finishes deployment. The entire system (Backend, Frontend, and Chatbot) is now fully synchronized with that morning's mutual fund data.
