FROM python:3.12-slim

WORKDIR /app

# Install lightweight runtime tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY pyproject.toml .
COPY src ./src
COPY workspace ./workspace
# Bake .agents into image at a staging path — will be synced to volume on startup
COPY .agents /app/.agents_image

# Install package in editable mode
RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src

EXPOSE 8000

# Entrypoint: seed .agents volume from image on first start (preserves runtime-installed skills)
COPY <<'EOF' /app/entrypoint.sh
#!/bin/sh
set -e

# If .agents/skills directory is empty or missing, seed from image
if [ ! -d "/app/.agents/skills" ] || [ -z "$(ls -A /app/.agents/skills 2>/dev/null)" ]; then
  echo "[LXION] Seeding .agents from image..."
  cp -r /app/.agents_image/. /app/.agents/
  echo "[LXION] .agents seeded OK"
else
  # Always sync built-in skills from image (overwrite only image skills, keep runtime skills)
  if [ -d "/app/.agents_image/skills" ]; then
    for skill_dir in /app/.agents_image/skills/*/; do
      skill_name=$(basename "$skill_dir")
      if [ ! -d "/app/.agents/skills/$skill_name" ]; then
        echo "[LXION] Syncing new built-in skill: $skill_name"
        cp -r "$skill_dir" "/app/.agents/skills/"
      fi
    done
  fi
fi

exec python -m uvicorn lxion.main:app --host 0.0.0.0 --port 8000
EOF
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]