# -*- coding: utf-8 -*-
"""Moe Clock for Windows - PySide6 port aligned with Linux 1.5.1.4."""
from __future__ import annotations

import ast
import datetime as dt
import locale
import os
import random
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from PySide6.QtCore import Qt, QTimer, QUrl, QPointF, Signal, QLocale
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap, QImage, QPainter, QColor, QPen, QFontMetricsF
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QDialog, QDialogButtonBox,
    QFileDialog, QFontDialog, QFormLayout, QHBoxLayout, QLabel, QMainWindow,
    QMenu, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget, QComboBox
)

APP_NAME = "Moe Clock"
VERSION = "1.5.1.4-win"
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
USER_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "moeclock"
CONFIG_FILE = USER_DIR / "moeclock.xml"

DEFAULTS = {
    "x_pos": "0", "y_pos": "0", "x_size": "320", "y_size": "200",
    "wallpaper_path": str(Path.home() / "Pictures"),
    "use_wallpaper": "[]", "font": "Meiryo", "color": "#F366FF",
    "notice": "True", "alwaysTop": "False", "weekOffset": "-10",
    "skin": "builtin:default", "sound": str(APP_DIR / "sound" / "sachika_01.wav"),
    "windowDecorate": "True", "annotationType": "0", "soundCutOut": "False",
    "calloutSize": "100%", "drawFrame": "False", "lineWidth": "4",
    "round": "12", "roundWindow": "False",
}

WEEK = ["(月)", "(火)", "(水)", "(木)", "(金)", "(土)", "(日)"]


def as_bool(value):
    return str(value).lower() in ("true", "1", "yes", "on")


