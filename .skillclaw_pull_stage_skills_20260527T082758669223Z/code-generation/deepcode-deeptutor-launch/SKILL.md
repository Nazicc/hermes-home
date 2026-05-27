---
name: deepcode-deeptutor-launch
description: "Use when launching HKUDS DeepCode (port 8000 backend + port 5173 frontend) and DeepTutor (port 8001 backend + port 3782 frontend) from /Users/can/DeepCode, or when starting/stopping these research pipeline services. DeepTutor is a git submodule inside DeepCode. NOT for: general coding tasks (use opencode/blackbox), or when DeepCode is not the target platform."
category: code-generation
---

---
name: deepcode-deeptutor-launch
description: "Use when launching HKUDS DeepCode (port 8000 backend + port 5173 frontend) and DeepTutor (port 8001 backend + port 3782 frontend) from /Users/can/DeepCode, or when starting/stopping these research pipeline services. DeepTutor is a git submodule inside DeepCode. NOT for: general coding tasks (use opencode/blackbox), or when DeepCode is not the target platform."
version: 1.1.0
author: Hermes Agent
license: MIT
---

## Repository Structure

- **DeepCode root**: `/Users/can/DeepCode/`
  - Backend: Python/FastAPI on **port 8000** (`new_ui/backend`)
  - Frontend: React on **port 5173** (`new_ui/frontend`)
- **DeepTutor**: `/Users/can/DeepCode/DeepTutor/` (git submodule — NOT a separate clone)
  - Backend: Python on **port 8001**
  - Frontend: React on **port 3782**

Both services share the same MiniMax LLM backend configured in DeepCode's `.env`.

## Service Summary

| Service | Backend Port | Frontend Port | Path |
|---------|-------------|---------------|------|
| DeepCode API | 8000 | — | /Users/can/DeepCode/new_ui/backend |
| DeepCode UI | — | 5173 | /Users/can/DeepCode/new_ui/frontend |
| DeepTutor API | 8001 | — | /Users/can/DeepCode/DeepTutor |
| DeepTutor UI | — | 3782 | /Users/can/DeepCode/DeepTutor/frontend |

## Prerequisites (One-Time Setup)

### DeepTutor Submodule Initialization

If `git submodule status` shows `no commits` for `DeepTutor`, initialize it:

bash
cd /Users/can/DeepCode
git submodule update --init


### Environment Verification Checklist

- [ ] DeepTutor submodule initialized: `git submodule status` in /Users/can/DeepCode
- [ ] `pip install -e ".[server]"` run from the DeepTutor submodule directory
- [ ] Frontend `node_modules` installed (run `npm install` if missing)
- [ ] MiniMax API key present in `.env` (see .env verification below)
- [ ] Port availability: `curl -s http://localhost:8000/health` and `curl -s http://localhost:8001/health`

## Startup Sequence

### 1. Check Existing Processes

bash
lsof -i :5173 -i :8000 -i :3782 -i :8001


Kill any stale processes before starting.

### 2. DeepCode Backend (port 8000)

bash
cd /Users/can/DeepCode/new_ui/backend
source venv/bin/activate
python main.py


Or alternatively:

bash
cd /Users/can/DeepCode && python -m deepcode_api &


Verify with `lsof -i :8000`.

### 3. DeepCode Frontend (port 5173)

bash
cd /Users/can/DeepCode/new_ui/frontend
npm run dev


### 4. DeepTutor Backend (port 8001)

bash
cd /Users/can/DeepCode/DeepTutor
pip install -e ".[server]"
deeptutor serve --port 8001


If `deeptutor serve` fails with uv version conflicts, use:

bash
pip install -e ".[server]"
python -m deeptutor_api


### 5. DeepTutor Frontend (port 3782)

bash
cd /Users/can/DeepCode/DeepTutor/frontend
npm install  # Required after submodule clone — node_modules often missing
NODE_OPTIONS="--max-old-space-size=4096" npm run dev


Or explicitly:

bash
node --max-old-space-size=4096 ./node_modules/next/dist/bin/next dev -p 3782


## Output Location

Generated code and papers are saved to:
- `/Users/can/DeepCode/deepcode_lab/papers/` — generated papers
- `/Users/can/DeepCode/deepcode_lab/` — other outputs (uploads, logs)

## Troubleshooting

**Frontend crashes with memory error:**
Add Node.js heap limit: `node --max-old-space-size=4096 ./node_modules/next/dist/bin/next dev -p <port>`

**API key appears masked in .env:**
The file viewer may show `***` but the actual key is present. Use:

bash
hexdump -C .env | grep sk-cp
# or
xxd .env | grep sk-cp


Real key format: `sk-cp-TJ9n77Ht2QK7u5U...`

**Backend starts but frontend won't:**
Check `npm install` was run in the frontend directory, then retry with memory flag above.

**DeepTutor not found at top level:**
DeepTutor is NOT a separate clone. It is a git submodule inside `/Users/can/DeepCode/DeepTutor/`. Run `git submodule update --init` if empty.

**DeepTutor submodule shows no commits:**
bash
cd /Users/can/DeepCode
git submodule update --init

