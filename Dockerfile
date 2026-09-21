FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY sceneEditor.py styles.json ./

# Manuscript in, suggestions out: mount a host folder at /data
ENV MANUSCRIPT_FILE=/data/novel.docx \
    OUTPUT_FILE=/data/scene_suggestions_patch.md

VOLUME /data

CMD ["python", "sceneEditor.py"]
