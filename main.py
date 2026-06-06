import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QLineEdit, QSpinBox,
    QColorDialog, QFileDialog, QComboBox, QGroupBox, QGridLayout,
    QTextEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QImage, QColor, QFont as QFont_

from PIL import Image, ImageDraw, ImageFont


class MemeGeneratorTab(QWidget):
    def __init__(self):
        super().__init__()
        self.image_path = None
        self.current_meme = None
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        controls = QVBoxLayout()

        self.load_btn = QPushButton("載入圖片")
        self.load_btn.clicked.connect(self.load_image)
        controls.addWidget(self.load_btn)

        controls.addWidget(QLabel("上方文字:"))
        self.top_text = QLineEdit()
        self.top_text.setPlaceholderText("輸入上方文字")
        controls.addWidget(self.top_text)

        controls.addWidget(QLabel("下方文字:"))
        self.bottom_text = QLineEdit()
        self.bottom_text.setPlaceholderText("輸入下方文字")
        controls.addWidget(self.bottom_text)

        self.generate_btn = QPushButton("生成迷因")
        self.generate_btn.clicked.connect(self.generate_meme)
        controls.addWidget(self.generate_btn)

        self.save_btn = QPushButton("儲存圖片")
        self.save_btn.clicked.connect(self.save_image)
        self.save_btn.setEnabled(False)
        controls.addWidget(self.save_btn)

        controls.addStretch()

        self.preview_label = QLabel("預覽區域\n請載入圖片並輸入文字")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(500, 400)
        self.preview_label.setStyleSheet("border: 1px solid gray; background: #1e1e1e; color: white;")

        layout.addLayout(controls)
        layout.addWidget(self.preview_label, 1)
        self.setLayout(layout)

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇圖片", "", "Images (*.png *.jpg *.jpeg *.gif *.bmp)"
        )
        if path:
            self.image_path = path
            pixmap = QPixmap(path)
            self.preview_label.setPixmap(
                pixmap.scaled(500, 400, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
            self.save_btn.setEnabled(False)

    def generate_meme(self):
        if not self.image_path:
            return
        top = self.top_text.text() or " "
        bottom = self.bottom_text.text() or " "

        img = Image.open(self.image_path).convert("RGBA")
        w, h = img.size

        max_dim = 800
        if w > max_dim or h > max_dim:
            ratio = min(max_dim / w, max_dim / h)
            w, h = int(w * ratio), int(h * ratio)
            img = img.resize((w, h), Image.LANCZOS)

        draw = ImageDraw.Draw(img)
        font_size = max(30, h // 8)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

        self._draw_meme_text(draw, top, font, w, h, "top")
        self._draw_meme_text(draw, bottom, font, w, h, "bottom")

        self.current_meme = img
        qimage = _pil_to_qpixmap(img)
        self.preview_label.setPixmap(
            qimage.scaled(500, 400, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
        )
        self.save_btn.setEnabled(True)

    def _draw_meme_text(self, draw, text, font, w, h, position):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        x = (w - tw) // 2
        y = 10 if position == "top" else h - th - 10

        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill="black")

        draw.text((x, y), text, font=font, fill="white")

    def save_image(self):
        if self.current_meme:
            path, _ = QFileDialog.getSaveFileName(
                self, "儲存圖片", "", "PNG (*.png);;JPEG (*.jpg)"
            )
            if path:
                self.current_meme.save(path)


class TextImageTab(QWidget):
    def __init__(self):
        super().__init__()
        self.current_img = None
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        controls = QVBoxLayout()

        g1 = QGroupBox("背景設定")
        g1_layout = QGridLayout()

        self.bg_color_btn = QPushButton("選擇背景色")
        self.bg_color_btn.clicked.connect(self.choose_bg_color)
        self.bg_color = QColor(30, 30, 30)
        self.bg_preview = QLabel()
        self.bg_preview.setFixedSize(40, 30)
        self.bg_preview.setStyleSheet(
            f"background-color: {self.bg_color.name()}; border: 1px solid gray;"
        )
        g1_layout.addWidget(self.bg_color_btn, 0, 0)
        g1_layout.addWidget(self.bg_preview, 0, 1)

        g1_layout.addWidget(QLabel("寬度:"), 1, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, 2000)
        self.width_spin.setValue(800)
        g1_layout.addWidget(self.width_spin, 1, 1)

        g1_layout.addWidget(QLabel("高度:"), 2, 0)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(100, 2000)
        self.height_spin.setValue(600)
        g1_layout.addWidget(self.height_spin, 2, 1)

        g1.setLayout(g1_layout)
        controls.addWidget(g1)

        g2 = QGroupBox("文字設定")
        g2_layout = QGridLayout()

        g2_layout.addWidget(QLabel("文字內容:"), 0, 0, 1, 2)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText("Hello\nWorld!")
        self.text_edit.setMaximumHeight(100)
        g2_layout.addWidget(self.text_edit, 1, 0, 1, 2)

        self.text_color_btn = QPushButton("文字顏色")
        self.text_color_btn.clicked.connect(self.choose_text_color)
        self.text_color = QColor(255, 255, 255)
        g2_layout.addWidget(self.text_color_btn, 2, 0)

        g2_layout.addWidget(QLabel("字體大小:"), 3, 0)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 200)
        self.font_size_spin.setValue(48)
        g2_layout.addWidget(self.font_size_spin, 3, 1)

        g2_layout.addWidget(QLabel("對齊方式:"), 4, 0)
        self.align_combo = QComboBox()
        self.align_combo.addItems(["置中", "靠左", "靠右"])
        g2_layout.addWidget(self.align_combo, 4, 1)

        g2.setLayout(g2_layout)
        controls.addWidget(g2)

        self.generate_btn = QPushButton("生成圖片")
        self.generate_btn.clicked.connect(self.generate_text_image)
        controls.addWidget(self.generate_btn)

        self.save_btn = QPushButton("儲存圖片")
        self.save_btn.clicked.connect(self.save_image)
        self.save_btn.setEnabled(False)
        controls.addWidget(self.save_btn)

        controls.addStretch()

        self.preview_label = QLabel("預覽區域")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(500, 400)
        self.preview_label.setStyleSheet("border: 1px solid gray; background: #1e1e1e; color: white;")

        layout.addLayout(controls)
        layout.addWidget(self.preview_label, 1)
        self.setLayout(layout)

    def choose_bg_color(self):
        color = QColorDialog.getColor(self.bg_color, self)
        if color.isValid():
            self.bg_color = color
            self.bg_preview.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid gray;"
            )

    def choose_text_color(self):
        color = QColorDialog.getColor(self.text_color, self)
        if color.isValid():
            self.text_color = color

    def generate_text_image(self):
        w = self.width_spin.value()
        h = self.height_spin.value()
        text = self.text_edit.toPlainText()
        font_size = self.font_size_spin.value()

        img = Image.new(
            "RGBA",
            (w, h),
            (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue(), 255),
        )
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

        lines = text.split("\n")
        line_height = font_size + 10
        total_height = len(lines) * line_height
        start_y = (h - total_height) // 2

        align = self.align_combo.currentText()
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]

            if align == "置中":
                x = (w - tw) // 2
            elif align == "靠左":
                x = 20
            else:
                x = w - tw - 20

            y = start_y + i * line_height
            draw.text(
                (x, y), line, font=font,
                fill=(self.text_color.red(), self.text_color.green(),
                      self.text_color.blue(), 255)
            )

        self.current_img = img
        qimage = _pil_to_qpixmap(img)
        self.preview_label.setPixmap(
            qimage.scaled(500, 400, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
        )
        self.save_btn.setEnabled(True)

    def save_image(self):
        if self.current_img:
            path, _ = QFileDialog.getSaveFileName(
                self, "儲存圖片", "", "PNG (*.png);;JPEG (*.jpg)"
            )
            if path:
                self.current_img.save(path)


class AnimationTab(QWidget):
    def __init__(self):
        super().__init__()
        self.frames = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)
        self.current_frame_idx = 0
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        controls = QVBoxLayout()

        g1 = QGroupBox("動畫設定")
        g1_layout = QGridLayout()

        g1_layout.addWidget(QLabel("動畫類型:"), 0, 0)
        self.anim_type = QComboBox()
        self.anim_type.addItems(["文字跑馬燈", "文字淡入淡出", "文字彈跳", "顏色漸變", "旋轉文字"])
        g1_layout.addWidget(self.anim_type, 0, 1)

        g1_layout.addWidget(QLabel("動畫文字:"), 1, 0, 1, 2)
        self.anim_text = QLineEdit("動畫文字!")
        g1_layout.addWidget(self.anim_text, 2, 0, 1, 2)

        g1_layout.addWidget(QLabel("幀數:"), 3, 0)
        self.frame_count = QSpinBox()
        self.frame_count.setRange(5, 60)
        self.frame_count.setValue(20)
        g1_layout.addWidget(self.frame_count, 3, 1)

        g1_layout.addWidget(QLabel("FPS:"), 4, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 30)
        self.fps_spin.setValue(10)
        g1_layout.addWidget(self.fps_spin, 4, 1)

        g1.setLayout(g1_layout)
        controls.addWidget(g1)

        g2 = QGroupBox("外觀設定")
        g2_layout = QGridLayout()

        self.fg_color_btn = QPushButton("前景色")
        self.fg_color_btn.clicked.connect(self.choose_fg)
        self.fg_color = QColor(255, 255, 255)
        g2_layout.addWidget(self.fg_color_btn, 0, 0)

        self.bg_color_btn = QPushButton("背景色")
        self.bg_color_btn.clicked.connect(self.choose_bg)
        self.bg_color = QColor(0, 0, 0)
        g2_layout.addWidget(self.bg_color_btn, 0, 1)

        g2_layout.addWidget(QLabel("圖片寬度:"), 1, 0)
        self.anim_w = QSpinBox()
        self.anim_w.setRange(100, 1000)
        self.anim_w.setValue(400)
        g2_layout.addWidget(self.anim_w, 1, 1)

        g2_layout.addWidget(QLabel("圖片高度:"), 2, 0)
        self.anim_h = QSpinBox()
        self.anim_h.setRange(100, 1000)
        self.anim_h.setValue(200)
        g2_layout.addWidget(self.anim_h, 2, 1)

        g2.setLayout(g2_layout)
        controls.addWidget(g2)

        self.generate_btn = QPushButton("生成動畫")
        self.generate_btn.clicked.connect(self.generate_animation)
        controls.addWidget(self.generate_btn)

        self.preview_btn = QPushButton("▶ 預覽動畫")
        self.preview_btn.clicked.connect(self.toggle_preview)
        self.preview_btn.setEnabled(False)
        controls.addWidget(self.preview_btn)

        self.save_btn = QPushButton("儲存為 GIF")
        self.save_btn.clicked.connect(self.save_gif)
        self.save_btn.setEnabled(False)
        controls.addWidget(self.save_btn)

        controls.addStretch()

        self.preview_label = QLabel("預覽區域")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(500, 400)
        self.preview_label.setStyleSheet("border: 1px solid gray; background: #1e1e1e; color: white;")

        layout.addLayout(controls)
        layout.addWidget(self.preview_label, 1)
        self.setLayout(layout)

    def choose_fg(self):
        c = QColorDialog.getColor(self.fg_color, self)
        if c.isValid():
            self.fg_color = c

    def choose_bg(self):
        c = QColorDialog.getColor(self.bg_color, self)
        if c.isValid():
            self.bg_color = c

    def generate_animation(self):
        self.frames = []
        text = self.anim_text.text()
        n = self.frame_count.value()
        w = self.anim_w.value()
        h = self.anim_h.value()
        anim_type = self.anim_type.currentText()
        bg = (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue(), 255)
        fg = (self.fg_color.red(), self.fg_color.green(), self.fg_color.blue(), 255)

        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        except (IOError, OSError):
            font = ImageFont.load_default()

        if anim_type == "文字跑馬燈":
            self.frames = self._marquee(text, w, h, font, bg, fg, n)
        elif anim_type == "文字淡入淡出":
            self.frames = self._fade(text, w, h, font, bg, fg, n)
        elif anim_type == "文字彈跳":
            self.frames = self._bounce(text, w, h, font, bg, fg, n)
        elif anim_type == "顏色漸變":
            self.frames = self._color_shift(text, w, h, font, bg, fg, n)
        elif anim_type == "旋轉文字":
            self.frames = self._rotate_text(text, w, h, font, bg, fg, n)

        if self.frames:
            self.current_frame_idx = 0
            self.show_frame(0)
            self.preview_btn.setEnabled(True)
            self.save_btn.setEnabled(True)

    def _marquee(self, text, w, h, font, bg, fg, n):
        frames = []
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        for i in range(n):
            img = Image.new("RGBA", (w, h), bg)
            draw = ImageDraw.Draw(img)
            x = w - int((w + tw) * i / n)
            y = (h - bbox[3] + bbox[1]) // 2
            draw.text((x, y), text, font=font, fill=fg)
            frames.append(img)
        return frames

    def _fade(self, text, w, h, font, bg, fg, n):
        frames = []
        bbox = font.getbbox(text)
        x = (w - (bbox[2] - bbox[0])) // 2
        y = (h - bbox[3] + bbox[1]) // 2
        half = n // 2
        for i in range(n):
            img = Image.new("RGBA", (w, h), bg)
            draw = ImageDraw.Draw(img)
            if i < half:
                alpha = int(255 * i / half) if half > 0 else 255
            else:
                alpha = int(255 * (n - 1 - i) / (n - half - 1)) if n - half - 1 > 0 else 0
            fill = (fg[0], fg[1], fg[2], alpha)
            draw.text((x, y), text, font=font, fill=fill)
            frames.append(img)
        return frames

    def _bounce(self, text, w, h, font, bg, fg, n):
        frames = []
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (w - tw) // 2
        for i in range(n):
            img = Image.new("RGBA", (w, h), bg)
            draw = ImageDraw.Draw(img)
            progress = i / (n - 1) if n > 1 else 0
            y = int(abs(h - th) * (1 - abs(2 * progress - 1)))
            draw.text((x, y), text, font=font, fill=fg)
            frames.append(img)
        return frames

    def _color_shift(self, text, w, h, font, bg, fg, n):
        frames = []
        bbox = font.getbbox(text)
        x = (w - (bbox[2] - bbox[0])) // 2
        y = (h - bbox[3] + bbox[1]) // 2
        for i in range(n):
            img = Image.new("RGBA", (w, h), bg)
            draw = ImageDraw.Draw(img)
            r = min(255, int(255 * i / n))
            g = min(255, int(255 * (n - i) / n))
            b = min(255, int(128 * abs(n / 2 - i) / (n / 2)))
            fill = (r, g, b, 255)
            draw.text((x, y), text, font=font, fill=fill)
            frames.append(img)
        return frames

    def _rotate_text(self, text, w, h, font, bg, fg, n):
        frames = []
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        for i in range(n):
            txt_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(txt_img)
            draw.text(((w - tw) // 2, (h - th) // 2), text, font=font, fill=fg)
            angle = 360 * i / n
            rotated = txt_img.rotate(angle, expand=False, center=(w // 2, h // 2))
            img = Image.new("RGBA", (w, h), bg)
            img = Image.alpha_composite(img, rotated)
            frames.append(img)
        return frames

    def show_frame(self, idx):
        if 0 <= idx < len(self.frames):
            img = self.frames[idx]
            qimage = QImage(img.tobytes(), img.width, img.height,
                            QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            self.preview_label.setPixmap(
                pixmap.scaled(500, 400, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )

    def toggle_preview(self):
        if self.timer.isActive():
            self.timer.stop()
            self.preview_btn.setText("▶ 預覽動畫")
        else:
            self.current_frame_idx = 0
            self.timer.start(1000 // self.fps_spin.value())
            self.preview_btn.setText("⏸ 暫停")

    def next_frame(self):
        if not self.frames:
            return
        self.current_frame_idx = (self.current_frame_idx + 1) % len(self.frames)
        self.show_frame(self.current_frame_idx)

    def save_gif(self):
        if not self.frames:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "儲存動畫", "", "GIF (*.gif)"
        )
        if path:
            frames_rgb = [f.convert("RGBA") for f in self.frames]
            frames_rgb[0].save(
                path,
                save_all=True,
                append_images=frames_rgb[1:],
                duration=1000 // self.fps_spin.value(),
                loop=0,
                disposal=2,
            )


def _pil_to_qpixmap(img):
    if img.mode == "RGBA":
        qimage = QImage(img.tobytes(), img.width, img.height,
                        QImage.Format.Format_RGBA8888)
    else:
        img = img.convert("RGB")
        qimage = QImage(img.tobytes(), img.width, img.height,
                        QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("圖片動畫生成器")
        self.setMinimumSize(900, 600)

        tabs = QTabWidget()
        tabs.addTab(MemeGeneratorTab(), "迷因生成器")
        tabs.addTab(TextImageTab(), "文字圖片")
        tabs.addTab(AnimationTab(), "動畫生成")

        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
