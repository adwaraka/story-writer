# Scene Editor

Rewrites a scene from your manuscript using a local Ollama model. Ollama runs natively on
your Mac (for GPU speed); only the script runs in Docker.

## Setup

1. Put your manuscript in `./data/` (default name: `novel.docx`).
2. Make sure Ollama is running and the model is pulled: `ollama pull hermes3`
3. Edit `.env`. It holds every setting: anchors, scene type, detail level, styles, model.
   (`.env` is a hidden file. In Finder press Cmd+Shift+. to show it.)

Keep `.env` values **unquoted** and comments on their own lines, so `docker compose` and
`docker run --env-file` read it identically.

Output is written to `./data/scene_suggestions_patch.md`.

## Run with Docker Compose

```bash
docker compose build
docker compose run --rm scene-editor
```

Rebuild whenever you change `sceneEditor.py`, since the script is baked into the image.
Changes to `.env` and `styles.json` take effect immediately, with no rebuild.

## Run with plain Docker (no compose)

```bash
docker build -t scene-editor .

docker run --rm \
  --env-file .env \
  --add-host=host.docker.internal:host-gateway \
  -v "$(pwd)/data:/data" \
  -v "$(pwd)/styles.json:/app/styles.json:ro" \
  scene-editor
```

## One-off overrides

`-e` beats `.env` in both tools, so you can tweak a single run without editing the file:

```bash
docker compose run --rm -e SCENE_TYPE=fight -e DETAIL_LEVEL=3 -e FIGHT_STYLE=swordplay scene-editor

docker run --rm --env-file .env -e TAGS="teasing, praise" \
  --add-host=host.docker.internal:host-gateway \
  -v "$(pwd)/data:/data" -v "$(pwd)/styles.json:/app/styles.json:ro" scene-editor
```

## Adding styles

Edit `styles.json` (genres, fightStyles, romanceStyles, tags), or type free text straight
into the matching `.env` field.
