[app]

title = PauzeNews
package.name = pauzenews
package.domain = devs.pauze
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,txt,md
source.exclude_dirs = .git,.github,.venv,venv,__pycache__,tests
version = 1.0.3
requirements = python3,kivy,certifi,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
# Keep target API 34 while using the pinned SDL2 bootstrap. API 35 enables
# enforced edge-to-edge rendering on Android 15+, which requires explicit
# system-bar inset support not provided by this pinned python-for-android build.
android.api = 34
# Keep API 24 for compatibility with the Android native runtime.
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.enable_androidx = True
p4a.bootstrap = sdl2
# The latest p4a master selects Python 3.14 and currently fails packaging charset-normalizer.
# Pin to a known release using the Python 3.11 recipe until upstream Android wheels are compatible.
p4a.branch = v2024.01.21

[buildozer]

log_level = 2
warn_on_root = 1
