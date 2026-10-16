# PauzeNews

**A Python-first Android news reader by PauzeDevs.**

PauzeNews is being built as a lightweight Android app focused on a clean reading experience, real headlines, clear publisher attribution, and a low operating budget.

## Planned MVP

- Multi-category RSS news feed
- Publisher, publication date, and original article link
- Search and category filters
- Local bookmarks and cached articles using SQLite
- Refresh/error states without fabricated headlines
- Dark, editorial-style interface
- Android APK packaging with Buildozer
- Automated tests for feed parsing and local storage

## Technology

- Python
- Kivy for the Android UI
- RSS/Atom parsing
- SQLite for local persistence
- Buildozer / python-for-android for APK builds
- GitHub Actions for tests and build workflow

## Development status

Early development. The app must be tested on a real Android device before it is considered beta-ready. News availability depends on source uptime, feed terms, and connectivity.

## Run locally

Python 3.11 or newer is recommended for desktop development.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Automated checks and APK builds

- The `Python tests` workflow compiles the Python modules and runs unit tests on pushes and pull requests to `main`.
- The `Android APK` workflow can be started manually from GitHub Actions and is also configured for `v*` tags. It builds a debug APK and uploads it as a short-lived workflow artifact; it does not publish a GitHub Release or Play Store release.

## Build an Android APK

Buildozer is most straightforward on Linux. Android packaging on macOS can be done through a Linux virtual machine or CI runner.

```bash
pip install buildozer
buildozer android debug
```

The first Android build downloads the Android toolchain and can take a while. See `buildozer.spec` for package settings.

## News sources

PauzeNews currently uses Google News RSS topic feeds for World, India, Technology, Science, and Business, plus an Aviation search feed. These feeds do not require an API key. Publisher attribution is taken from each RSS item's source metadata when supplied; NASA is retained as a secondary Science feed.

The app displays headlines, short excerpts where supplied by feeds, publisher names, timestamps, and links to the original articles. It does not intentionally republish full articles. Source availability depends on connectivity and feed uptime, and feed terms and attribution requirements should be reviewed before public release.

## Privacy

The MVP does not require user accounts. Bookmarks and preferences are stored locally on the device. Do not add API keys or secrets to the repository.

## License

A license has not yet been selected. Until one is added, the repository should not be assumed to grant permission to redistribute the source code.