class Config:
    def __init__(self):
        self.values = DEFAULTS.copy()
        if CONFIG_FILE.exists():
            try:
                root = ET.parse(CONFIG_FILE).getroot()
                options = root.find("options")
                if options is not None:
                    for key in DEFAULTS:
                        node = options.find(key)
                        if node is not None and node.text is not None:
                            self.values[key] = node.text
            except Exception:
                pass

    def get(self, key):
        return self.values.get(key, DEFAULTS[key])

    def set(self, key, value):
        self.values[key] = str(value)

    def save(self):
        USER_DIR.mkdir(parents=True, exist_ok=True)
        root = ET.Element("moeclock")
        opts = ET.SubElement(root, "options")
        for key in DEFAULTS:
            ET.SubElement(opts, key).text = self.get(key)
        ET.ElementTree(root).write(CONFIG_FILE, encoding="utf-8", xml_declaration=True)


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.clock = parent
        self.setWindowTitle("Moe Clock - 設定")
        self.setMinimumWidth(480)
        form = QFormLayout()

        self.wallpaper = QLabel(self.clock.wallpaper_dir)
        btn_wall = QPushButton("参照…")
        btn_wall.clicked.connect(self.choose_wallpaper)
        row = QHBoxLayout()
        row.addWidget(self.wallpaper, 1)
        row.addWidget(btn_wall)
        form.addRow("壁紙フォルダー", row)

        self.skin_combo = QComboBox()
        self.skin_paths = []
        for skin_path in self.clock.available_skins():
            self.skin_combo.addItem(Path(skin_path).name, skin_path)
            self.skin_paths.append(skin_path)
        current_skin = str(Path(self.clock.skin_dir).resolve())
        selected_index = -1
        for index in range(self.skin_combo.count()):
            item_path = str(Path(self.skin_combo.itemData(index)).resolve())
            if item_path == current_skin:
                selected_index = index
                break
        if selected_index < 0:
            self.skin_combo.addItem(f"Custom: {Path(self.clock.skin_dir).name}", self.clock.skin_dir)
            selected_index = self.skin_combo.count() - 1
        self.skin_combo.setCurrentIndex(selected_index)

        btn_skin = QPushButton("参照…")
        btn_skin.clicked.connect(self.choose_skin)
        row = QHBoxLayout()
        row.addWidget(self.skin_combo, 1)
        row.addWidget(btn_skin)
        form.addRow("スキン", row)

        self.font_button = QPushButton(self.clock.font_name)
        self.font_button.clicked.connect(self.choose_font)
        form.addRow("フォント", self.font_button)

        self.color_button = QPushButton(self.clock.color)
        self.color_button.clicked.connect(self.choose_color)
        self.skin_combo.currentIndexChanged.connect(self.update_skin_color)
        form.addRow("文字色", self.color_button)

        self.offset = QSpinBox()
        self.offset.setRange(-200, 200)
        self.offset.setValue(self.clock.week_offset)
        form.addRow("曜日の位置調整", self.offset)

        self.sound = QLabel(self.clock.sound_file)
        btn_sound = QPushButton("参照…")
        btn_sound.clicked.connect(self.choose_sound)
        btn_sound_play = QPushButton("再生")
        btn_sound_play.clicked.connect(self.preview_sound)
        row = QHBoxLayout()
        row.addWidget(self.sound, 1)
        row.addWidget(btn_sound)
        row.addWidget(btn_sound_play)
        form.addRow("毎時チャイム音声（WAV）", row)

        self.callout_size = QSpinBox()
        self.callout_size.setRange(25, 200)
        self.callout_size.setSuffix("%")
        self.callout_size.setValue(int(float(self.clock.callout_size.replace("%", ""))))
        form.addRow("吹き出しサイズ", self.callout_size)

        self.draw_frame = QCheckBox("スキンの枠の代わりに角丸枠を描画する")
        self.draw_frame.setChecked(self.clock.draw_frame)
        form.addRow("", self.draw_frame)

        self.line_width = QSpinBox()
        self.line_width.setRange(1, 20)
        self.line_width.setValue(self.clock.line_width)
        form.addRow("枠線の太さ", self.line_width)

        self.round = QSpinBox()
        self.round.setRange(0, 100)
        self.round.setValue(self.clock.round_radius)
        form.addRow("枠線の角丸半径", self.round)

        self.cutout = QCheckBox("音声再生前に無音WAVを再生する（音声デバイス互換性）")
        self.cutout.setChecked(self.clock.sound_cutout)
        form.addRow("", self.cutout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("OK")
        buttons.button(QDialogButtonBox.Cancel).setText("キャンセル")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def update_skin_color(self, _index=None):
        """Update the color control immediately when the selected skin changes."""
        skin_path = self.skin_combo.currentData()
        if skin_path:
            color = self.clock.load_skin_color(skin_path, fallback=self.color_button.text())
            self.color_button.setText(color)

    def choose_wallpaper(self):
        p = QFileDialog.getExistingDirectory(self, "壁紙フォルダーを選択", self.wallpaper.text())
        if p:
            self.wallpaper.setText(p)

    def choose_skin(self):
        current = self.skin_combo.currentData() or str(APP_DIR / "skins")
        p = QFileDialog.getExistingDirectory(self, "スキンフォルダーを選択", current)
        if p:
            label = f"Custom: {Path(p).name}"
            existing = -1
            for index in range(self.skin_combo.count()):
                item_path = self.skin_combo.itemData(index)
                if item_path and str(Path(item_path).resolve()) == str(Path(p).resolve()):
                    existing = index
                    break
            if existing < 0:
                self.skin_combo.addItem(label, p)
                existing = self.skin_combo.count() - 1
            self.skin_combo.setCurrentIndex(existing)

    def choose_font(self):
        ok, font = QFontDialog.getFont(QFont(self.clock.font_name), self)
        if ok:
            self.font_button.setText(font.family())

    def choose_color(self):
        from PySide6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self.clock.color), self)
        if c.isValid():
            self.color_button.setText(c.name().upper())

    def preview_sound(self):
        """Play the WAV currently shown in the settings dialog."""
        path = Path(self.sound.text())
        if not path.is_file():
            QMessageBox.warning(self, "音声ファイル", "再生するWAVファイルが見つかりません。")
            return
        self.clock._play_file(path)

    def choose_sound(self):
        p, _ = QFileDialog.getOpenFileName(self, "WAVファイルを選択", self.sound.text(), "WAVファイル (*.wav);;すべてのファイル (*.*)")
        if p:
            self.sound.setText(p)


