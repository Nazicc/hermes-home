import os
os.environ["LETTA_PG_URI"] = "postgresql://letta:letta_secret_2026@localhost:15432/letta"
os.environ["OPENAI_API_KEY"] = "sk-MAsMY4UuXuYumXZMldjw1fZQQe3TVjzR"
os.environ["OPENAI_BASE_URL"] = "https://token.sensenova.cn/v1"

import uvicorn
from letta.server.rest_api.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18283, log_level="info")
