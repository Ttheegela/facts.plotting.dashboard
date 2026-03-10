# ─────────────────────────────────────────────────────────
# facts-viz — Lightweight FACTS Dashboard Generator
#
# Completely independent from the FACTS runtime image.
# Only contains what is needed to read .nc output files
# and generate a self-contained HTML dashboard.
#
# Build:
#   docker build -t facts-viz .
#
# Run (all SSPs under one root):
#   docker run --rm \
#     -v /your/exp.alt.emis:/data \
#     facts-viz --exp-root /data/ --output /data/dashboard.html
#
# Run (SSPs from separate runs):
#   docker run --rm \
#     -v /run1/coupling.ssp126:/ssp126 \
#     -v /run2/coupling.ssp585:/ssp585 \
#     facts-viz \
#       --ssp-dir /ssp126 \
#       --ssp-dir /ssp585 \
#       --output  /ssp126/dashboard.html
# ─────────────────────────────────────────────────────────

FROM python:3.11-slim

LABEL maintainer="FACTS Sea-Level Projections"
LABEL description="FACTS Dashboard Generator — standalone viz tool"

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the dashboard script
COPY facts_dashboard.py .

# Default output directory (users mount their data here)
VOLUME ["/data"]

ENTRYPOINT ["python", "facts_dashboard.py"]