class ClickableLabel(QLabel):
    """Image display label that emits a signal on a left mouse click."""
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class MoeClock(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        g = self.cfg.get
        self.wallpaper_dir = g("wallpaper_path")
        self.used_wallpapers = self._parse_list(g("use_wallpaper"))
        self.font_name = g("font")
        self.color = g("color")
        self.notice = as_bool(g("notice"))
        self.always_top = as_bool(g("alwaysTop"))
        self.week_offset = int(g("weekOffset"))
        # Resolve the saved skin independently of PyInstaller's one-file
        # extraction directory, which changes on every application launch.
        self.skin_dir = self.resolve_skin_path(g("skin"))
        self.color = self.load_skin_color(self.skin_dir, fallback=self.color)
        self.sound_file = g("sound")
        self.decorated = as_bool(g("windowDecorate"))
        self.annotation_type = int(g("annotationType"))
        self.sound_cutout = as_bool(g("soundCutOut"))
        self.callout_size = g("calloutSize")
        self.draw_frame = as_bool(g("drawFrame"))
        self.line_width = int(g("lineWidth"))
        self.round_radius = int(g("round"))
        self.round_window = as_bool(g("roundWindow"))
        self.last_minute = -1
        self.last_chime_hour = None
        self.current_wallpaper = None
        self._sound = QSoundEffect(self)
        self._sound.setLoopCount(1)
        self._sound.setVolume(1.0)
        self._sound_pending = False
        self._sound.statusChanged.connect(self._on_sound_status_changed)

        self.view = ClickableLabel()
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_menu)
        self.view.clicked.connect(self.change_wallpaper)
        self.setCentralWidget(self.view)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(APP_DIR / "moeclock.png")))
        self.display_limit = (max(280, int(g("x_size"))), max(88, int(g("y_size"))))
        self.resize(*self.display_limit)
        self.move(int(g("x_pos")), int(g("y_pos")))
        self._apply_window_flags()
        self._build_menu()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(250)
        self.change_wallpaper()
        self.tick()
        # Wait until Qt has laid out the central widget before fitting the window.
        QTimer.singleShot(0, self._resize_to_wallpaper)

    @staticmethod
    def _parse_list(value):
        try:
            result = ast.literal_eval(value)
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def _apply_window_flags(self):
        flags = Qt.Window
        if not self.decorated:
            flags |= Qt.FramelessWindowHint
        if self.always_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _build_menu(self):
        self.menu = QMenu(self)
        settings = self.menu.addAction("設定…")
        settings.triggered.connect(self.open_settings)
        self.notice_action = self.menu.addAction("毎時チャイム")
        self.notice_action.setCheckable(True)
        self.notice_action.setChecked(self.notice)
        self.notice_action.toggled.connect(lambda v: setattr(self, "notice", v))
        self.top_action = self.menu.addAction("常に手前に表示")
        self.top_action.setCheckable(True)
        self.top_action.setChecked(self.always_top)
        self.top_action.toggled.connect(self.toggle_top)
        self.decorate_action = self.menu.addAction("タイトルバーを表示")
        self.decorate_action.setCheckable(True)
        self.decorate_action.setChecked(self.decorated)
        self.decorate_action.toggled.connect(self.toggle_decorate)

        size_menu = self.menu.addMenu("ウィンドウサイズ")
        for label, size in [("極小", (280, 88)), ("小", (320, 180)),
                            ("中", (400, 225)), ("大", (480, 270)),
                            ("特大", (640, 360))]:
            a = size_menu.addAction(label)
            a.triggered.connect(lambda checked=False, s=size: self.set_display_size(s))
        pos_menu = self.menu.addMenu("吹き出しの位置")
        for label, value in [("左上", 3), ("右上", 1), ("左下", 2), ("右下", 0)]:
            a = pos_menu.addAction(label)
            a.triggered.connect(lambda checked=False, v=value: self.set_annotation(v))
        self.menu.addSeparator()
        about = self.menu.addAction("このアプリについて")
        about.triggered.connect(self.about)
        quit_action = self.menu.addAction("終了")
        quit_action.triggered.connect(self.close)

    def show_menu(self, pos):
        self.menu.exec(self.view.mapToGlobal(pos))

    def toggle_top(self, value):
        self.always_top = value
        self._apply_window_flags()

    def toggle_decorate(self, value):
        self.decorated = value
        self._apply_window_flags()

    def set_annotation(self, value):
        self.annotation_type = value
        self.render()

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.wallpaper_dir = dlg.wallpaper.text()
            self.skin_dir = dlg.skin_combo.currentData() or self.skin_dir
            self.color = dlg.color_button.text()
            self.font_name = dlg.font_button.text()
            self.week_offset = dlg.offset.value()
            self.sound_file = dlg.sound.text()
            self.sound_cutout = dlg.cutout.isChecked()
            self.callout_size = f"{dlg.callout_size.value()}%"
            self.draw_frame = dlg.draw_frame.isChecked()
            self.line_width = dlg.line_width.value()
            self.round_radius = dlg.round.value()
            self.change_wallpaper(force=True)
            self.save_config()

    def about(self):
        QMessageBox.about(self, "Moe Clockについて", f"Moe Clock {VERSION}\\nMIT License\\nChange the image every minute and notify the time.")

    @staticmethod
    def resolve_skin_path(saved_value):
        """Resolve built-in skins across PyInstaller one-file launches.

        New configurations store built-in skins as ``builtin:<folder>``.
        Older configurations may contain a stale _MEIPASS absolute path;
        recover those by their folder name under the current bundled skins.
        External skin folders remain absolute paths.
        """
        value = str(saved_value or "builtin:default")
        root = APP_DIR / "skins"

        if value.startswith("builtin:"):
            skin_name = value.split(":", 1)[1].strip()
            candidate = root / skin_name
            if candidate.is_dir():
                return str(candidate)
            default_skin = root / "default"
            return str(default_skin)

        saved_path = Path(value).expanduser()
        if saved_path.is_dir():
            return str(saved_path)

        # Migration for paths saved by earlier EXE builds, e.g.
        # ...\_MEI12345\skins\moeskin_blue. The _MEIPASS part is
        # temporary, but the skin folder name is stable in the bundled data.
        if saved_path.parent.name.lower() == "skins":
            bundled_candidate = root / saved_path.name
            if bundled_candidate.is_dir():
                return str(bundled_candidate)

        return str(root / "default")

    @staticmethod
    def skin_config_value(skin_path):
        """Store bundled skins by stable name and external skins by path."""
        path = Path(skin_path).expanduser()
        bundled_root = (APP_DIR / "skins").resolve()
        try:
            relative = path.resolve().relative_to(bundled_root)
            if len(relative.parts) == 1:
                return f"builtin:{relative.name}"
        except (OSError, ValueError):
            pass
        return str(path.resolve())

    @staticmethod
    def load_skin_color(skin_dir, fallback="#F366FF"):
        """Read the skin accent color from color_setting.txt.

        The bundled Linux skins store one hexadecimal color per file. That
        color is used for both the date/time text and the program-drawn frame.
        """
        color_file = Path(skin_dir) / "color_setting.txt"
        if not color_file.is_file():
            return fallback
        try:
            content = color_file.read_text(encoding="utf-8-sig")
            match = re.search(r"#[0-9A-Fa-f]{6}", content)
            if match:
                return match.group(0).upper()
        except (OSError, UnicodeError):
            pass
        return fallback

    def available_skins(self):
        """Return bundled skin folders that contain a supported skin asset."""
        root = APP_DIR / "skins"
        found = []
        if root.is_dir():
            for folder in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                if folder.is_dir() and any(
                    (folder / asset).is_file()
                    for asset in ("annotation.svg", "annotation.png", "logo.png", "color_setting.txt")
                ):
                    found.append(str(folder))
        # Keep a user-selected skin available even when it is outside APP_DIR.
        current = Path(self.skin_dir)
        if current.is_dir() and str(current.resolve()) not in {
            str(Path(item).resolve()) for item in found
        }:
            found.append(str(current))
        return found

    def find_wallpapers(self):
        p = Path(self.wallpaper_dir)
        if not p.is_dir():
            return []
        return [str(x) for x in p.rglob("*") if x.is_file() and x.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp")]

    def change_wallpaper(self, force=False):
        files = self.find_wallpapers()
        if not files:
            self.current_wallpaper = None
            self.render()
            return
        candidates = [x for x in files if x not in self.used_wallpapers]
        if not candidates:
            self.used_wallpapers = []
            candidates = files
        self.current_wallpaper = random.choice(candidates)
        self.used_wallpapers.append(self.current_wallpaper)
        self._resize_to_wallpaper()
        self.render()
        self.save_config()

    def set_display_size(self, size):
        """Set the maximum outer window size, then fit the wallpaper inside it."""
        self.display_limit = (max(280, int(size[0])), max(88, int(size[1])))
        self._resize_to_wallpaper()
        self.render()

    def _resize_to_wallpaper(self):
        """Keep the wallpaper's aspect ratio and resize the window height to it.

        The configured display width is retained. The client height is derived
        directly from the source image dimensions; the old display height is
        not used as a crop/letterbox limit.
        """
        if not self.current_wallpaper:
            return
        try:
            with Image.open(self.current_wallpaper) as source:
                iw, ih = source.size
            if iw <= 0 or ih <= 0:
                return

            target_w = max(1, int(self.display_limit[0]))
            target_h = max(1, int(round(target_w * ih / iw)))

            # Reserve space around the image for the outside frame. The
            # wallpaper itself remains target_w x target_h; only the label
            # (and therefore the client area) grows by the frame margins.
            frame_margin = max(1, int(self.line_width)) + 1 if self.draw_frame else 0
            self.view.setFixedSize(
                target_w + frame_margin * 2,
                target_h + frame_margin * 2
            )
            self.adjustSize()
            self.view.updateGeometry()
            self.render()
        except Exception:
            logging.exception("Could not resize window to wallpaper aspect ratio")


    def render(self):
        # Render the wallpaper into its original display area, excluding the
        # transparent margin reserved for the outside frame.
        frame_margin = max(1, int(self.line_width)) + 1 if self.draw_frame else 0
        w = max(1, self.view.width() - frame_margin * 2)
        h = max(1, self.view.height() - frame_margin * 2)
        skin = Path(self.skin_dir)
        try:
            if self.current_wallpaper and Path(self.current_wallpaper).exists():
                bg = Image.open(self.current_wallpaper).convert("RGBA")
            else:
                bg = Image.new("RGBA", (w, h), (35, 25, 45, 255))
            # Preserve the wallpaper aspect ratio even if the client area is
            # temporarily resized to a different ratio (e.g. during startup).
            # The normal window sizing path fits the client area to this image.
            fitted = ImageOps.contain(bg, (w, h), method=Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            canvas.alpha_composite(fitted, ((w - fitted.width) // 2,
                                            (h - fitted.height) // 2))

            # Linux 1.5.1.4 uses annotation.svg as the canonical callout asset.
            # Keep PNG fallback for older/custom skins.
            svg_path = skin / "annotation.svg"
            ann_path = skin / "annotation.png"
            callout_type = self.annotation_type
            basename = Path(self.current_wallpaper).name.upper() if self.current_wallpaper else ""
            if basename.startswith("--UL--"): callout_type = 3
            elif basename.startswith("--LL--"): callout_type = 2
            elif basename.startswith("--UR--"): callout_type = 1
            elif basename.startswith("--LR--"): callout_type = 0
            callout_json = skin / "callout.json"
            if callout_json.exists():
                try:
                    import json
                    callout_type = int(json.loads(callout_json.read_text(encoding="utf-8"))["callout_positon"])
                except Exception:
                    pass
            ann = None
            scale = max(0.25, min(2.0, float(self.callout_size.replace("%", "")) / 100.0))
            if svg_path.exists():
                renderer = QSvgRenderer(str(svg_path))
                if renderer.isValid():
                    natural = renderer.defaultSize()
                    aw = max(1, int(round(natural.width() * scale)))
                    ah = max(1, int(round(natural.height() * scale)))
                    qimg = QImage(aw, ah, QImage.Format_ARGB32)
                    qimg.fill(Qt.transparent)
                    painter = QPainter(qimg)
                    painter.scale(scale, scale)
                    renderer.render(painter)
                    painter.end()
                    # PySide6 returns a memoryview from QImage.bits();
                    # unlike older bindings it has no setsize() method.
                    # Copy exactly the pixel buffer into Pillow.
                    ptr = qimg.bits()
                    pixel_data = memoryview(ptr).cast("B")[:qimg.sizeInBytes()]
                    ann = Image.frombytes("RGBA", (aw, ah), pixel_data.tobytes(), "raw", "BGRA")
            if ann is None and ann_path.exists():
                ann = Image.open(ann_path).convert("RGBA")
                if scale != 1.0:
                    ann = ann.resize((max(1, int(ann.width * scale)), max(1, int(ann.height * scale))), Image.Resampling.LANCZOS)
            if ann is not None:
                # Match Linux 1.5.1.4 Cairo transforms:
                # type 1 = vertical flip, type 2 = horizontal flip, type 3 = both.
                if callout_type in (1, 3):
                    ann = ann.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if callout_type in (2, 3):
                    ann = ann.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                aw, ah = ann.size
                # Draw date/time with Qt rather than Pillow. QFontDialog
                # stores a family name (e.g. "Yu Gothic"), not a font file;
                # QPainter resolves that family through Windows font services.
                aw, ah = ann.size
                rgba = ann.convert("RGBA")
                qimg_text = QImage(
                    rgba.tobytes("raw", "RGBA"), aw, ah, aw * 4,
                    QImage.Format_RGBA8888
                ).copy()
                painter_text = QPainter(qimg_text)
                text_color = QColor(self.color)

                def qt_font(pixel_size):
                    font = QFont(self.font_name)
                    font.setPixelSize(max(1, int(round(pixel_size))))
                    font.setStyleStrategy(QFont.PreferAntialias)
                    return font

                def draw_top(text, x, y, pixel_size):
                    font = qt_font(pixel_size)
                    painter_text.setFont(font)
                    painter_text.setPen(text_color)
                    metrics = QFontMetricsF(font)
                    bounds = metrics.boundingRect(text)
                    painter_text.drawText(
                        QPointF(float(x - bounds.left()),
                                float(y - bounds.top())),
                        text
                    )
                    return metrics.horizontalAdvance(text), bounds.height()

                now = dt.datetime.now()
                year, date, time = now.strftime("%Yねん"), now.strftime("%m/%d"), now.strftime("%H:%M")
                xoff = aw // 2 + 10
                year_y, date_y, time_y, now_y = 38, 57, 81, 108
                if callout_type in (1, 3):
                    year_y, date_y, time_y, now_y = 28, 47, 71, 98
                if callout_type in (2, 3):
                    xoff = 40

                def centered(text, y, pixel_size):
                    font = qt_font(pixel_size)
                    metrics = QFontMetricsF(font)
                    text_width = metrics.horizontalAdvance(text)
                    x = xoff - text_width / 2 + aw - 144
                    draw_top(text, x, y + ah - 144, pixel_size)
                    return x, text_width, metrics.height()

                centered(year, year_y, 16)
                date_x, date_width, date_height = centered(date, date_y, 16)
                weekday = WEEK[now.weekday()]
                weekday_font = qt_font(10)
                weekday_metrics = QFontMetricsF(weekday_font)
                weekday_x = date_x + date_width + self.week_offset
                weekday_y = (date_y + ah - 144
                             + (date_height - weekday_metrics.height()) / 2)
                draw_top(weekday, weekday_x, weekday_y, 10)
                centered(time, time_y, 22)
                centered("になったよ！" if now.minute == 0 else "だよ！", now_y, 15)
                painter_text.end()
                text_bytes = bytes(qimg_text.bits())[:qimg_text.sizeInBytes()]
                ann = Image.frombytes(
                    "RGBA", (aw, ah), text_bytes, "raw", "RGBA"
                )
                if callout_type == 0:
                    xy = (w - aw, canvas.height - ah)
                elif callout_type == 1:
                    xy = (w - aw, 0)
                elif callout_type == 2:
                    xy = (0, canvas.height - ah)
                else:
                    xy = (0, 0)
                canvas.alpha_composite(ann, xy)

            logo_path = skin / "logo.png"
            if logo_path.exists():
                logo = Image.open(logo_path).convert("RGBA")
                if callout_type == 2:
                    xy = (w - logo.width, canvas.height - logo.height)
                else:
                    xy = (0, canvas.height - logo.height)
                canvas.alpha_composite(logo, xy)

            if self.draw_frame:
                # Draw the configurable rounded frame outside the wallpaper.
                stroke_width = max(1, int(self.line_width))
                margin = stroke_width + 1
                radius = max(0, int(self.round_radius)) + margin

                framed = Image.new(
                    "RGBA",
                    (w + margin * 2, h + margin * 2),
                    (0, 0, 0, 0)
                )
                framed.alpha_composite(canvas, (margin, margin))

                d = ImageDraw.Draw(framed)
                d.rounded_rectangle(
                    (0, 0, framed.width - 1, framed.height - 1),
                    radius=radius,
                    outline=self.color,
                    width=stroke_width
                )
                canvas = framed
            else:
                # When the checkbox is off, use the selected skin's frame.png.
                # Stretch it to the exact current wallpaper/window canvas size.
                frame_path = skin / "frame.png"
                if frame_path.is_file():
                    frame = Image.open(frame_path).convert("RGBA")
                    if frame.size != canvas.size:
                        frame = frame.resize(
                            canvas.size, Image.Resampling.LANCZOS
                        )
                    canvas.alpha_composite(frame, (0, 0))

            rgba = canvas.convert("RGBA")
            data = rgba.tobytes("raw", "RGBA")
            image = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888).copy()
            self.view.setPixmap(QPixmap.fromImage(image))
        except Exception as exc:
            self.view.setText(f"Image rendering error:\\n{exc}")

    def tick(self):
        now = dt.datetime.now()
        if self.last_minute != now.minute:
            self.last_minute = now.minute
            self.change_wallpaper()
        if self.isMinimized():
            self.setWindowTitle(now.strftime("Moe Clock - %H:%M:%S"))
        else:
            self.setWindowTitle(APP_NAME)

        # Play once per hour. A short 5-second window tolerates Windows timer
        # scheduling delays, while the hour key prevents duplicate playback.
        hour_key = now.strftime("%Y-%m-%d %H")
        if (self.notice and now.minute == 0 and now.second <= 5
                and self.last_chime_hour != hour_key):
            self.last_chime_hour = hour_key
            self.play_sound()

    def play_sound(self):
        path = Path(self.sound_file)
        if not path.is_file():
            return
        if self.sound_cutout:
            silent = APP_DIR / "sound" / "nosound.wav"
            if silent.is_file():
                self._play_file(silent)
                QTimer.singleShot(350, lambda: self._play_file(path))
                return
        self._play_file(path)

    def _play_file(self, path):
        path = Path(path)
        if not path.is_file():
            return
        self._sound_pending = False
        self._sound.stop()
        self._sound.setSource(QUrl.fromLocalFile(str(path.resolve())))
        if self._sound.status() == QSoundEffect.Status.Ready:
            self._sound.play()
        else:
            # QSoundEffect loads WAV files asynchronously. Calling play()
            # while Loading can be ignored, so start when the source is Ready.
            self._sound_pending = True

    def _on_sound_status_changed(self):
        if not self._sound_pending:
            return
        status = self._sound.status()
        if status == QSoundEffect.Status.Ready:
            self._sound_pending = False
            self._sound.play()
        elif status == QSoundEffect.Status.Error:
            self._sound_pending = False

    def save_config(self):
        self.cfg.set("wallpaper_path", self.wallpaper_dir)
        self.cfg.set("use_wallpaper", repr(self.used_wallpapers))
        self.cfg.set("font", self.font_name)
        self.cfg.set("color", self.color)
        self.cfg.set("notice", self.notice)
        self.cfg.set("alwaysTop", self.always_top)
        self.cfg.set("weekOffset", self.week_offset)
        self.cfg.set("skin", self.skin_config_value(self.skin_dir))
        self.cfg.set("sound", self.sound_file)
        self.cfg.set("windowDecorate", self.decorated)
        self.cfg.set("annotationType", self.annotation_type)
        self.cfg.set("soundCutOut", self.sound_cutout)
        self.cfg.set("calloutSize", self.callout_size)
        self.cfg.set("drawFrame", self.draw_frame)
        self.cfg.set("lineWidth", self.line_width)
        self.cfg.set("round", self.round_radius)
        self.cfg.set("roundWindow", self.round_window)
        self.cfg.set("x_pos", self.x())
        self.cfg.set("y_pos", self.y())
        self.cfg.set("x_size", self.display_limit[0])
        self.cfg.set("y_size", self.display_limit[1])
        self.cfg.save()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render()

    def closeEvent(self, event):
        self.save_config()
        event.accept()


def main():
    # Windows側の日時ロケールを日本語に設定（利用できない環境では既定値を維持）
    try:
        locale.setlocale(locale.LC_TIME, "Japanese_Japan.932")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, "ja_JP.UTF-8")
        except locale.Error:
            pass

    # Qtの表示・書式処理に使用する既定ロケールを日本語（日本）に固定
    QLocale.setDefault(QLocale(QLocale.Language.Japanese, QLocale.Country.Japan))

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = MoeClock()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
