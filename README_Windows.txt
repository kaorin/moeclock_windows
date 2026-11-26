Moe Clock for Windows - feature-aligned port
==================================

Target: Windows 10/11, standalone one-file EXE.
GUI: PySide6 / Image rendering: Pillow / Packaging: PyInstaller.

BUILD
1. Install 64-bit Python 3.12 (or a compatible newer Python).
2. Open this folder in Explorer.
3. Double-click build_windows.bat.
4. The EXE will be created at dist\moeclock.exe.
   Build on Windows: PyInstaller produces a Windows executable only
   when run on Windows.

RUN
- Run dist\moeclock.exe.
- Right-click the clock to open Settings, change size, annotation position,
  enable hourly chime, toggle always-on-top, or exit.
- Select a wallpaper folder in Settings on first run.
- Settings are stored in %APPDATA%\moeclock\moeclock.xml.
- The default skin and bundled WAV files are included in the EXE.

NOTES
- This is the initial Windows port. It preserves the core features and the
  Linux 1.5.1.4 skin assets, SVG callouts, and sounds, but the original GTK layout has been replaced
  with a native Windows-style PySide6 settings dialog and context menu.
- For best results, use a folder containing JPG/PNG images as wallpaper source.
- Bundled skins are in skins\; SVG annotation.svg is rendered through QtSvg.
- Linux-compatible callout size, draw-frame, line width, and corner radius settings are supported.
- To use another skin, choose a folder containing frame.png, annotation.png,
  and logo.png.
Skin persistence: built-in skins are saved by stable skin folder name (builtin:<name>), not by PyInstaller temporary extraction path. External skins are saved as absolute paths.
