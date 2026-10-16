[app]

title = PauzeNews
package.name = pauzenews
package.domain = devs.pauze
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,txt,md
source.exclude_dirs = .git,.github,.venv,venv,__pycache__,tests
version = 0.1.0
requirements = python3,kivy
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 35
# Python 3.14 uses pwritev/preadv in remote debugging; Android NDK exposes these from API 24.
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.enable_androidx = True
p4a.bootstrap = sdl2

[buildozer]

log_level = 2
warn_on_root = 1
