# -*- mode: python ; coding: utf-8 -*-
"""Сборка исполняемого файла.

    pyinstaller app.spec

Всё, что отличается от значений по умолчанию, собрано здесь, чтобы сборка
воспроизводилась одной командой и не зависела от того, какие ключи вспомнил
человек за клавиатурой.

Целевая среда: Windows 7 32-bit, Python 3.8.10 — последний, который на неё
ставится. Собирать надо именно в этой среде: PyInstaller кладёт в файл тот
интерпретатор, под которым запущен.
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    # Значок окна нужен файлом в рантайме: значок в ресурсах .exe его
    # не заменяет, Tk показывает своё перо.
    datas=[('assets/icon.ico', 'assets'), ('assets/icon.png', 'assets')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # Утилита живёт на стандартной библиотеке. Тяжёлое, что PyInstaller
    # иногда затягивает сам, исключаем: на размер влияет заметно.
    excludes=[
        'numpy', 'pandas', 'matplotlib', 'scipy', 'PIL',
        'pytest', 'setuptools', 'pip',
        'unittest', 'pydoc', 'doctest',
        'email', 'http', 'xml', 'urllib', 'ssl', 'socket',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FinnPowerCounter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX усиливает ложные срабатывания антивирусов
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # оператору консоль не нужна
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
