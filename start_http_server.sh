#!/bin/bash
export SMTP_HOST="smtp.test.com"
export SMTP_PORT="587"
export SMTP_USERNAME="test@test.com"
export SMTP_PASSWORD="password"
export SMTP_USE_TLS="true"
export SMTP_FROM_EMAIL="test@test.com"

uv run python main.py --transport http --port 8003