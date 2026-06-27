# EditDNA Rank Studio

EditDNA Rank Studio is a reference-based AI video generation and editing platform. A user uploads one ranking video they like. Gemini analyses the reference video and extracts its editing grammar: structure, pacing, captions, motion, audio, transitions, and ranking flow. The user then gives a new ranking topic. A swarm of specialised agents uses Tavily for research, Gemini for video understanding, SLNG for audio and voice commands, and Mubit for durable memory. The swarm selects five clips, asks the user to approve or reject each decision, stitches the final ranking video, and learns from feedback across short-term, episodic, and long-term memory. The user is no longer a manual editor; they become a creative director approving agent decisions.

## Swarm stages (candidate acquisition)

```text
stage_5_candidate_discovery     → CandidateDiscoveryAgent
stage_5a_platform_video_search  → PlatformVideoSearchAgent (Tavily URL discovery, traced)
stage_5b_platform_video_download → PlatformVideoDownloadAgent (yt-dlp/HTTP, traced)
stage_6_candidate_analysis      → CandidateAnalysisAgent
```

Every search query, discovered URL, download start/success/failure is recorded as:
- `AgentTrace.tool_calls` on the search/download agents
- `ProjectBlackboard.download_events` (exposed at `GET /api/projects/{id}/downloads`)
- Mubit trace memory via `BaseAgent.execute()`

## Architecture

- **Blackboard swarm**: specialised agents read/write a shared `ProjectBlackboard`
- **MoE edit pipeline**: Story, Cut, Caption, and Motion experts run **in parallel**, exchange messages on a shared bus, then a Fusion agent merges weighted proposals into the edit plan
- **Human gates**: candidate approval, edit plan approval, final output approval
- **Real APIs first**: no silent mock data unless `ALLOW_DEMO_FALLBACK=true`

### MoE edit pipeline (parallel experts)

```text
MoE Router          → computes expert weights from reference blueprint + memory
Round 1 (propose)   → Story ∥ Cut ∥ Caption ∥ Motion  (asyncio.gather)
Round 2 (refine)    → experts read peer messages and refine proposals
Fusion Agent        → weighted merge → EditPlan
Critic Agent        → validates harness goals; retries MoE until goals met (max 2)
Goal Harness        → evaluates edit-plan goals and drives corrective loops
```

Inter-agent messages are stored on `ProjectBlackboard.agent_messages` and visible in the UI trace panel.

## Setup

### 1. Environment

Copy `.env.example` to `.env` and fill in keys:

```bash
GEMINI_API_KEY=
TAVILY_API_KEY=
SLNG_API_KEY=
MUBIT_API_KEY=
```

API discovery notes: see `docs/API_DISCOVERY.md`.

### 2. Backend (venv required)

All backend Python commands must run inside `backend/.venv`.

```bash
cd backend
./scripts/setup_venv.sh
./scripts/run_dev.sh
```

Manual alternative:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Requires **FFmpeg** installed locally for rendering.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

### 4. Video sources

The swarm uses **both** local assets and open-web platform search:

1. **Local files** in `sample_assets/` (optional fallback)
2. **Tavily web search** for YouTube, TikTok, Instagram, X, Facebook, Vimeo, Reddit, etc.
3. **yt-dlp download** of discovered platform URLs into `uploads/{project_id}/candidates/`
4. **Gemini analysis** from downloaded files or YouTube URLs directly

Install yt-dlp (required for platform downloads):

```bash
pip install yt-dlp
# or: brew install yt-dlp
```

Env:

```bash
ALLOW_WEB_VIDEO_FETCH=true
```

**Note:** You are responsible for usage rights on downloaded platform content. The tool fetches publicly discoverable URLs for hackathon/demo workflows.

## Flow

1. Upload reference ranking video
2. Gemini extracts `ReferenceBlueprint`
3. Enter topic → Tavily research
4. Discover/analyse candidate clips from sample assets + user uploads
5. Ranking agent selects top 5 → user approves/reorders
6. Swarm builds `EditPlan` → user approves
7. FFmpeg renders output MP4
8. User gives text/voice feedback → SLNG STT + Mubit memory
9. Regenerate with memory influence
10. Comparison agent scores reference vs generated

## API

Base URL: `http://127.0.0.1:8000`

Key endpoints:

- `POST /api/projects`
- `POST /api/projects/{id}/upload-reference`
- `POST /api/projects/{id}/analyse-reference`
- `POST /api/projects/{id}/topic`
- `POST /api/projects/{id}/research`
- `POST /api/projects/{id}/candidates/discover`
- `POST /api/projects/{id}/ranking/select`
- `POST /api/projects/{id}/edit-plan`
- `POST /api/projects/{id}/render`
- `POST /api/projects/{id}/feedback/text`
- `POST /api/projects/{id}/regenerate`
- `POST /api/projects/{id}/final-approve`
- `GET /api/projects/{id}/comparison`

## Missing keys behaviour

If an API key is missing, endpoints fail with explicit errors like `Missing GEMINI_API_KEY`. The UI surfaces missing keys on the landing page via `/api/health`.
