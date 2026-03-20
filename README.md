# Sean Lead Agent

Username Acquisition & Corporate Outreach System

## Quick Start

### 1. Clone and install
```bash
git clone <your-repo-url>
cd username-acquisition-agent
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your Supabase, API keys, etc.
```

### 3. Set up Supabase
Run `migrations/001_initial_schema.sql` in your Supabase SQL Editor.

### 4. Run locally
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Deploy to Railway
Push to GitHub. Railway auto-deploys from your linked repo.

## API Docs
Once running, visit `http://localhost:8000/docs` for the interactive API documentation.

## Architecture
- **Engine A:** Opportunity Scanner (company discovery, handle scanning, scoring)
- **Engine B:** Outreach & Booking (contact enrichment, messaging, sequences)
- **Dashboard:** React frontend (Pipeline view, approval queue, reports)

See `Sean_Lead_Agent_Build_Plan.md` for complete architecture documentation.
