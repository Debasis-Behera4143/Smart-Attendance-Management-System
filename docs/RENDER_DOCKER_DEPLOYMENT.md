# Render Docker Deployment

This project is configured for Docker deployment on Render.

## 1. Files used

- `Dockerfile`
- `render.yaml`
- `requirements.txt`

## 2. Deploy from Render dashboard

1. Open Render.
2. Click `New` -> `Blueprint`.
3. Connect your GitHub repo.
4. Render reads `render.yaml` and builds from `Dockerfile`.
5. Deploy.

## 3. Important runtime notes

- The app listens on Render's dynamic `PORT` automatically.
- Flask app entry is `web.app:app` via Gunicorn.
- SQLite files are ephemeral on free containers; attach a persistent disk for retained data.

## 4. If build is slow/fails on dlib

1. Keep Docker build (not Python env).
2. Re-deploy once (network/build cache hiccups are common).
3. If needed, move face-recognition features to a background/local node and keep Render for dashboard/reporting APIs.
