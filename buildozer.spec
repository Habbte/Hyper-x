[app]
title = Hyper X
package.name = hyperxadder
package.domain = com.habtex

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt

version = 1.0.0

requirements = python3,\
    kivy==2.2.1,\
    kivymd==1.1.1,\
    telethon==1.34.0,\
    cryptg,\
    pyaes,\
    rsa,\
    colorama

# Orientation
orientation = portrait

# Android-specific
android.permissions = INTERNET,\
    RECEIVE_BOOT_COMPLETED,\
    FOREGROUND_SERVICE,\
    WAKE_LOCK,\
    READ_EXTERNAL_STORAGE,\
    WRITE_EXTERNAL_STORAGE

android.api = 33
android.minapi = 26
android.ndk = 25b
android.sdk = 33
android.ndk_api = 21

android.archs = arm64-v8a, armeabi-v7a

# Keep app alive in background
android.wakelock = True
android.foreground_service = True
android.foreground_service_type = dataSync

# Icons (place 512x512 icon.png in assets/)
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png

# Gradle extras for foreground service
android.gradle_dependencies = androidx.core:core:1.10.1

[buildozer]
log_level = 2
warn_on_root = 1
