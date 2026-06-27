# API Discovery — EditDNA Rank Studio

Official documentation inspected via Google AI docs, Tavily SDK reference, SLNG docs, and Mubit llms-full.txt (June 2026).

---

## Gemini (google-genai)

### Package

Install inside the backend virtual environment:

```bash
cd backend
source .venv/bin/activate
pip install google-genai
```

### Client initialization

```python
from google import genai

# Prefer GEMINI_API_KEY; SDK also reads GOOGLE_API_KEY from env
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
```

Auth: `GEMINI_API_KEY` or `GOOGLE_API_KEY` via header `x-goog-api-key`.

### Video file upload

```python
myfile = client.files.upload(file="path/to/video.mp4")
```

REST uploads to `https://generativelanguage.googleapis.com/upload/v1beta/files` with resumable protocol.

### Wait until active/processed

```python
import time

while not myfile.state or myfile.state.name != "ACTIVE":
    time.sleep(5)
    myfile = client.files.get(name=myfile.name)

if myfile.state.name == "FAILED":
    raise RuntimeError("Video processing failed")
```

States: `PROCESSING` → `ACTIVE` or `FAILED`.

### Pass video into Gemini

**generateContent (recommended for structured JSON):**

```python
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        {"file_data": {"file_uri": myfile.uri, "mime_type": myfile.mime_type}},
        {"text": prompt},
    ],
    config={
        "response_mime_type": "application/json",
        "response_json_schema": MyModel.model_json_schema(),
    },
)
```

**Interactions API (video understanding docs):**

```python
interaction = client.interactions.create(
    model="gemini-2.5-flash",
    input=[
        {"type": "video", "uri": myfile.uri, "mime_type": myfile.mime_type},
        {"type": "text", "text": prompt},
    ],
)
text = interaction.output_text
```

### Structured JSON output

Use `response_json_schema` (preferred over deprecated `response_schema`):

```python
config={
    "response_mime_type": "application/json",
    "response_json_schema": schema_model.model_json_schema(),
}
```

Parse: `json.loads(response.text)` then validate with Pydantic. Some SDK versions expose `response.parsed`.

### Model names

| Use case | Model |
|----------|-------|
| Reference analysis (strong) | `gemini-2.5-pro` or `gemini-2.5-flash` |
| Candidate analysis (fast) | `gemini-2.5-flash` |

Docs also reference `gemini-3.5-flash`; use 2.5 series for broad availability.

### Timestamped video analysis

Prompt with `MM:SS` timestamps:

```
Describe key events with timestamps for salient moments. Include audio and visual details at 00:05, 00:10, etc.
```

Default sampling: **1 FPS** for File API; timestamps added every second.

### Media resolution / FPS / limits

| Input method | Max size | Use case |
|--------------|----------|----------|
| File API | 2GB free / 20GB paid | Recommended for video |
| Inline | < 100MB | Short clips only |

- Tokenization: ~300 tokens/sec at default resolution, ~100 at low (`media_resolution="low"`).
- Supported MIME: `video/mp4`, `video/mpeg`, `video/mov`, `video/webm`, etc.
- One video per prompt recommended for best results.

### Error handling

- Missing key → configure `GEMINI_API_KEY`
- `FAILED` file state → retry upload
- Invalid JSON → retry once with repair prompt
- 400 INVALID_ARGUMENT on schema → use `response_json_schema` not `response_schema`

---

## Tavily (tavily-python)

### Package

Install inside the backend virtual environment:

```bash
cd backend
source .venv/bin/activate
pip install tavily-python
```

### Client initialization

```python
from tavily import TavilyClient, AsyncTavilyClient

client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
# Optional: project_id, session_id, human_id
```

Keyless mode: `TavilyClient()` without key (search/extract only, rate-limited).

### Search

```python
response = client.search(
    query="Top 5 AI video editing tools 2026",
    search_depth="advanced",
    max_results=10,
    include_answer="advanced",
    include_raw_content=False,
)
```

### Response fields (search)

```python
{
    "query": str,
    "results": [
        {
            "title": str,
            "url": str,
            "content": str,
            "score": float,
            "raw_content": str | None,
        }
    ],
    "answer": str | None,
    "response_time": float,
    "request_id": str,
}
```

### Extract

```python
response = client.extract(
    urls=["https://example.com"],
    extract_depth="basic",  # or "advanced"
    query="optional focus query",
    chunks_per_source=3,
)
```

### Response fields (extract)

```python
{
    "results": [{"url": str, "raw_content": str, ...}],
    "failed_results": [...],
    "response_time": float,
}
```

### Research task

