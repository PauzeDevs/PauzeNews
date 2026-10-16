<div align="center">

# PauzeNews

### The world, in context.

A lightweight, Android-first news reader with a clean, gold-accented editorial interface.

<p>
  <a href="https://github.com/PauzeDevs/PauzeNews/actions/workflows/tests.yml"><img alt="Python tests" src="https://github.com/PauzeDevs/PauzeNews/actions/workflows/tests.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml"><img alt="Android APK build" src="https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml/badge.svg?branch=main"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Kivy" src="https://img.shields.io/badge/UI-Kivy-4B8BBE">
  <img alt="Platform-Android" src="https://img.shields.io/badge/Platform-Android-3DDC84?logo=android&logoColor=white">
  <img alt="License-Proprietary" src="https://img.shields.io/badge/License-Proprietary-D9A441">
</p>

<p>
  <a href="https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml"><strong>Build APK</strong></a>
  · <a href="https://github.com/PauzeDevs/PauzeNews/actions">Workflow runs</a>
  · <a href="https://github.com/PauzeDevs/PauzeNews/issues">Report a bug</a>
  · <a href="https://github.com/PauzeDevs/PauzeNews/blob/main/LICENSE">License</a>
</p>

<img alt="Animated gold line" src="https://capsule-render.vercel.app/api?type=rect&color=0:9A6B20,50:D9A441,100:F2D58A&height=3&section=header">

</div>

## Overview

PauzeNews is a Python-first news reader built with **Kivy**. It brings topic-based headlines into one Android-friendly interface, with local search, bookmarks, cached stories, publisher attribution, and links to original articles.

The interface uses a dark graphite background with restrained gold accents, generous spacing, and an editorial card layout.

> **Development status:** Early development. A successful CI build does not replace testing on a physical Android device. The Android workflow creates a debug APK artifact; it does not publish a GitHub Release or Play Store release.

## Features

- **Topic feeds:** For You, World, India, Technology, Science, Business, and Aviation.
- **No API key required:** Google News RSS topic feeds; NASA remains a secondary Science source.
- **Publisher attribution:** Uses source metadata when supplied by a feed.
- **Search:** Filter cached headlines by title, publisher, or summary.
- **Bookmarks:** Save stories locally using SQLite.
- **Offline-friendly cache:** Previously fetched headlines may remain available when refresh fails.
- **Honest error states:** Feed failures are shown instead of inventing headlines.
- **Gold editorial UI:** Dark surfaces, warm gold highlights, rounded story cards, and clear action buttons.
- **Android packaging:** Buildozer and python-for-android build the APK.
- **Automated checks:** GitHub Actions compiles Python modules and runs unit tests.

## Live project status

These badges are linked to GitHub Actions. Open them to see workflow results and logs.

| Workflow | Purpose |
| --- | --- |
| [Python tests](https://github.com/PauzeDevs/PauzeNews/actions/workflows/tests.yml) | Compile modules and run unit tests |
| [Android APK](https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml) | Build and upload a debug APK artifact |
| [All workflow runs](https://github.com/PauzeDevs/PauzeNews/actions) | Inspect recent runs, logs, and artifacts |

Badges update automatically when GitHub Actions reports a new status. They show workflow status, not a guarantee that every device or network will work.

## Install PauzeNews on Android

### Option 1 — Download a successful APK artifact

1. Open [Android APK workflow runs](https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml).
2. Open a run marked **Success**.
3. Scroll to **Artifacts** and download **pauzenews-debug-apk**.
4. Extract the ZIP and locate the APK file.
5. Transfer the APK to your Android device and open it. If prompted, allow installation from that source for this install.
6. Launch PauzeNews and connect to the internet to fetch headlines.

**Note:** Workflow artifacts expire after 14 days. If no successful run or artifact is available, start a new build using the workflow link above.

### Option 2 — Start an APK build

1. Visit the [Android APK workflow](https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml).
2. Select **Run workflow**, choose the main branch, and start it.
3. Wait for the run to finish successfully.
4. Download the **pauzenews-debug-apk** artifact from that run.

Builds can take several minutes because Android tooling and Python-for-Android dependencies must be downloaded and compiled.

### Option 3 — Run from source

Linux is the recommended build environment. On macOS, use a Linux VM or CI runner. On Windows, use WSL2 or Linux for Android packaging.

Requirements: Python 3.11, Java 17 for Android packaging, Git, system build dependencies, and internet access.

```bash
git clone https://github.com/PauzeDevs/PauzeNews.git
cd PauzeNews
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

To build a debug APK on supported Linux:

```bash
python -m pip install "Cython==0.29.36" buildozer
buildozer -v android debug
```

The APK is normally placed in the **bin/** directory. The first build may take significantly longer than later builds.

## Run the tests

From the repository root:

```bash
python -m compileall -q main.py news_core.py tests
python -m unittest discover -s tests -v
```

See the [Python tests workflow](https://github.com/PauzeDevs/PauzeNews/actions/workflows/tests.yml) for CI logs.

## News sources and attribution

Current feeds are configured in [news_core.py](news_core.py):

| Category | Feed |
| --- | --- |
| World | Google News RSS |
| India | Google News RSS |
| Technology | Google News RSS |
| Science | Google News RSS, with NASA as a secondary source |
| Business | Google News RSS |
| Aviation | Google News RSS search feed |

Feeds are fetched over HTTPS. Availability depends on connectivity and upstream services. Headlines, publisher names, summaries, and links may be subject to third-party terms and rights. PauzeNews links readers to original articles and does not intentionally republish full articles.

## Project structure

```text
PauzeNews/
├── main.py                     # Kivy application and UI
├── news_core.py                # RSS/Atom fetching, parsing, SQLite storage
├── requirements.txt            # Python runtime dependencies
├── buildozer.spec              # Android package/build configuration
├── tests/
│   └── test_news_core.py       # Feed parsing and storage tests
└── .github/workflows/
    ├── tests.yml               # Python CI
    └── android-apk.yml         # Android debug APK workflow
```

## Privacy and permissions

- The current MVP does not require user accounts.
- Bookmarks and cached articles are stored locally in SQLite.
- Android internet permission is used to retrieve feeds.
- Never commit API keys, credentials, signing keys, or other secrets.

## Special links

- **[Repository](https://github.com/PauzeDevs/PauzeNews)**
- **[Download/build Android APK](https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml)**
- **[Latest workflow runs](https://github.com/PauzeDevs/PauzeNews/actions)**
- **[Python test results](https://github.com/PauzeDevs/PauzeNews/actions/workflows/tests.yml)**
- **[Browse source code](https://github.com/PauzeDevs/PauzeNews/tree/main)**
- **[Open an issue](https://github.com/PauzeDevs/PauzeNews/issues/new/choose)**
- **[Security policy](https://github.com/PauzeDevs/PauzeNews/security)**
- **[License](LICENSE)**

## Contributing and license

PauzeNews uses a proprietary license. Read [LICENSE](LICENSE) before using or sharing the code. Permission beyond the stated personal-use terms must be obtained from PauzeDevs.

Copyright © 2026 PauzeDevs. All rights reserved.

<div align="center">

<img alt="Animated gold footer" src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=24,25,26&height=100&section=footer">

**PauzeNews** · *The world, in context.*

</div>
