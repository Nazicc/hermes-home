#!/bin/bash
# Hermes login startup — managed by launchd
exec > /Users/can/.hermes/logs/startup.log 2>&1
date

cd /Users/can/.hermes
nohup ./hermes-agent/venv/bin/python -m hermes_cli.main gateway run &>/Users/can/.hermes/logs/gateway.log &
sleep 5

cd /Users/can/.skillclaw
nohup ./.venv/bin/skillclaw start &>/Users/can/.skillclaw/logs/skillclaw.log &
sleep 3

PYTHONPATH=/Users/can/DeepCode:\$PYTHONPATH nohup /Users/can/.hermes/mcp-venv/bin/python -m uvicorn new_ui.backend.main:app --host 0.0.0.0 --port 8000 &>/Users/can/.hermes/logs/newui.log &
sleep 2

nohup /Users/can/.hermes/mcp-venv/bin/python3 /Users/can/.hermes/mcp-venv/bin/deeptutor serve --port 8001 &>/Users/can/.hermes/logs/deeptutor.log &
