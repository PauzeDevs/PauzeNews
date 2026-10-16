[app]

title = PauzeNews
package.name = pauzenews
package.domain = devs.pauze
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,txt,md
source.exclude_dirs = .git,.github,.venv,venv,__pycache__,tests
version = 0.1.0
requirements = python3,kivy,requests,feedparser
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 35
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.enable_androidx = True
p4a.bootstrap = sdl2

[buildozer]

log_level = 2
warn_on_root = 1