```python
task = client.research(
    input="Research top AI video editing tools",
    model="mini",  # or "pro"
)
request_id = task["request_id"]

while True:
    result = client.get_research(request_id)
    if result["status"] == "completed":
        break
    if result["status"] == "failed":
        raise RuntimeError("Research failed")
    time.sleep(5)

# result["content"], result["sources"]
```

---

## SLNG (HTTP API)

No official Python SDK required — use `httpx`.

### Auth

```
Authorization: Bearer SLNG_API_KEY
```

Base URL: `https://api.slng.ai`

### STT (Speech-to-Text)

**Multipart upload:**

```bash
curl https://api.slng.ai/v1/stt/slng/deepgram/nova:3-en \
  -H "Authorization: Bearer SLNG_API_KEY" \
  -F "audio=@recording.wav" \
  -F "language=en"
```

**JSON with URL:**

```bash
curl https://api.slng.ai/v1/stt/slng/deepgram/nova:3-multi \
  -H "Authorization: Bearer SLNG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://...", "language":"en"}'
```

**Response schema (Deepgram Nova 3):**

```json
{
  "results": {
    "channels": [
      {
        "alternatives": [
          {
            "transcript": "transcript text",
            "confidence": 0.97
          }
        ]
      }
    ]
  },
  "metadata": {
    "request_id": "req-123",
    "duration": 2.5
  }
}
```

### TTS (Text-to-Speech)

```bash
curl https://api.slng.ai/v1/tts/slng/deepgram/aura:2-en \
  -H "Authorization: Bearer SLNG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from Barcelona!", "model": "aura-2-thalia-en"}' \
  --output hello.wav
```

Returns binary audio (WAV).

### WebSocket (voice agents)

```
wss://api.slng.ai/v1/stt/slng/deepgram/nova:3-en
wss://api.slng.ai/v1/tts/slng/deepgram/aura:2-en
```

For MVP we use HTTP batch STT/TTS.

---

## Mubit (mubit-sdk)

### Package

Install inside the backend virtual environment:

```bash
cd backend
source .venv/bin/activate
pip install mubit-sdk
```

### Client initialization

```python
from mubit import Client

client = Client(
    api_key=os.environ["MUBIT_API_KEY"],
    run_id="project-run-id",
    transport=os.getenv("MUBIT_TRANSPORT", "auto"),
)
# Optional endpoint: MUBIT_ENDPOINT=https://api.mubit.ai
```

### remember()

```python
result = client.remember(
    session_id=run_id,       # alias for run scope
    agent_id="reference-analyst",
    user_id="user-123",
    content="User prefers dramatic #1 reveal",
    intent="lesson",         # fact | lesson | rule | trace | mental_model
    lesson_scope="global",   # session | global (for cross-session recall)
    metadata={
        "memory_scope": "long_term",
        "video_type": "ranking_video",
        "topic": "Top 5 AI tools",
        "feedback_type": "text_feedback",
        "timestamp": "2026-06-27T12:00:00Z",
        "confidence": 0.9,
    },
)
# Returns job_id — poll get_ingest_job until done=True for read-after-write
```

### recall()

```python
answer = client.recall(
    session_id=run_id,
    agent_id="ranking-agent",
    user_id="user-123",
    query="What editing preferences does this user have?",
    entry_types=["fact", "lesson", "rule"],
)
# answer["final_answer"], answer["evidence"], answer["citations"]
```

Cross-session long-term: use `intent="lesson"`, `lesson_scope="global"`, same `user_id`.

### get_context()

```python
context = client.get_context(
    session_id=run_id,
    query="Draft ranking video for AI editing tools",
    mode="summary",  # full | summary | sectioned
    max_token_budget=300,
)
# context["section_summaries"] or context["context_block"]
```

### Recommended metadata fields

- `user_id`, `project_id` (in metadata), `run_id` (session_id)
- `agent_id`, `intent`, `memory_scope` (short_term | episodic | long_term)
- `video_type`, `topic`, `feedback_type`, `timestamp`, `confidence`

### Error handling

- `remember()` is async ingest — poll `client.get_ingest_job(job_id)` until `done=True`
- Missing scope → recall returns empty; use `lesson_scope="global"` for long-term
- Auth: `MUBIT_API_KEY` format `mbt_<instance>_<key_id>_<secret>`

---

## Adapter implementation notes

1. **Gemini**: Use `generate_content` + `response_json_schema` for ReferenceBlueprint and CandidateVideo.
2. **Tavily**: Use `search` for topic research; optional `research()` for deep reports; `extract()` for URL context.
3. **SLNG**: HTTP via httpx; extract audio from video with FFmpeg before STT.
4. **Mubit**: Map memory_scope to intent/lesson_scope; poll ingest jobs after writes.
