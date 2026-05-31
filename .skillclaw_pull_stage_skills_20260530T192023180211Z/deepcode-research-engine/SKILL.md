---
name: deepcode-research-engine
description: "Use when transforming research papers into working code, running AI research automation workflows via the deepcode-hku pipeline, or interacting with the DeepTutor-backed research system at /Users/can/DeepCode. Triggered by: deepcode-hku pip package, DeepTutor submodule, research-to-code pipelines, or /Users/can/DeepCode directory. NOT for: general feature implementation (use opencode), deep research with web search (use deerflow-commander), or launching DeepCode/DeepTutor servers (use deepcode-deeptutor-launch)."
category: general
---

# DeepCode Research Engine (deepcode-hku)

## Environment

- **Install path**: `/Users/can/DeepCode`
- **Package name**: `deepcode-hku` (pip-installed, version 1.2.0)
- **Entry point**: `deepcode.py` (Python CLI wrapper)
- **Backend**: FastAPI via `uvicorn main:app --host 0.0.0.0 --port 8000`
- **Submodule**: `DeepTutor/` (HKU DeepTutor research tutoring system)
- **Platform**: macOS (`/Users/can/` path)

## Startup & Shutdown

bash
# Start backend (if not running)
cd /Users/can/DeepCode && uvicorn main:app --host 0.0.0.0 --port 8000

# Check if running
lsof -i :8000 | grep LISTEN

# Stop backend
pkill -f "uvicorn main:app.*port 8000"

# Via Python CLI
python /Users/can/DeepCode/deepcode.py --help


## API

- **Backend URL**: `http://localhost:8000`
- **Known endpoint**: `/docs` (FastAPI Swagger UI)
- **Note**: Not all endpoints are documented. Check `/docs` for available routes.

## Workflow Integration

1. Start the FastAPI backend if not running
2. Submit research papers or queries via the API
3. DeepTutor submodule handles tutoring/educational aspects
4. Results are returned via the API

## Constraints

- Backend must be running before API calls
- Port 8000 must be free
- DeepTutor submodule must be initialized (`git submodule update --init`)
- The `main:app` module is the FastAPI application entry point

