"""Raster sketch workspace. Images stay portable inside normal BeastNotes backups."""
import os
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QTimer, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QSpinBox, QColorDialog, QFileDialog, QMessageBox, QScrollArea, QLabel)


def png_bytes(image):
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise OSError('Could not encode drawing')
    return bytes(buffer.data())


def save_png(image, path):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    try:
        with open(temporary, 'wb') as handle:
            handle.write(png_bytes(image))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Canvas(QWidget):
    changed = Signal()
    colorPicked = Signal(QColor)

    def __init__(self):
        super().__init__()
        self.image = QImage(1280, 800, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.GlobalColor.white)
        self.tool = 'Pen'
        self.color = QColor('#47358c')
        self.stroke_width = 6
        self.scale = 1.0
        self.undo_stack, self.redo_stack = [], []
        self.origin = self.last = None
        self.preview = None
        self.dirty = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.sync_size()

    def sync_size(self):
        self.setFixedSize(round(self.image.width() * self.scale), round(self.image.height() * self.scale))
        self.update()

    def checkpoint(self):
        # Bound history by bytes as well as count (large imported images cost more).
        self.undo_stack.append(self.image.copy())
        budget = max(1, min(30, (96 * 1024**2) // max(1, self.image.sizeInBytes())))
        del self.undo_stack[:-budget]
        self.redo_stack.clear()

    def notify(self):
        self.dirty = True
        self.update()
        self.changed.emit()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.image)
            self.image = self.undo_stack.pop()
            self.sync_size()
            self.notify()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.image)
            self.image = self.redo_stack.pop()
            self.sync_size()
            self.notify()

    def point(self, event):
        p = event.position() / self.scale
        return QPointF(max(0, min(self.image.width()-1, p.x())), max(0, min(self.image.height()-1, p.y())))

    def draw_segment(self, start, end):
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor('white') if self.tool == 'Eraser' else self.color
        painter.setPen(QPen(color, self.stroke_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if start == end:
            painter.drawPoint(start)
        else:
            painter.drawLine(start, end)
        painter.end()

    def draw_shape(self, target, end):
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.color, self.stroke_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        rect = QRectF(self.origin, end).normalized()
        if self.tool == 'Line':
            painter.drawLine(self.origin, end)
        elif self.tool == 'Rectangle':
            painter.drawRect(rect)
        else:
            painter.drawEllipse(rect)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self.point(event)
        if self.tool == 'Eyedropper':
            self.color = self.image.pixelColor(int(point.x()), int(point.y()))
            self.colorPicked.emit(self.color)
            return
        self.checkpoint()
        self.origin = self.last = point
        if self.tool in ('Pen', 'Eraser'):
            self.draw_segment(point, point)
            self.update()

    def mouseMoveEvent(self, event):
        if self.origin is None:
            return
        point = self.point(event)
        if self.tool in ('Pen', 'Eraser'):
            self.draw_segment(self.last, point)
            self.last = point
        else:
            self.preview = self.image.copy()
            self.draw_shape(self.preview, point)
        self.update()

    def mouseReleaseEvent(self, event):
        if self.origin is None or event.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool in ('Pen', 'Eraser'):
            self.draw_segment(self.last, self.point(event))
        else:
            self.draw_shape(self.image, self.point(event))
        self.origin = self.last = self.preview = None
        self.notify()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.scale(self.scale, self.scale)
        painter.drawImage(0, 0, self.preview if self.preview is not None else self.image)
        painter.end()


class PaintDialog(QDialog):
    def __init__(self, parent, draft_path, initial=None):
        super().__init__(parent)
        self.setWindowTitle('Paint · BeastNotes V4')
        self.setStyleSheet('QDialog {background:#15161f;color:#e7e7f0;} QLabel {color:#b9b5cc;} QPushButton {background:#252435;color:#eeeaff;} QComboBox,QSpinBox {background:#252435;color:#eeeaff;}')
        self.resize(1150, 820)
        self.setMinimumSize(760, 540)
        self.draft_path = Path(draft_path)
        self.canvas = Canvas()
        self.inserted_image = None
        layout = QVBoxLayout(self)
        heading = QLabel('Make room for a visual thought.')
        heading.setStyleSheet('font-size:24px; font-weight:700; padding:8px;')
        layout.addWidget(heading)
        tools = QHBoxLayout()
        self.tools = QComboBox()
        self.tools.addItems(['Pen', 'Eraser', 'Line', 'Rectangle', 'Ellipse', 'Eyedropper'])
        self.tools.currentTextChanged.connect(lambda value: setattr(self.canvas, 'tool', value))
        tools.addWidget(self.tools)
        self.color_button = QPushButton('Ink')
        self.color_button.clicked.connect(self.choose_color)
        tools.addWidget(self.color_button)
        self.update_color(self.canvas.color)
        self.canvas.colorPicked.connect(self.update_color)
        tools.addWidget(QLabel('Size'))
        width = QSpinBox()
        width.setRange(1, 80)
        width.setValue(6)
        width.valueChanged.connect(lambda value: setattr(self.canvas, 'stroke_width', value))
        tools.addWidget(width)
        for title, callback in [('Undo', self.canvas.undo), ('Redo', self.canvas.redo),
                                ('Clear', self.clear), ('Open image', self.open_image)]:
            b = QPushButton(title)
            b.clicked.connect(callback)
            tools.addWidget(b)
        self.zoom = QComboBox()
        self.zoom.addItems(['25%', '50%', '75%', '100%', '150%', '200%'])
        self.zoom.setCurrentText('75%')
        self.zoom.currentTextChanged.connect(self.change_zoom)
        tools.addWidget(self.zoom)
        layout.addLayout(tools)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setStyleSheet('QScrollArea {background:#242635; border:1px solid #41435b;}')
        layout.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        self.status = QLabel('1280 × 800 · white canvas · local draft recovery')
        bottom.addWidget(self.status, 1)
        for title, callback in [('Export PNG', self.export), ('Keep draft & close', self.reject),
                                ('Insert into note', self.insert)]:
            b = QPushButton(title)
            b.clicked.connect(callback)
            bottom.addWidget(b)
        layout.addLayout(bottom)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.persist)
        self.canvas.changed.connect(lambda: self.timer.start())
        for keys, fn in [('Ctrl+Z', self.canvas.undo), ('Ctrl+Shift+Z', self.canvas.redo), ('Ctrl+Y', self.canvas.redo)]:
            QShortcut(QKeySequence(keys), self, activated=fn)
        if initial is not None and not initial.isNull():
            self.canvas.image = initial.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        elif self.draft_path.exists():
            restored = QImage(str(self.draft_path))
            if not restored.isNull():
                self.canvas.image = restored.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                self.status.setText('Recovered your unfinished drawing')
        self.change_zoom(self.zoom.currentText())

    def change_zoom(self, value):
        self.canvas.scale = int(value.rstrip('%')) / 100
        self.canvas.sync_size()

    def update_color(self, color):
        self.canvas.color = color
        self.color_button.setStyleSheet(f'background:{color.name()};color:{"black" if color.lightness()>140 else "white"};')
        self.color_button.setText(color.name())

    def choose_color(self):
        color = QColorDialog.getColor(self.canvas.color, self, 'Choose ink')
        if color.isValid():
            self.update_color(color)

    def clear(self):
        if QMessageBox.question(self, 'Clear canvas', 'Clear this drawing? You can undo this.') == QMessageBox.StandardButton.Yes:
            self.canvas.checkpoint()
            self.canvas.image.fill(Qt.GlobalColor.white)
            self.canvas.notify()

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open image', '', 'Images (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not path:
            return
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.width() * size.height() > 8_000_000:
            QMessageBox.warning(self, 'Image too large', 'Choose an image with at most 8 million pixels.')
            return
        image = reader.read()
        if image.isNull():
            QMessageBox.warning(self, 'Could not open image', reader.errorString())
            return
        self.canvas.checkpoint()
        # Flatten transparency onto white so the eraser has consistent behaviour.
        flat = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
        flat.fill(Qt.GlobalColor.white)
        painter = QPainter(flat)
        painter.drawImage(0, 0, image)
        painter.end()
        self.canvas.image = flat
        self.canvas.sync_size()
        self.canvas.notify()

    def persist(self):
        if not self.canvas.dirty:
            return True
        try:
            save_png(self.canvas.image, self.draft_path)
            self.status.setText(f'{self.canvas.image.width()} × {self.canvas.image.height()} · Draft saved locally')
            self.canvas.dirty = False
            return True
        except OSError as exc:
            self.status.setText('Draft save failed: ' + str(exc))
            return False

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export drawing', 'Drawing.png', 'PNG (*.png)')
        if path:
            try:
                save_png(self.canvas.image, path)
                self.status.setText('PNG exported')
            except OSError as exc:
                QMessageBox.warning(self, 'Export failed', str(exc))

    def insert(self):
        self.timer.stop()
        if not self.persist():
            return
        self.inserted_image = self.canvas.image.copy()
        self.accept()

    def reject(self):
        self.timer.stop()
        if self.persist():
            super().reject()
