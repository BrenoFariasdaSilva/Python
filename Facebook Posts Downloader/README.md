# Facebook Posts Downloader

Downloads posts from the configured Facebook profile into:

```text
Outputs/
└── YYYY-MM-DD-Title/
    ├── post.json
    ├── photo_001.jpg
    ├── photo_002.jpg
    └── video_001.mp4
```

## Important Chrome behavior

Chrome 136+ blocks remote debugging against the normal default Chrome user-data directory. Because of that, an ordinary already-open personal Chrome profile cannot simply be attached by Playwright.

The program therefore uses this order:

1. Try `http://127.0.0.1:9222` in case Chrome was explicitly started with an allowed CDP configuration.
2. Otherwise open a dedicated persistent profile in `./.browser_profile/`.
3. On the first run, log in to Facebook in that automation browser.
4. Later executions reuse that dedicated authenticated profile.

No password or browser cookie is written to the post JSON files or application logs.

## Install

```powershell
make install
```

Or:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m playwright install chromium
```

## Run

```powershell
make run
```

Or:

```powershell
.\venv\Scripts\python.exe .\main.py
```

## Configuration

The principal constants are near the top of `main.py`:

- `PROFILE_URL`
- `PROFILE_DISPLAY_NAME`
- `CDP_ENDPOINT`
- `AUTOMATION_PROFILE_DIR`
- `OUTPUT_DIR`
- scroll/login/media timeout constants

## Reliability notes

Facebook's timeline DOM is private implementation detail and can change without notice. The downloader uses multiple selector/date/media fallbacks, records per-media failures in `post.json`, writes completed posts incrementally, and resumes from existing metadata on later runs.

For videos, Facebook may sometimes expose only segmented or blob-backed playback instead of a complete direct file. Partial HTTP 206/range responses are rejected so the program does not silently save corrupt videos; the failure is recorded in `post.json` instead.

## Git safety

`.browser_profile/`, `Outputs/`, `Logs/`, virtual environments, and Python caches are ignored so authenticated browser data is not accidentally committed.
