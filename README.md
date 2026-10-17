<div align="center">

# PauzeNews

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Inter&weight=600&size=22&duration=2600&pause=700&color=4C8DFF&center=true&vCenter=true&width=680&lines=PauzeNews" alt="Animated header: PauzeNews">
</p>

### The world, in context.

A premium, Android-first news reader with a charcoal canvas, warm metallic-gold accents, crisp editorial cards, and a clean, Apple Developer-inspired visual hierarchy.

<p>
  <a href="https://github.com/PauzeDevs/PauzeNews/actions/workflows/tests.yml"><img alt="Python tests" src="https://github.com/PauzeDevs/PauzeNews/actions/workflows/tests.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml"><img alt="Android APK build" src="https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml/badge.svg?branch=main"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Kivy" src="https://img.shields.io/badge/UI-Kivy-4B8BBE">
  <img alt="Platform-Android" src="https://img.shields.io/badge/Platform-Android-3DDC84?logo=android&logoColor=white">
  <img alt="License-Proprietary" src="https://img.shields.io/badge/License-Proprietary-D9A441">
</p>

<p>
  <a href="https://github.com/PauzeDevs/PauzeNews/releases"><strong>Download latest release</strong></a>
  · <a href="https://github.com/PauzeDevs/PauzeNews/actions">Workflow runs</a>
  · <a href="https://github.com/PauzeDevs/PauzeNews/issues">Report a bug</a>
  · <a href="https://github.com/PauzeDevs/PauzeNews/blob/main/LICENSE">License</a>
</p>

<img alt="Animated gold line" src="https://capsule-render.vercel.app/api?type=rect&color=0:9A6B20,50:D9A441,100:F2D58A&height=3&section=header">

</div>

## Overview

PauzeNews is a Python-first news reader built with **Kivy**. It brings topic-based headlines into one Android-friendly interface, with local search, bookmarks, cached stories, publisher attribution, and links to original articles.

The interface pairs near-black and charcoal surfaces with a restrained metallic-gold accent, high-contrast typography, rounded topic pills, and compact full-width story cards. Its visual direction takes cues from Apple Developer's clarity and hierarchy without copying Apple's branding. The Android layout reserves safe space around system bars and renders a small first batch to keep startup lightweight.

> **Release verification:** Official APKs are provided through GitHub Releases. Every push to `main` builds and checks an APK; commits marked `[release]` publish stable releases, and commits marked `[pre-release]` publish versioned pre-releases with the built APK. Physical-device installation and reader behavior should also be verified.

## Features

- **Topic feeds:** For You, World, India, Technology, Science, Business, and Aviation.
- **No API key required:** Google News RSS topic feeds; NASA remains a secondary Science source.
- **Publisher attribution:** Uses source metadata when supplied by a feed.
- **Search:** Filter cached headlines by title, publisher, or summary.
- **In-app article reader:** Open publisher pages in a dedicated native Android reader, navigate page history, and return to headlines with Back. If WebView initialization fails on a device, the app attempts to open the story in the system browser.
- **Bookmarks:** Save stories locally using SQLite.
- **Offline-friendly cache:** Previously fetched headlines may remain available when refresh fails.
- **Honest error states:** Feed failures are shown instead of inventing headlines.
- **Premium editorial UI:** Near-black and charcoal surfaces, warm gold highlights, softly outlined cards, rounded topic pills, and compact full-width story layouts inspired by Apple Developer's clean hierarchy.
- **Android packaging:** Buildozer and python-for-android build the APK.
- **Automated checks:** GitHub Actions compiles Python modules and runs unit tests.

## Install PauzeNews on Android

### Option 1 — Download from GitHub Releases (recommended)

1. Open the **[PauzeNews Releases page](https://github.com/PauzeDevs/PauzeNews/releases)**.
2. Open the latest release. Prefer a release marked **Latest**.
3. Under **Assets**, download the file ending in `.apk` (not the source-code ZIP or TAR.GZ).
4. Once downloaded, open the APK on your Android device.
5. If Android prompts you, allow your browser or file manager to **install unknown apps** for this installation, then return and install the APK.
6. Open PauzeNews and connect to the internet to load headlines.

**Only use APK files attached to the official GitHub Releases page.** The app's APK is not distributed through GitHub Actions artifact downloads. If there is no release or no APK under its Assets, a release build has not been published yet.

### Troubleshooting installation

- **“App not installed”:** Check that your device is compatible and that you have enough free storage. If an older build is installed, Android may reject an APK signed with a different key; back up anything important before uninstalling the old version.
- **“For your security, your phone is not allowed to install unknown apps”:** Open the Android settings prompt for the app you used to download the APK and enable permission to install unknown apps, then retry.
- **No APK in Assets:** Check back after the release build finishes, or report the issue in [GitHub Issues](https://github.com/PauzeDevs/PauzeNews/issues).

## Build from source

This section is for developers. Building locally is separate from downloading the official release APK.

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

The locally built APK is normally placed in the **bin/** directory. Locally built APKs are not official releases unless published by PauzeDevs through the repository's release process.

## Live project status

These badges are linked to GitHub Actions. Open them to see workflow results and logs.

| Workflow | Purpose |
| --- | --- |
| [Python tests](https://github.com/PauzeDevs/PauzeNews/actions/workflows/tests.yml) | Compile modules and run unit tests |
| [Android APK](https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml) | Build Android APKs; version-tagged builds attach APKs to GitHub Releases |
| [All workflow runs](https://github.com/PauzeDevs/PauzeNews/actions) | Inspect recent runs and logs |

Badges update automatically when GitHub Actions reports a new status. They show workflow status, not a guarantee that every device or network will work.

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
    └── android-apk.yml         # Android APK build and release workflow
```

## Privacy and permissions

- The current MVP does not require user accounts.
- Bookmarks and cached articles are stored locally in SQLite.
- Android internet permission is used to retrieve feeds.
- Never commit API keys, credentials, signing keys, or other secrets.

## Special links

- **[Download latest APK release](https://github.com/PauzeDevs/PauzeNews/releases)**
- **[All releases and version history](https://github.com/PauzeDevs/PauzeNews/releases)**
- **[Android APK workflow and logs](https://github.com/PauzeDevs/PauzeNews/actions/workflows/android-apk.yml)**
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
