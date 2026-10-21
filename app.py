import sys
import os
import re
import json
import math
import time
import uuid
import copy
import random
import shutil
import zipfile
import tempfile
import traceback
import base64
from pathlib import Path
from datetime import datetime
from urllib.parse import unquote

from paint import PaintDialog
from studio import StudioMixin, record_revisions

from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QPointF, QUrl, QLockFile,
    QVariantAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QColor, QBrush, QPen, QPainter, QPainterPath, QFont,
    QImage, QImageReader, QPixmap, QIcon, QPalette, QDesktopServices,
    QTextDocument, QTextCursor, QTextCharFormat, QTextBlockFormat,
    QTextImageFormat, QTextListFormat, QShortcut, QKeySequence
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QPlainTextEdit,
    QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QListWidget, QListWidgetItem, QSplitter, QStackedWidget,
    QMenu, QDialog, QDialogButtonBox, QInputDialog, QFileDialog,
    QMessageBox, QComboBox, QProgressBar, QCheckBox,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsPathItem, QGraphicsTextItem, QGraphicsItem,
    QAbstractItemView, QButtonGroup, QFrame
)

APP = 'BeastNotes V4'
BASE = Path(__file__).resolve().parent
INSTALL_ROOT = BASE.parent.parent if BASE.parent.name == 'releases' else BASE
DATA = Path(os.environ.get('BEASTNOTES_DATA', str(INSTALL_ROOT / 'Data'))).expanduser().resolve()
ROLE = Qt.ItemDataRole.UserRole
COLORS = {
    'root': '#e4ddff',
    'book': '#ac92ff',
    'chapter': '#73b6ff',
    'note': '#ed9bc7'
}
MEDIA_RE = re.compile(r'beastimage:([^"\'<>\s]+)', re.I)
LINK_RE = re.compile(
    r'href\s*=\s*["\'](?:beastnote|beastnotes|note):/*([^"\'\s?#]+)',
    re.I
)

STYLE = """
* { font-family: "Segoe UI"; font-size: 13px; }
QMainWindow, QDialog { background: #101117; color: #e7e7f0; }
QWidget { color: #e7e7f0; }
QWidget#Header { background: #15161f; border-bottom: 1px solid #292b3b; }
QWidget#Side, QWidget#Details { background: #15161f; }
QLabel#Brand { font-size: 23px; font-weight: 700; color: #eeeaff; }
QLabel#Badge { color: #b8a4ff; font-size: 11px; font-weight: 700; }
QLabel#Muted { color: #9398ae; }
QLabel#Section { color: #9398ae; font-size: 11px; font-weight: 700; }
QLabel#Metric { font-size: 29px; font-weight: 700; color: #e8e0ff; }
QLabel#Big { font-size: 26px; font-weight: 700; }
QLabel#Saved { color: #81d9ba; font-size: 12px; }
QLineEdit, QComboBox, QPlainTextEdit {
    background: #1b1d29;
    border: 1px solid #303346;
    border-radius: 8px;
    padding: 9px;
    selection-background-color: #60458e;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: #a58ae8;
}
QLineEdit#Title {
    background: transparent; border: none;
    padding: 8px 0px; font-size: 29px; font-weight: 700;
}
QTextEdit#Editor {
    background: #101117; border: none; padding: 15px 20px;
    selection-background-color: #60458e; color: #e4e4ee;
}
QTextEdit#Prompt {
    background: #191b26; border: 1px solid #303346;
    border-radius: 12px; padding: 20px;
}
QPushButton {
    background: #232536; border: 1px solid #35384d;
    border-radius: 8px; padding: 8px 12px; min-height: 19px;
}
QPushButton:hover { background: #30334a; border-color: #78649f; }
QPushButton:pressed { background: #3a3154; }
QPushButton:checked {
    background: #3a2f55; border-color: #977bcf; color: #e9dcff;
}
QPushButton:disabled { color: #666b80; border-color: #292b39; }
QPushButton#Accent {
    background: #8061bf; border-color: #a78bd9; color: white;
}
QPushButton#Accent:hover { background: #9472d4; }
QPushButton#Quiet { background: transparent; border-color: transparent; }
QPushButton#Danger:hover { background: #4b283d; border-color: #be7296; }
QTreeWidget, QListWidget {
    background: transparent; border: none; outline: none;
    selection-background-color: #352d4d;
}
QTreeWidget::item, QListWidget::item {
    padding: 8px 5px; border-radius: 6px; margin: 1px 0px;
}
QTreeWidget::item:hover, QListWidget::item:hover { background: #222536; }
QTreeWidget::item:selected, QListWidget::item:selected {
    background: #39304f; color: #f4edff;
}
QMenu {
    background: #202230; border: 1px solid #45415a; padding: 6px;
}
QMenu::item { padding: 8px 22px; border-radius: 5px; }
QMenu::item:selected { background: #46365f; }
QMenu::separator { height: 1px; background: #36384b; margin: 5px; }
QToolTip {
    background: #282b3d; color: #f1edff;
    border: 1px solid #78649f; padding: 6px;
}
QSplitter::handle { background: #272938; width: 2px; }
QSplitter::handle:hover { background: #977bcf; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 0px; }
QScrollBar::handle:vertical {
    background: #41445c; border-radius: 4px; min-height: 28px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal { height: 9px; background: transparent; }
QScrollBar::handle:horizontal { background: #41445c; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QProgressBar {
    background: #242638; border: none; border-radius: 5px; height: 8px;
}
QProgressBar::chunk { background: #aa8ce8; border-radius: 5px; }
QFrame#Card {
    background: #191b26; border: 1px solid #303346; border-radius: 12px;
}
QStatusBar { background: #15161f; color: #9398ae; font-size: 11px; }
QCheckBox { spacing: 8px; }
"""

def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')

def token():
    return uuid.uuid4().hex

def file_stamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S-%f')

def plain(markup):
    doc = QTextDocument()
    doc.setHtml(markup or '')
    return doc.toPlainText().replace('\ufffc', '')

def walk(nodes, trail=()):
    for node in nodes:
        path = trail + (node['title'],)
        yield node, path
        yield from walk(node.get('children', []), path)

def all_stored_nodes(data):
    yield from (n for n, _ in walk(data['roots']))
    for record in data['trash']:
        yield from (n for n, _ in walk([record['node']]))

def links(markup):
    return {unquote(x) for x in LINK_RE.findall(markup or '')}

def image_names(markup):
    return {
        Path(unquote(x).lstrip('/')).name
        for x in MEDIA_RE.findall(markup or '')
    }

def new_node(kind='note', title='Untitled', markup=''):
    return {
        'id': token(), 'kind': kind, 'title': title,
        'html': markup, 'text': plain(markup),
        'children': [], 'tags': [], 'favorite': False,
        'created': now(), 'updated': now()
    }

def default_data():
    ideas = new_node('note', 'Ideas', '<h1>Give an idea somewhere to land.</h1><p></p>')
    welcome = new_node('note', 'Welcome to V4', (
        '<h1>A little more room for your brain.</h1>'
        '<p>This is your separate V4 workspace. Use <b>Import</b> '
        'above to copy your previous notebooks.</p>'
        '<h2>New in V4</h2>'
        '<p><b>Paint</b> a sketch, diagram or annotation and insert it into your note. '
        'Drawings have undo, shapes, zoom, PNG export and draft recovery.</p>'
        '<p>Press <b>Ctrl+K</b> to jump to a page or command; <b>Ctrl+H</b> to find and replace. '
        'Use <b>Studio</b> for page history, display settings and duplicate page. '
        '<b>Alt+Left / Right</b> moves through visited pages.</p>'
        '<h2>Make yourself at home</h2>'
        '<p>Drag pages into any branch. Books, chapters and notes can all '
        'have their own content and children.</p>'
        '<p>☐ Paste a screenshot or drop an image here</p>'
        '<p>☐ Add a link with the Link button</p>'
        '<p>☐ Open the graph and rearrange your constellation</p>'
        '<p>Click a checkbox character to tick it. Right-click an image '
        'to resize it.</p>'
        '<h2>A connected workspace</h2>'
        '<p>The panel on the right shows headings and pages that link here. '
        'Use tags and favourites to find your way back.</p>'
        '<p>Try your <a href="beastnote:' + ideas['id'] + '">Ideas page</a>.</p>'
        '<h2>Keep a complete copy</h2>'
        '<p>Backups include your active pages, bin, images, graph positions '
        'and typing scores. Choose an external folder from More when you want '
        'a copy somewhere else.</p>'
    ))
    chapter = new_node('chapter', 'Start here', '<p>Your first chapter.</p>')
    chapter['children'] = [welcome, ideas]
    book = new_node('book', 'Your second brain', '<p>A collection you can make your own.</p>')
    book['children'] = [chapter]
    return {
        'schema': 3, 'roots': [book], 'trash': [], 'layout': {},
        'prefs': {'last': welcome['id']}, 'scores': []
    }

def validate(data):
    if not isinstance(data, dict) or data.get('schema') != 3:
        raise ValueError('This is not a BeastNotes V4 data file.')
    for key, typ in (
        ('roots', list), ('trash', list), ('layout', dict),
        ('prefs', dict), ('scores', list)
    ):
        if not isinstance(data.get(key), typ):
            raise ValueError('Invalid data section: ' + key)
    seen = set()
    def check(nodes, used):
        for n in nodes:
            if not isinstance(n, dict):
                raise ValueError('A page is not a valid object.')
            if not isinstance(n.get('id'), str) or not n['id']:
                raise ValueError('A page is missing its ID.')
            if n['id'] in used or n['id'] == '__root__':
                raise ValueError('Duplicate or reserved page ID: ' + n['id'])
            used.add(n['id'])
            if n.get('kind') not in ('book', 'chapter', 'note'):
                raise ValueError('Unknown page type.')
            for key in ('title', 'html', 'text'):
                if not isinstance(n.get(key), str):
                    raise ValueError('Invalid page field: ' + key)
            if not isinstance(n.get('children'), list):
                raise ValueError('Invalid children list.')
            if not isinstance(n.get('tags'), list):
                raise ValueError('Invalid tag list.')
            if not all(isinstance(t, str) for t in n['tags']):
                raise ValueError('Invalid tag.')
            check(n['children'], used)
    check(data['roots'], seen)
    for record in data['trash']:
        if not isinstance(record, dict) or not isinstance(record.get('node'), dict):
            raise ValueError('Invalid bin entry.')
        check([record['node']], set() if record.get('restored') else seen)
    for score in data['scores']:
        if not isinstance(score, dict):
            raise ValueError('Invalid typing score.')
        if not isinstance(score.get('wpm'), (int, float)):
            raise ValueError('Invalid typing speed.')
        if not isinstance(score.get('accuracy'), (int, float)):
            raise ValueError('Invalid typing accuracy.')

def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + token() + '.tmp')
    try:
        with open(temp, 'xb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()

class Vault:
    def __init__(self, root, load=True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.images = self.root / 'images'
        self.images.mkdir(exist_ok=True)
        self.path = self.root / 'vault.json'
        self.saved = ''
        self._revision_times = {}
        if load and self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8-sig'))
            validate(self.data)
            self.saved = self.serialized()
        else:
            self.data = default_data()
            if load:
                self.save()

    def serialized(self):
        return json.dumps(self.data, ensure_ascii=False, indent=2)

    def get(self, ident):
        return next((n for n, _ in walk(self.data['roots']) if n['id'] == ident), None)

    def location(self, ident):
        def find(nodes, parent=None):
            for i, n in enumerate(nodes):
                if n['id'] == ident:
                    return nodes, i, parent
                result = find(n['children'], n['id'])
                if result:
                    return result
            return None
        return find(self.data['roots'])

    def save(self):
        validate(self.data)
        encoded = self.serialized()
        if encoded == self.saved:
            return False
        record_revisions(self, encoded)
        atomic_write(self.path, encoded.encode('utf-8'))
        self.saved = encoded
        return True

    def change(self, fn):
        before = copy.deepcopy(self.data)
        try:
            result = fn()
            self.save()
            return result
        except Exception:
            self.data = before
            raise

    def bin_page(self, ident):
        def action():
            loc = self.location(ident)
            if not loc:
                raise ValueError('That page no longer exists.')
            siblings, index, parent = loc
            record = {
                'node': copy.deepcopy(siblings[index]),
                'parent': parent, 'index': index,
                'at': now(), 'restored': False
            }
            self.data['trash'].append(record)
            siblings.pop(index)
        self.change(action)

    def restore_page(self, index):
        def action():
            record = self.data['trash'][index]
            if record.get('restored'):
                raise ValueError('This entry has already been restored.')
            node = copy.deepcopy(record['node'])
            parent = self.get(record.get('parent'))
            target = parent['children'] if parent else self.data['roots']
            position = max(0, min(int(record.get('index', len(target))), len(target)))
            target.insert(position, node)
            record['restored'] = True
            record['restored_at'] = now()
            return node['id']
        return self.change(action)

    def backup_dir(self):
        chosen = self.data['prefs'].get('backup_dir')
        return Path(chosen) if chosen else self.root / 'backups'

def write_bundle(data, images_dir, destination):
    validate(data)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.' + token() + '.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('vault.json', json.dumps(data, ensure_ascii=False))
            archive.writestr('manifest.json', json.dumps({
                'app': APP, 'schema': 3, 'created': now()
            }))
            for path in Path(images_dir).iterdir():
                if path.is_file() and re.fullmatch(
                    r'[A-Za-z0-9_.-]+\.(png|jpg|jpeg|webp|bmp|gif)', path.name, re.I
                ):
                    archive.write(path, 'images/' + path.name)
        with open(temporary, 'rb+') as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()

def read_bundle(path):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [e.filename for e in entries]
        if len(entries) > 50000 or len(names) != len(set(names)):
            raise ValueError('This backup has duplicate entries or too many files.')
        if sum(e.file_size for e in entries) > 4 * 1024**3:
            raise ValueError('This backup exceeds the 4 GB restoration limit.')
        for entry in entries:
            allowed = entry.filename in ('vault.json', 'manifest.json')
            allowed = allowed or bool(re.fullmatch(
                r'images/[A-Za-z0-9_.-]+\.(png|jpg|jpeg|webp|bmp|gif)',
                entry.filename, re.I
            ))
            if not allowed or entry.file_size > 256 * 1024**2:
                raise ValueError('Unexpected or oversized file in backup.')
        if 'vault.json' not in names:
            raise ValueError('The backup does not contain vault.json.')
        data = json.loads(archive.read('vault.json').decode('utf-8-sig'))
        validate(data)
        media = {
            n.split('/', 1)[1]: archive.read(n)
            for n in names if n.startswith('images/')
        }
    for node in all_stored_nodes(data):
        missing = image_names(node['html']) - set(media)
        if missing:
            raise ValueError('Backup is missing image: ' + next(iter(missing)))
    return data, media

def install_bundle(vault, path, safety=True):
    data, media = read_bundle(path)
    if safety:
        write_bundle(
            vault.data, vault.images,
            vault.root / 'backups' / ('Before-restore-' + file_stamp() + '.zip')
        )
    remap = {}
    for name, content in media.items():
        dest = vault.images / name
        if dest.exists() and dest.read_bytes() != content:
            new_name = token() + Path(name).suffix.lower()
            remap[name] = new_name
            dest = vault.images / new_name
        if not dest.exists():
            atomic_write(dest, content)
    if remap:
        for node in all_stored_nodes(data):
            def replace(match):
                name = Path(unquote(match.group(1)).lstrip('/')).name
                return 'beastimage:' + remap.get(name, name)
            node['html'] = MEDIA_RE.sub(replace, node['html'])
    vault.change(lambda: setattr(vault, 'data', data))

class MediaDocument(QTextDocument):
    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.setDefaultFont(QFont('Segoe UI', 14))
        self.setDefaultStyleSheet(
            'a { color:#bda2ff; text-decoration:underline; }'
            'h1 { color:#eee6ff; } h2 { color:#c6b5ee; }'
        )
        self.setDocumentMargin(10)

    def loadResource(self, resource_type, name):
        if resource_type == int(QTextDocument.ResourceType.ImageResource):
            if name.scheme() == 'beastimage':
                filename = Path(unquote(name.toString().split(':', 1)[1]).lstrip('/')).name
                path = self.vault.images / filename
                if path.is_file():
                    return QImage(str(path))
            return QImage()
        return None

class Editor(QTextEdit):
    openLink = Signal(str)

    def __init__(self, vault):
        super().__init__()
        self.vault = vault
        self.setObjectName('Editor')
        self.setDocument(MediaDocument(vault, self))
        self.setAcceptDrops(True)
        self.setTabChangesFocus(False)
        self.setPlaceholderText('Start writing. Drop an image. Follow a thought.')
        self.down_point = None

    def add_image(self, image):
        if image.isNull():
            raise ValueError('That image could not be opened.')
        filename = token() + '.png'
        path = self.vault.images / filename
        temporary = path.with_suffix('.tmp')
        if not image.save(str(temporary), 'PNG'):
            raise OSError('Could not save the imported image.')
        os.replace(temporary, path)
        fmt = QTextImageFormat()
        fmt.setName('beastimage:' + filename)
        width = min(720, image.width())
        fmt.setWidth(width)
        fmt.setHeight(image.height() * width / max(1, image.width()))
        cursor = self.textCursor()
        cursor.insertImage(fmt)
        cursor.insertBlock()
        self.setTextCursor(cursor)

    def read_image(self, path):
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            raise ValueError('Cannot open image: ' + str(path))
        return image

    def canInsertFromMimeData(self, source):
        return source.hasImage() or source.hasUrls() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        try:
            if source.hasImage():
                value = source.imageData()
                image = value.toImage() if isinstance(value, QPixmap) else QImage(value)
                self.add_image(image)
                return
            if source.hasUrls():
                urls = source.urls()
                paths = [Path(u.toLocalFile()) for u in urls if u.isLocalFile()]
                supported = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tif', '.tiff'}
                if paths and all(p.suffix.lower() in supported for p in paths):
                    for path in paths:
                        self.add_image(self.read_image(path))
                    return
            super().insertFromMimeData(source)
        except Exception as exc:
            QMessageBox.warning(self, 'Image import', str(exc))

    def mousePressEvent(self, event):
        self.down_point = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        point = event.position().toPoint()
        super().mouseReleaseEvent(event)
        if event.button() != Qt.MouseButton.LeftButton or self.down_point is None:
            return
        if (point - self.down_point).manhattanLength() > 5:
            return
        cursor = self.cursorForPosition(point)
        text = cursor.block().text()
        if cursor.positionInBlock() <= 1 and text.startswith(('☐ ', '☑ ')):
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(
                QTextCursor.MoveOperation.NextCharacter,
                QTextCursor.MoveMode.KeepAnchor
            )
            cursor.insertText('☑' if text.startswith('☐') else '☐')
            return
        address = self.anchorAt(point)
        if address and not self.textCursor().hasSelection():
            self.openLink.emit(address)

    def image_cursor(self, point):
        position = self.cursorForPosition(point).position()
        for candidate in (position, position - 1):
            if candidate < 0 or candidate >= self.document().characterCount() - 1:
                continue
            cursor = QTextCursor(self.document())
            cursor.setPosition(candidate)
            cursor.movePosition(
                QTextCursor.MoveOperation.NextCharacter,
                QTextCursor.MoveMode.KeepAnchor
            )
            if cursor.selectedText() == '\ufffc' and cursor.charFormat().isImageFormat():
                return cursor
        return None

    def contextMenuEvent(self, event):
        cursor = self.image_cursor(event.pos())
        menu = self.createStandardContextMenu()
        if cursor:
            menu.addSeparator()
            action = menu.addAction('Resize image...')
            def resize():
                fmt = cursor.charFormat().toImageFormat()
                name = Path(fmt.name().split(':', 1)[-1].lstrip('/')).name
                image = QImage(str(self.vault.images / name))
                if image.isNull():
                    QMessageBox.warning(self, 'Image', 'The stored image is missing.')
                    return
                width, ok = QInputDialog.getInt(
                    self, 'Image width', 'Display width in pixels:',
                    int(fmt.width() or image.width()), 40, 3000, 20
                )
                if ok:
                    fmt.setWidth(width)
                    fmt.setHeight(image.height() * width / image.width())
                    cursor.setCharFormat(fmt)
            action.triggered.connect(resize)
            paint_action = menu.addAction('Paint on a copy...')
            def paint_copy():
                fmt = cursor.charFormat().toImageFormat()
                name = Path(unquote(fmt.name().split(':', 1)[-1]).lstrip('/')).name
                image = QImage(str(self.vault.images / name))
                if not image.isNull():
                    self.setTextCursor(cursor)
                    self.window().open_paint_image(image)
            paint_action.triggered.connect(paint_copy)
        menu.exec(event.globalPos())
        menu.deleteLater()

def label(text, name='Muted'):
    item = QLabel(text)
    item.setObjectName(name)
    return item

def button(text, callback=None, name=None, tip=None):
    item = QPushButton(text)
    if callback:
        item.clicked.connect(callback)
    if name:
        item.setObjectName(name)
    if tip:
        item.setToolTip(tip)
    return item

def row(*widgets):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for item in widgets:
        if item is None:
            layout.addStretch()
        else:
            layout.addWidget(item)
    return container

def menu_action(menu, text, callback):
    action = menu.addAction(text)
    action.triggered.connect(lambda checked=False: callback())
    return action

class NoteTree(QTreeWidget):
    moved = Signal()
    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setIndentation(19)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAnimated(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def dropEvent(self, event):
        super().dropEvent(event)
        if event.isAccepted():
            self.moved.emit()

class BinButton(QPushButton):
    binRequested = Signal(str)
    def __init__(self):
        super().__init__('Bin')
        self.setObjectName('Danger')
        self.setAcceptDrops(True)
        self.setToolTip('Open the bin, or drag a page here.')

    def dragEnterEvent(self, event):
        if isinstance(event.source(), NoteTree):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if isinstance(event.source(), NoteTree):
            event.acceptProposedAction()

    def dropEvent(self, event):
        source = event.source()
        item = source.currentItem() if isinstance(source, NoteTree) else None
        if item:
            ident = item.data(0, ROLE)
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            QTimer.singleShot(0, lambda: self.binRequested.emit(ident))

class GraphView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor('#101117'))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(160)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.apply_scale)

    def apply_scale(self, value):
        current = self.transform().m11()
        if current:
            factor = float(value) / current
            self.scale(factor, factor)

    def wheelEvent(self, event):
        if not event.angleDelta().y():
            return
        self.animation.stop()
        start = self.transform().m11()
        end = max(.08, min(4.0, start * (1.22 ** (event.angleDelta().y() / 120))))
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        self.animation.start()
        event.accept()

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if self.transform().m11() < .25:
            return
        painter.setPen(QPen(QColor('#232534'), 1))
        step = 40
        left = math.floor(rect.left() / step) * step
        top = math.floor(rect.top() / step) * step
        points = []
        for x in range(int(left), int(rect.right()) + step, step):
            for y in range(int(top), int(rect.bottom()) + step, step):
                points.append(QPointF(x, y))
        if points:
            painter.drawPoints(points)

class GraphNode(QGraphicsEllipseItem):
    def __init__(self, graph, ident, kind, title, tooltip):
        radius = 14 if kind in ('root', 'book') else 10
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.graph, self.ident = graph, ident
        color = QColor(COLORS[kind])
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.lighter(125), 2))
        self.setZValue(3)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(tooltip)
        self.caption = QGraphicsTextItem(title if len(title) <= 25 else title[:23] + '…', self)
        self.caption.setDefaultTextColor(QColor('#d8d9e7'))
        self.caption.setFont(QFont('Segoe UI', 10))
        self.caption.setPos(radius + 5, -13)
        self.caption.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if hasattr(self, 'graph') and not self.graph.building:
                self.graph.update_edges()
                self.graph.save_timer.start()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        if self.ident != '__root__':
            self.graph.main.open_page(self.ident)
            self.graph.main.raise_()
            self.graph.main.activateWindow()
        event.accept()

class Graph(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle('Your constellation - ' + APP)
        self.resize(1100, 780)
        self.building = True
        self.nodes, self.edges = {}, []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Find a page in the constellation...')
        self.nearby = QCheckBox('Selected neighbourhood')
        layout.addWidget(row(
            label('Your constellation', 'Big'), None,
            button('Fit all', self.fit_all),
            button('Reset layout', self.reset_layout)
        ))
        layout.addWidget(row(self.search, self.nearby))
        self.scene = QGraphicsScene(self)
        self.view = GraphView(self.scene)
        layout.addWidget(self.view, 1)
        layout.addWidget(label(
            'Drag dots to arrange • Drag the background to pan • Scroll to zoom • '
            'Double-click a page to open • Teal dotted lines are page links'
        ))
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(300)
        self.save_timer.timeout.connect(self.save_positions)
        self.search.textChanged.connect(self.fade)
        self.nearby.toggled.connect(self.fade)
        self.scene.selectionChanged.connect(self.fade)
        self.build()
        QTimer.singleShot(60, self.fit_all)

    def build(self):
        self.building = True
        self.nodes.clear()
        self.edges.clear()
        self.scene.clear()
        data = self.main.vault.data
        root = GraphNode(self, '__root__', 'root', 'BeastNotes', 'Your collection')
        self.scene.addItem(root)
        self.nodes['__root__'] = root
        automatic = {'__root__': (0, 0)}
        relationships = []

        def weight(node):
            return sum(weight(c) for c in node['children']) if node['children'] else 1

        def arrange(nodes, parent, depth, start, span, trail=()):
            total = sum(weight(n) for n in nodes) or 1
            angle = start
            for node in nodes:
                portion = span * weight(node) / total
                middle = angle + portion / 2
                radius = depth * 190
                automatic[node['id']] = (math.cos(middle) * radius, math.sin(middle) * radius)
                path = trail + (node['title'],)
                item = GraphNode(
                    self, node['id'], node['kind'], node['title'], ' / '.join(path)
                )
                self.scene.addItem(item)
                self.nodes[node['id']] = item
                relationships.append((parent, node['id'], False))
                arrange(node['children'], node['id'], depth + 1, angle, portion, path)
                angle += portion

        arrange(data['roots'], '__root__', 1, -math.pi, math.tau)
        for ident, item in self.nodes.items():
            position = data['layout'].get(ident, automatic[ident])
            if not isinstance(position, (list, tuple)) or len(position) != 2:
                position = automatic[ident]
            try:
                x, y = float(position[0]), float(position[1])
                if not math.isfinite(x) or not math.isfinite(y):
                    raise ValueError()
            except (ValueError, TypeError):
                x, y = automatic[ident]
            item.setPos(x, y)

        used = set()
        for node, _ in walk(data['roots']):
            for target in links(node['html']):
                pair = tuple(sorted((node['id'], target)))
                if target in self.nodes and target != node['id'] and pair not in used:
                    relationships.append((node['id'], target, True))
                    used.add(pair)

        for source, target, explicit in relationships:
            edge = QGraphicsPathItem()
            pen = QPen(QColor('#72cdbb' if explicit else '#49405f'), 1.6 if explicit else 1.3)
            if explicit:
                pen.setStyle(Qt.PenStyle.DotLine)
            edge.setPen(pen)
            edge.setZValue(0 if explicit else -1)
            self.scene.addItem(edge)
            self.edges.append((edge, source, target))
        self.building = False
        self.update_edges()
        self.fade()

    def update_edges(self):
        for item, source, target in self.edges:
            a, b = self.nodes[source].pos(), self.nodes[target].pos()
            path = QPainterPath(a)
            offset = (b.x() - a.x()) * .45
            path.cubicTo(QPointF(a.x() + offset, a.y()), QPointF(b.x() - offset, b.y()), b)
            item.setPath(path)

    def fit_all(self):
        bounds = self.scene.itemsBoundingRect().adjusted(-100, -90, 100, 90)
        self.scene.setSceneRect(bounds.adjusted(-400, -400, 400, 400))
        self.view.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def fade(self):
        query = self.search.text().strip().casefold()
        selected = [n.ident for n in self.scene.selectedItems() if isinstance(n, GraphNode)]
        allowed = set(self.nodes)
        if self.nearby.isChecked() and selected:
            allowed = set(selected)
            for _, a, b in self.edges:
                if a in selected or b in selected:
                    allowed.update((a, b))
        for ident, node in self.nodes.items():
            visible = ident in allowed and (not query or query in node.toolTip().casefold())
            node.setOpacity(1 if visible else .13)
        for edge, source, target in self.edges:
            edge.setOpacity(1 if self.nodes[source].opacity() > .5 and
                            self.nodes[target].opacity() > .5 else .08)

    def save_positions(self):
        if self.building:
            return
        self.main.vault.data['layout'] = {
            ident: [item.pos().x(), item.pos().y()] for ident, item in self.nodes.items()
        }
        self.main.schedule_save()

    def reset_layout(self):
        self.save_timer.stop()
        self.main.vault.data['layout'] = {}
        self.build()
        self.fit_all()
        self.main.schedule_save()

    def closeEvent(self, event):
        self.save_timer.stop()
        self.save_positions()
        event.accept()

class TypingInput(QPlainTextEdit):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.setAcceptDrops(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setMaximumHeight(115)
        self.setPlaceholderText('Type here. The clock starts with your first character.')
        self.setFont(QFont('Consolas', 16))

    def canInsertFromMimeData(self, source):
        return False

    def insertFromMimeData(self, source):
        return

    def dropEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event):
        if self.game.started and time.monotonic() >= self.game.started + self.game.duration:
            self.game.finish()
            return
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            return
        if event.key() == Qt.Key.Key_Backspace or (
            len(event.text()) == 1 and event.text().isprintable()
        ):
            self.moveCursor(QTextCursor.MoveOperation.End)
            super().keyPressEvent(event)

class Sparkline(QWidget):
    def __init__(self):
        super().__init__()
        self.values = []
        self.setMinimumHeight(110)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(15, 15, -15, -15)
        painter.setPen(QPen(QColor('#2d3044'), 1))
        for fraction in (.25, .5, .75):
            y = rect.top() + rect.height() * fraction
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        if len(self.values) < 2:
            painter.setPen(QColor('#9398ae'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Your progress will appear here')
            return
        low, high = min(self.values), max(self.values)
        margin = max(5, (high - low) * .2)
        low, high = max(0, low - margin), high + margin
        points = [
            QPointF(
                rect.left() + i * rect.width() / (len(self.values) - 1),
                rect.bottom() - (value - low) * rect.height() / max(1, high - low)
            ) for i, value in enumerate(self.values)
        ]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        painter.setPen(QPen(QColor('#b49aef'), 3))
        painter.drawPath(path)
        painter.setBrush(QColor('#e4d7ff'))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(points[-1], 4, 4)

def speed(correct, seconds):
    return round(correct * 12 / max(seconds, .1), 1)

class TypingGame(QWidget):
    SENTENCES = [
        'small steps make room for bigger ideas',
        'the quiet evening gives every thought a little space',
        'a good question can open a door you never noticed',
        'keep building until the pieces begin to fit together',
        'somewhere between the stars there is another story',
        'the best time to write an idea down is right now',
        'every new page begins with a single small thought',
        'you do not have to see the whole road to take a step',
        'the rain moves softly across the window tonight',
        'curiosity turns ordinary moments into discoveries',
        'follow the thread and see where the story takes you',
        'there is always another way to connect the dots',
        'the last train carries a thousand different stories',
        'a notebook is a place where unfinished ideas belong'
    ]

    def _classic_base_init(self, main):
        super().__init__()
        self.main = main
        self.started = None
        self.finished = False
        self.old = ''
        self.attempts = self.correct_attempts = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(45, 30, 45, 25)
        layout.setSpacing(16)
        layout.addWidget(label('Find your flow.', 'Big'))
        layout.addWidget(label('A little practice. A clearer head. Your own pace.'))
        self.length = QComboBox()
        self.length.addItems(['15 seconds', '30 seconds', '60 seconds'])
        self.length.setCurrentIndex(1)
        self.mode = QComboBox()
        self.mode.addItems(['Classic lowercase', 'Punctuation', 'Words from my notes'])
        layout.addWidget(row(self.length, self.mode, None, button('New round', self.new_round, 'Accent')))
        self.clock = label('30s', 'Metric')
        self.wpm = label('0 WPM', 'Metric')
        self.accuracy = label('100%', 'Metric')
        layout.addWidget(row(self.clock, None, self.wpm, None, self.accuracy))
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.prompt_view = QTextEdit()
        self.prompt_view.setObjectName('Prompt')
        self.prompt_view.setReadOnly(True)
        self.prompt_view.setMinimumHeight(180)
        self.prompt_view.setMaximumHeight(230)
        layout.addWidget(self.prompt_view)
        self.input = TypingInput(self)
        layout.addWidget(self.input)
        self.result = label('Five correctly positioned characters count as one word.')
        layout.addWidget(self.result)
        self.history_label = label('', 'Section')
        layout.addWidget(self.history_label)
        self.chart = Sparkline()
        layout.addWidget(self.chart, 1)
        self.recent = QListWidget()
        self.recent.setMaximumHeight(145)
        layout.addWidget(self.recent)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)
        self.input.textChanged.connect(self.input_changed)
        self.length.currentIndexChanged.connect(self.new_round)
        self.mode.currentIndexChanged.connect(self.new_round)
        self.new_round()
        self.refresh_history()

    def _classic_base_more_text(self):
        if self.mode.currentIndex() == 2:
            corpus = ' '.join(n['text'] for n, _ in walk(self.main.vault.data['roots']))
            words = re.findall(r'\b[a-z]{2,16}\b', corpus.lower())
            if words:
                return ' '.join(random.choice(words) for _ in range(65))
        sentences = [random.choice(self.SENTENCES) for _ in range(5)]
        if self.mode.currentIndex() == 1:
            return ' '.join(s.capitalize() + random.choice(['.', '.', '!', '?']) for s in sentences)
        return ' '.join(sentences)

    def _classic_base_new_round(self):
        if not hasattr(self, 'input'):
            return
        self.timer.stop()
        self.duration = [15, 30, 60][self.length.currentIndex()]
        self.started, self.finished = None, False
        self.old = ''
        self.attempts = self.correct_attempts = 0
        self.prompt = self.more_text()
        self.input.blockSignals(True)
        self.input.setReadOnly(False)
        self.input.clear()
        self.input.blockSignals(False)
        self.progress.setRange(0, self.duration * 100)
        self.progress.setValue(self.duration * 100)
        self.clock.setText(str(self.duration) + 's')
        self.wpm.setText('0 WPM')
        self.accuracy.setText('100%')
        self.result.setText('The clock starts when you type. Pasting is disabled.')
        self.render_prompt('')
        self.input.setFocus()

    def render_prompt(self, typed):
        start = max(0, (len(typed) // 80 - 1) * 80)
        stop = min(len(self.prompt), start + 390)
        parts = []
        for i in range(start, stop):
            char = self.prompt[i]
            escaped = {'&': '&amp;', '<': '&lt;', '>': '&gt;', ' ': '&nbsp;'}.get(char, char)
            if i < len(typed):
                color = '#8fe0bd' if typed[i] == char else '#ff8fbd'
                background = '#4b263d' if typed[i] != char else 'transparent'
            else:
                color, background = '#a2a6bd', 'transparent'
            if i == len(typed) and not self.finished:
                background = '#4d3c6a'
                color = '#ffffff'
            parts.append('<span style="color:%s;background-color:%s;">%s</span>' %
                         (color, background, escaped))
        self.prompt_view.setHtml(
            '<p style="font-family:Consolas;font-size:20pt;line-height:150%;">' +
            ''.join(parts) + '</p>'
        )

    def input_changed(self):
        if self.finished:
            return
        typed = self.input.toPlainText()
        if typed and self.started is None:
            self.started = time.monotonic()
            self.timer.start()
        while len(self.prompt) < len(typed) + 140:
            self.prompt += ' ' + self.more_text()
        if len(typed) > len(self.old):
            for index in range(len(self.old), len(typed)):
                self.attempts += 1
                self.correct_attempts += int(typed[index] == self.prompt[index])
        self.old = typed
        self.render_prompt(typed)
        self.tick()

    def tick(self):
        if self.started is None:
            return
        elapsed = min(self.duration, time.monotonic() - self.started)
        remaining = max(0, self.duration - elapsed)
        self.clock.setText(str(math.ceil(remaining)) + 's')
        self.progress.setValue(int(remaining * 100))
        correct = sum(a == b for a, b in zip(self.old, self.prompt))
        self.wpm.setText(str(speed(correct, elapsed)) + ' WPM')
        accuracy = 100 * self.correct_attempts / max(1, self.attempts)
        self.accuracy.setText(str(round(accuracy, 1)) + '%')
        if remaining <= 0:
            self.finish()

    def finish(self):
        if self.finished or self.started is None:
            return
        self.finished = True
        self.timer.stop()
        self.input.setReadOnly(True)
        elapsed = min(self.duration, time.monotonic() - self.started)
        correct = sum(a == b for a, b in zip(self.old, self.prompt))
        wpm = speed(correct, elapsed)
        accuracy = round(100 * self.correct_attempts / max(1, self.attempts), 1)
        self.wpm.setText(str(wpm) + ' WPM')
        self.accuracy.setText(str(accuracy) + '%')
        self.clock.setText('Done')
        self.progress.setValue(0)
        score = {
            'at': now(), 'duration': self.duration, 'mode': self.mode.currentText(),
            'wpm': wpm, 'accuracy': accuracy,
            'mistakes': self.attempts - self.correct_attempts
        }
        if self.mode.currentIndex() == 0:
            score['difficulty'] = self.difficulty.currentText()
        self.main.vault.data['scores'].append(score)
        self.main.flush()
        self.result.setText(
            f"{wpm} WPM · {accuracy}% accuracy · {score['mistakes']} mistyped characters"
        )
        self.render_prompt(self.old)
        self.refresh_history()

    def _classic_base_refresh_history(self):
        scores = self.main.vault.data['scores']
        best = max((s['wpm'] for s in scores), default=0)
        self.history_label.setText(f'YOUR PROGRESS    ·    {len(scores)} ROUNDS    ·    BEST {best} WPM')
        self.chart.values = [s['wpm'] for s in scores[-40:]]
        self.chart.update()
        self.recent.clear()
        for score in reversed(scores[-12:]):
            self.recent.addItem(
                f"{score.get('at', '')[:16].replace('T', ' ')}    "
                f"{score['wpm']} WPM    {score['accuracy']}%    "
                f"{score.get('duration', 30)}s"
            )

    _CLASSIC_DIFFICULTY_VERSION = 1

    _CLASSIC_EASY_WORDS = (
        "a an as at be by do go he if in is it me my no of on or so to up us we "
        "all and are ask bag bed big box boy bus can car cat cup day did dog dry "
        "ear eat egg end eye far few fit fly for fox fun get got gum guy had "
        "ham has hat hen her him his hit hot how ice ink jam job joy jug key "
        "kid leg let lid lip log lot low mad man map mat men met mix mug mum "
        "nap net new nod not now nut off old one our out own pan pat paw pen "
        "pet pie pig pin pot put ran rat red row rug run sad sat saw sea see "
        "set she shy sip sit six sky son sun tag tap tea ten the tie tin tip "
        "toe top toy try two use van vet was way web wet who why win won yes "
        "yet you back ball band bank bath bear bell best bird blue boat book "
        "both cake call came card care cold come cook cool dark desk door down "
        "draw each east easy face fact fall fast feel feet find fire fish five "
        "food foot four free from full game gave gift girl give glad gold good "
        "grew grow hair half hand hard have head hear heat held help here high "
        "hill hold home hope hour idea into jump just keep kind knew know lake "
        "land last late leaf left less life like line list live long look lost "
        "love made mail main make many milk mind miss moon more most move much "
        "must name near need next nice nine nose note once only open over page "
        "park part pass past path pick pink play pool rain read real rest rice "
        "ride ring rise road rock room rose rule safe said same sand save seat "
        "seed seem seen ship shoe shop show side sing size slow snow soft some "
        "song soon star stay step stop such sure swim take talk tall team tell "
        "than that them then they thin this time tiny told took town tree true "
        "turn walk wall want warm wash wave ways week well went were west what "
        "when wide wild wind wish with wood word work year your apple beach "
        "bread chair clean clear cloud dream drink early field first fresh "
        "glass grass green happy heart house light lunch music night paper "
        "place plant quiet right river round seven short sleep small smile "
        "sound south space stand start still stone story table thank their "
        "there these thing think those three today train trust under until "
        "voice watch water white whole woman world write young"
    ).split()

    _CLASSIC_HARD_SENTENCES = [
        "although the original explanation appeared straightforward the unexpected consequences required considerably more investigation",
        "before the committee could reach a reasonable conclusion every recommendation needed independent verification",
        "while the surrounding circumstances remained uncertain the experienced coordinator accepted responsibility for the final decision",
        "because the available information contradicted earlier assumptions the researchers reconsidered their interpretation of the evidence",
        "despite considerable disagreement the organisation eventually established a comprehensive strategy for improving communication",
        "when competing priorities threatened the schedule the administrator reorganised responsibilities without compromising essential requirements",
        "rather than immediately dismissing unfamiliar suggestions the thoughtful supervisor encouraged further investigation and constructive discussion",
        "although the infrastructure appeared reliable a detailed examination revealed several vulnerabilities that required immediate attention",
        "after carefully considering the alternatives the representative explained why the proposed arrangement was unnecessarily complicated",
        "whenever concentration began to deteriorate the exceptionally patient instructor recommended a deliberate change of approach",
        "because misunderstanding can undermine cooperation the coordinator communicated expectations before assigning additional responsibilities",
        "while simultaneously monitoring several developments the investigator recognised an inconsistency that fundamentally changed the explanation",
        "despite the extraordinary complexity of the situation the interdisciplinary team maintained a remarkably consistent standard of communication",
        "before implementing the recommendations the organisation examined whether the anticipated improvements justified the additional expenditure",
        "although the preliminary results were encouraging the researcher emphasised that independent verification remained absolutely essential",
        "when the investigation revealed contradictory information the administrator requested a comprehensive explanation before authorising further expenditure",
        "rather than concentrating exclusively on immediate achievements the committee considered the consequences for future generations",
        "after establishing responsibility for the misunderstanding the representatives developed a more effective procedure for sharing information",
        "because apparently insignificant discrepancies can accumulate the experienced accountant approached every calculation with extraordinary precision",
        "while the discussion continued the investigator systematically distinguished reasonable assumptions from conclusions requiring further verification"
    ]

    def __init__(self, main):
        self._classic_base_init(main)

        controls = self.mode.parentWidget()
        controls_layout = controls.layout() if controls is not None else None
        if controls_layout is None or controls_layout.indexOf(self.mode) < 0:
            raise RuntimeError("The typing controls layout was not recognised.")

        self.difficulty = QComboBox(controls)
        self.difficulty.setObjectName("ClassicDifficulty")
        self.difficulty.addItems(["Easy", "Moderate", "Hard"])
        self.difficulty.setMinimumWidth(120)
        self.difficulty.setToolTip("Difficulty for Classic lowercase")

        saved = self.main.vault.data["prefs"].get(
            "typing_classic_difficulty", "Moderate"
        )
        if saved not in ("Easy", "Moderate", "Hard"):
            saved = "Moderate"
        self.difficulty.setCurrentText(saved)
        controls_layout.insertWidget(
            controls_layout.indexOf(self.mode) + 1,
            self.difficulty
        )

        self.difficulty_hint = label("")
        self.difficulty_hint.setWordWrap(True)
        outer = self.layout()
        controls_position = outer.indexOf(controls)
        if controls_position < 0:
            raise RuntimeError("The typing controls container was not recognised.")
        outer.insertWidget(controls_position + 1, self.difficulty_hint)

        self.difficulty.currentTextChanged.connect(
            self._classic_difficulty_changed
        )
        self.new_round()

    def _classic_difficulty_changed(self, *_unused):
        self.main.vault.data["prefs"]["typing_classic_difficulty"] = (
            self.difficulty.currentText()
        )
        self.new_round()
        self.main.schedule_save()

    def new_round(self, *_unused):
        if hasattr(self, "difficulty"):
            classic = self.mode.currentIndex() == 0
            self.difficulty.setVisible(classic)
            self.difficulty_hint.setVisible(classic)
            descriptions = {
                "Easy": "Easy / short, familiar words to build speed and rhythm",
                "Moderate": "Moderate / basic sentences with everyday words",
                "Hard": "Hard / longer words and more complex sentence structures"
            }
            self.difficulty_hint.setText(
                descriptions.get(self.difficulty.currentText(), descriptions["Moderate"])
            )
        return self._classic_base_new_round()

    def more_text(self):
        if self.mode.currentIndex() != 0:
            return self._classic_base_more_text()

        difficulty = (
            self.difficulty.currentText()
            if hasattr(self, "difficulty")
            else "Moderate"
        )
        if difficulty == "Easy":
            return " ".join(random.choices(self._CLASSIC_EASY_WORDS, k=90))
        if difficulty == "Hard":
            return " ".join(random.sample(self._CLASSIC_HARD_SENTENCES, 5))
        return self._classic_base_more_text()

    def refresh_history(self):
        self._classic_base_refresh_history()
        for index, score in enumerate(reversed(self.main.vault.data["scores"][-12:])):
            item = self.recent.item(index)
            if item is None:
                continue
            mode = score.get("mode", "")
            difficulty = score.get("difficulty")
            detail = mode
            if mode == "Classic lowercase" and difficulty:
                detail += " / " + difficulty
            if detail:
                item.setText(item.text() + "    " + detail)

class BackupThread(QThread):
    done = Signal(str, str)
    def __init__(self, data, images, destination, parent=None):
        super().__init__(parent)
        self.data, self.images, self.destination = data, images, destination

    def run(self):
        try:
            write_bundle(self.data, self.images, self.destination)
            self.done.emit(str(self.destination), '')
        except Exception as exc:
            self.done.emit('', str(exc))

def legacy_nodes(raw):
    if isinstance(raw, dict):
        chosen = None
        for key in ('roots', 'items', 'tree', 'books', 'notebooks', 'notes', 'nodes'):
            if key in raw and isinstance(raw[key], list):
                chosen = raw[key]
                break
            if key == 'tree' and isinstance(raw.get(key), dict):
                return legacy_nodes(raw[key])
        if chosen is None and isinstance(raw.get('root'), dict):
            root = raw['root']
            chosen = [root] if root.get('title') or root.get('name') else root.get('children')
        if chosen is None and ('title' in raw or 'name' in raw):
            chosen = [raw]
        if chosen is None:
            raise ValueError(
                'The old JSON structure was not recognised. Nothing was imported or changed.'
            )
        raw = chosen
    if not isinstance(raw, list):
        raise ValueError('Expected a list of pages in the old file.')

    def convert(item, depth=0):
        if not isinstance(item, dict):
            raise ValueError('An old page has an unsupported structure.')
        kind = str(item.get('kind', item.get('type', item.get('node_type', 'note')))).lower()
        aliases = {
            'notebook': 'book', 'section': 'chapter', 'page': 'note',
            'folder': 'book' if depth == 0 else 'chapter'
        }
        kind = aliases.get(kind, kind)
        if kind not in ('book', 'chapter', 'note'):
            raise ValueError('Unrecognised old page type: ' + kind)
        content = item.get('content', '')
        content_obj = content if isinstance(content, dict) else {}
        markup = item.get('html') or item.get('content_html') or content_obj.get('html')
        if not markup:
            text = item.get('text', item.get('plain_text', content_obj.get('text', content)))
            if not isinstance(text, str):
                raise ValueError('An old page contains unsupported content.')
            if re.search(r'<(?:html|p|h[1-6]|div|span|ul|br)[\s>]', text, re.I):
                markup = text
            else:
                doc = QTextDocument()
                doc.setPlainText(text)
                markup = doc.toHtml()
        node = new_node(kind, str(item.get('title', item.get('name', 'Untitled'))), markup)
        node['id'] = str(item.get('id') or item.get('uid') or item.get('uuid') or token())
        node['favorite'] = bool(item.get('favorite', item.get('pinned', False)))
        tags = item.get('tags', [])
        node['tags'] = [str(t) for t in tags] if isinstance(tags, list) else [
            x.strip().lstrip('#') for x in str(tags).split(',') if x.strip()
        ]
        children = item.get('children', [])
        if not isinstance(children, list):
            raise ValueError('An old page has an unsupported children field.')
        node['children'] = [convert(child, depth + 1) for child in children]
        node['created'] = str(item.get('created', now()))
        node['updated'] = str(item.get('updated', now()))
        return node

    return [convert(n) for n in raw]

class Window(StudioMixin, QMainWindow):
    def __init__(self, vault, testing=False):
        super().__init__()
        self.vault, self.testing = vault, testing
        self.current = None
        self.loading = self.rebuilding = False
        self.only_favorites = False
        self.focused = False
        self.worker = None
        self.last_backup = 0
        self.save_error_shown = False
        self.graphs = []
        self.items = {}
        self.setWindowTitle(APP)
        size = vault.data['prefs'].get('window_size', [1500, 940])
        self.resize(max(1000, int(size[0])), max(700, int(size[1])))
        self.setMinimumSize(1000, 680)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(500)
        self.save_timer.timeout.connect(self.flush)

        shell = QWidget()
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(shell)
        header = QWidget()
        header.setObjectName('Header')
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 13, 20, 13)
        hl.setSpacing(10)
        hl.addWidget(label('BeastNotes', 'Brand'))
        hl.addWidget(label('V4  /  STUDIO', 'Badge'))
        hl.addSpacing(20)
        self.notes_nav = button('Notes', lambda: self.switch_tab(0))
        self.typing_nav = button('Typing', lambda: self.switch_tab(1))
        nav = QButtonGroup(self)
        nav.setExclusive(True)
        for b in (self.notes_nav, self.typing_nav):
            b.setCheckable(True)
            nav.addButton(b)
            hl.addWidget(b)
        self.notes_nav.setChecked(True)
        hl.addStretch()
        self.totals = label('')
        hl.addWidget(self.totals)
        hl.addSpacing(10)
        hl.addWidget(button('Import', self.import_workspace))
        hl.addWidget(button('Graph', self.open_graph))
        hl.addWidget(button('Backups', self.backup_browser))
        more = button('More')
        more_menu = QMenu(more)
        menu_action(more_menu, 'Back up now', self.backup_now)
        menu_action(more_menu, 'Choose backup folder...', self.choose_backup_folder)
        more_menu.addSeparator()
        menu_action(more_menu, 'Export this page...', self.export_page)
        menu_action(more_menu, 'Import a text or Markdown page...', self.import_text)
        menu_action(more_menu, 'Import legacy notes...', self.import_old)
        menu_action(more_menu, 'Open V4 data folder', self.open_data_folder)
        more_menu.addSeparator()
        menu_action(more_menu, 'About BeastNotes V4', self.about)
        more.setMenu(more_menu)
        hl.addWidget(more)
        outer.addWidget(header)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.stack.addWidget(self.splitter)
        self.side = QWidget()
        self.side.setObjectName('Side')
        sl = QVBoxLayout(self.side)
        sl.setContentsMargins(16, 20, 12, 16)
        sl.setSpacing(12)
        sl.addWidget(label('YOUR WORKSPACE', 'Section'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search everything...')
        self.search.setClearButtonEnabled(True)
        sl.addWidget(self.search)
        self.all_filter = button('All pages', lambda: self.set_filter(False))
        self.fav_filter = button('Favourites', lambda: self.set_filter(True))
        for b in (self.all_filter, self.fav_filter):
            b.setCheckable(True)
        self.all_filter.setChecked(True)
        sl.addWidget(row(self.all_filter, self.fav_filter))
        self.tree = NoteTree()
        sl.addWidget(self.tree, 1)
        self.results = QListWidget()
        self.results.hide()
        sl.addWidget(self.results, 1)
        add = button('+ Add page', name='Accent')
        add_menu = QMenu(add)
        menu_action(add_menu, 'New book', lambda: self.create_page('book'))
        menu_action(add_menu, 'New chapter', lambda: self.create_page('chapter'))
        menu_action(add_menu, 'New note', lambda: self.create_page('note'))
        add.setMenu(add_menu)
        self.bin_button = BinButton()
        sl.addWidget(row(add, self.bin_button))
        sl.addWidget(label('A space for the things worth keeping.'))
        self.side.setMinimumWidth(230)
        self.splitter.addWidget(self.side)

        writing = QWidget()
        wl = QVBoxLayout(writing)
        wl.setContentsMargins(30, 20, 30, 12)
        wl.setSpacing(9)
        self.breadcrumb = label('')
        self.breadcrumb.setWordWrap(True)
        self.breadcrumb.setMinimumWidth(350)
        self.favorite_button = button('☆', self.toggle_favorite, tip='Favourite this page')
        self.favorite_button.setCheckable(True)
        self.quick_add = button('+ Note', self.quick_create)
        self.focus_button = button('Focus', self.toggle_focus)
        wl.addWidget(row(self.breadcrumb, None, self.favorite_button, self.quick_add, self.focus_button))
        self.title = QLineEdit()
        self.title.setObjectName('Title')
        self.title.setPlaceholderText('Untitled')
        wl.addWidget(self.title)
        self.editor = Editor(vault)

        self.bold = button('B', self.set_bold, tip='Bold · Ctrl+B')
        self.bold.setCheckable(True)
        self.bold.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        self.italic = button('I', self.set_italic, tip='Italic · Ctrl+I')
        self.italic.setCheckable(True)
        self.heading = QComboBox()
        self.heading.addItems(['Normal', 'Heading 1', 'Heading 2'])
        self.heading.setMaximumWidth(135)
        toolbar = row(
            self.bold, self.italic, self.heading,
            button('☐', self.toggle_checkbox, tip='Insert or toggle a checkbox'),
            button('• List', self.make_list),
            button('↗ Link', self.insert_link),
            button('Image', self.pick_image),
            button('Paint', self.open_paint, tip='Draw a sketch and insert it into this page'),
            None,
            button('A−', self.editor.zoomOut, tip='Zoom out'),
            button('A+', self.editor.zoomIn, tip='Zoom in')
        )
        wl.addWidget(toolbar)
        wl.addWidget(self.editor, 1)
        self.page_stats = label('')
        self.saved_label = label('● Saved locally', 'Saved')
        self.saved_label.setMinimumWidth(125)
        wl.addWidget(row(self.page_stats, None, self.saved_label))
        self.splitter.addWidget(writing)

        self.details = QWidget()
        self.details.setObjectName('Details')
        dl = QVBoxLayout(self.details)
        dl.setContentsMargins(17, 24, 17, 16)
        dl.setSpacing(12)
        dl.addWidget(label('PAGE DETAILS', 'Section'))
        self.detail_summary = label('')
        self.detail_summary.setWordWrap(True)
        dl.addWidget(self.detail_summary)
        dl.addWidget(label('TAGS', 'Section'))
        self.tags = QLineEdit()
        self.tags.setPlaceholderText('work, ideas, personal')
        dl.addWidget(self.tags)
        dl.addWidget(label('Comma separated · searchable with #tag'))
        dl.addWidget(label('ON THIS PAGE', 'Section'))
        self.outline = QListWidget()
        dl.addWidget(self.outline, 1)
        dl.addWidget(label('LINKS TO THIS PAGE', 'Section'))
        self.backlinks = QListWidget()
        dl.addWidget(self.backlinks, 1)
        self.details.setMinimumWidth(205)
        self.splitter.addWidget(self.details)
        self.splitter.setSizes(vault.data['prefs'].get('splitter', [280, 970, 250]))
        self.splitter.setStretchFactor(1, 1)

        self.game = TypingGame(self)
        self.stack.addWidget(self.game)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(140)
        self.search_timer.timeout.connect(self.update_search)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.results.itemClicked.connect(lambda item: self.open_result(item))
        self.tree.currentItemChanged.connect(self.tree_selected)
        self.tree.itemDoubleClicked.connect(lambda item, column: self.rename_page(item.data(0, ROLE)))
        self.tree.customContextMenuRequested.connect(self.tree_menu)
        self.tree.moved.connect(self.tree_moved)
        self.bin_button.clicked.connect(self.bin_dialog)
        self.bin_button.binRequested.connect(self.bin_page)
        self.editor.textChanged.connect(self.schedule_save)
        self.editor.cursorPositionChanged.connect(self.sync_format)
        self.editor.openLink.connect(self.follow_link)
        self.title.textChanged.connect(self.title_changed)
        self.tags.editingFinished.connect(self.schedule_save)
        self.heading.currentIndexChanged.connect(self.set_heading)
        self.outline.itemClicked.connect(self.jump_heading)
        self.backlinks.itemClicked.connect(lambda item: self.open_result(item))

        self.shortcuts = []
        for keys, fn in (
            ('Ctrl+N', lambda: self.create_page('note')),
            ('Ctrl+Shift+N', lambda: self.create_page('book')),
            ('Ctrl+F', lambda: self.search.setFocus()),
            ('Ctrl+B', lambda: self.bold.click()),
            ('Ctrl+I', lambda: self.italic.click())
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(fn)
            self.shortcuts.append(shortcut)

        self.render_tree()
        desired = vault.data['prefs'].get('last')
        self.open_page(desired if vault.get(desired) else self.first_page(), save=False)
        self.refresh_totals()
        self.statusBar().showMessage('V4 workspace · local to this computer')
        self.setup_studio()

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        self.notes_nav.setChecked(index == 0)
        self.typing_nav.setChecked(index == 1)
        if index == 1:
            self.game.input.setFocus()

    def error(self, exc):
        QMessageBox.critical(self, APP, str(exc))

    def first_page(self):
        nodes = list(walk(self.vault.data['roots']))
        return next((n['id'] for n, _ in nodes if n['kind'] == 'note'),
                    nodes[0][0]['id'] if nodes else None)

    def capture(self):
        node = self.vault.get(self.current)
        if not node or self.loading:
            return
        markup = self.editor.toHtml()
        text = self.editor.toPlainText().replace('\ufffc', '')
        title = self.title.text().strip() or 'Untitled'
        tags = list(dict.fromkeys(
            t.strip().lstrip('#') for t in self.tags.text().split(',') if t.strip().lstrip('#')
        ))
        if (node['html'], node['text'], node['title'], node['tags']) != (markup, text, title, tags):
            node.update(html=markup, text=text, title=title, tags=tags, updated=now())
        if self.current in self.items:
            self.items[self.current].setText(0, self.tree_caption(node))

    def schedule_save(self):
        if self.loading:
            return
        self.saved_label.setText('● Saving...')
        self.saved_label.setStyleSheet('color:#c9b5ef;')
        self.save_timer.start()

    def title_changed(self):
        if self.loading:
            return
        node = self.vault.get(self.current)
        if node and self.current in self.items:
            preview = dict(node, title=self.title.text().strip() or 'Untitled')
            self.items[self.current].setText(0, self.tree_caption(preview))
        self.schedule_save()

    def flush(self):
        self.save_timer.stop()
        try:
            self.capture()
            wrote = self.vault.save()
            self.saved_label.setText('● Saved locally')
            self.saved_label.setStyleSheet('color:#81d9ba;')
            self.save_error_shown = False
            self.refresh_totals()
            self.refresh_details()
            self.update_search()
            if wrote and not self.testing and time.monotonic() - self.last_backup >= 300:
                self.start_backup()
            return True
        except Exception as exc:
            self.saved_label.setText('● Save failed')
            self.saved_label.setStyleSheet('color:#ff91b5;')
            if not self.save_error_shown:
                self.save_error_shown = True
                self.error('Your changes remain in memory, but saving failed:\n\n' + str(exc))
            return False

    def modify(self, fn):
        if not self.flush():
            return False
        try:
            self.vault.change(fn)
            self.render_tree()
            if self.current and not self.vault.get(self.current):
                self.current = None
                self.open_page(self.first_page(), save=False)
            self.refresh_totals()
            self.refresh_details()
            self.update_search()
            return True
        except Exception as exc:
            self.error(exc)
            self.render_tree()
            return False

    def tree_caption(self, node):
        symbol = {'book': '▣', 'chapter': '▤', 'note': '•'}[node['kind']]
        return ('★ ' if node.get('favorite') else symbol + ' ') + node['title']

    def render_tree(self):
        expanded = set()
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                expanded.add(item.data(0, ROLE))
            iterator += 1
        was_empty = not self.items
        self.rebuilding = True
        self.tree.clear()
        self.items = {}
        def add(nodes, parent=None, trail=()):
            for node in nodes:
                item = QTreeWidgetItem([self.tree_caption(node)])
                item.setData(0, ROLE, node['id'])
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable |
                    Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
                )
                item.setForeground(0, QBrush(QColor(COLORS[node['kind']])))
                path = trail + (node['title'],)
                item.setToolTip(0, ' / '.join(path))
                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
                self.items[node['id']] = item
                add(node['children'], item, path)
                item.setExpanded(node['id'] in expanded or (was_empty and len(path) < 3))
        add(self.vault.data['roots'])
        if self.current in self.items:
            self.tree.setCurrentItem(self.items[self.current])
        self.rebuilding = False

    def tree_selected(self, item, previous):
        if item and not self.rebuilding:
            self.open_page(item.data(0, ROLE))

    def _open_page(self, ident, save=True):
        if save and not self.flush():
            self.rebuilding = True
            if self.current in self.items:
                self.tree.setCurrentItem(self.items[self.current])
            self.rebuilding = False
            return
        node = self.vault.get(ident)
        self.loading = True
        self.current = ident if node else None
        self.title.setEnabled(bool(node))
        self.editor.setEnabled(bool(node))
        self.tags.setEnabled(bool(node))
        self.favorite_button.setEnabled(bool(node))
        self.title.setText(node['title'] if node else '')
        self.editor.setHtml(node['html'] if node else '')
        self.tags.setText(', '.join(node['tags']) if node else '')
        self.favorite_button.setChecked(bool(node and node.get('favorite')))
        self.favorite_button.setText('★' if node and node.get('favorite') else '☆')
        self.quick_add.setText(
            '+ Book' if not node else '+ Chapter' if node['kind'] == 'book' else '+ Note'
        )
        path = next((p for n, p in walk(self.vault.data['roots']) if n['id'] == ident), ())
        self.breadcrumb.setText(' / '.join(path) or 'Your workspace')
        self.loading = False
        if node:
            self.vault.data['prefs']['last'] = ident
            item = self.items.get(ident)
            if item:
                self.rebuilding = True
                parent = item.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                self.rebuilding = False
        self.editor.setExtraSelections([])
        query = self.search.text().strip().lstrip('#')
        if query and node:
            cursor = self.editor.document().find(query.split()[0])
            if not cursor.isNull():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format.setBackground(QColor('#58416f'))
                self.editor.setExtraSelections([selection])
                self.editor.setTextCursor(cursor)
                self.editor.ensureCursorVisible()
        self.refresh_details()
        self.sync_format()
        self.switch_tab(0)

    def set_filter(self, favorites):
        self.only_favorites = favorites
        self.all_filter.setChecked(not favorites)
        self.fav_filter.setChecked(favorites)
        self.update_search()

    def update_search(self):
        query = self.search.text().strip().casefold()
        searching = bool(query) or self.only_favorites
        self.tree.setVisible(not searching)
        self.results.setVisible(searching)
        self.results.clear()
        if not searching:
            return
        terms = query.split()
        matches = 0
        for node, path in walk(self.vault.data['roots']):
            haystack = (' / '.join(path) + '\n' + node['text'] + '\n' +
                        ' '.join('#' + t for t in node['tags'])).casefold()
            if self.only_favorites and not node.get('favorite'):
                continue
            if not all(term in haystack for term in terms):
                continue
            snippet = node['text'].replace('\n', ' ')
            if terms:
                position = snippet.casefold().find(terms[0])
                if position >= 0:
                    snippet = snippet[max(0, position - 35):]
            text = ' / '.join(path)
            if snippet:
                text += '\n' + snippet[:95]
            item = QListWidgetItem(text)
            item.setData(ROLE, node['id'])
            item.setToolTip(' / '.join(path))
            self.results.addItem(item)
            matches += 1
        if not matches:
            item = QListWidgetItem('No matching pages')
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)

    def open_result(self, item):
        ident = item.data(ROLE)
        if ident:
            self.open_page(ident)

    def refresh_totals(self):
        nodes = [n for n, _ in walk(self.vault.data['roots'])]
        notes = sum(n['kind'] == 'note' for n in nodes)
        words = sum(len(n['text'].split()) for n in nodes)
        chars = sum(len(n['text']) for n in nodes)
        self.totals.setText(f'{notes:,} notes · {words:,} words · {chars:,} chars')
        pending = sum(not r.get('restored') for r in self.vault.data['trash'])
        self.bin_button.setText(f'Bin · {pending}')

    def refresh_details(self):
        node = self.vault.get(self.current)
        self.outline.clear()
        self.backlinks.clear()
        if not node:
            self.page_stats.setText('Create a book to begin.')
            self.detail_summary.setText('No page selected')
            return
        text = self.editor.toPlainText().replace('\ufffc', '')
        words = len(text.split())
        self.page_stats.setText(f'{words:,} words · {len(text):,} characters · {max(1, math.ceil(words / 220))} min read')
        self.detail_summary.setText(
            node['kind'].capitalize() + '\nUpdated ' +
            node.get('updated', '')[:16].replace('T', ' ')
        )
        block = self.editor.document().begin()
        while block.isValid():
            level = block.blockFormat().headingLevel()
            if level:
                item = QListWidgetItem(('    ' if level > 1 else '') + block.text())
                item.setData(ROLE, block.position())
                self.outline.addItem(item)
            block = block.next()
        if not self.outline.count():
            item = QListWidgetItem('Headings will appear here')
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.outline.addItem(item)
        for source, path in walk(self.vault.data['roots']):
            if source['id'] != self.current and self.current in links(source['html']):
                item = QListWidgetItem(source['title'])
                item.setToolTip(' / '.join(path))
                item.setData(ROLE, source['id'])
                self.backlinks.addItem(item)
        if not self.backlinks.count():
            item = QListWidgetItem('No incoming links yet')
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.backlinks.addItem(item)

    def jump_heading(self, item):
        position = item.data(ROLE)
        if position is not None:
            cursor = self.editor.textCursor()
            cursor.setPosition(position)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
            self.editor.setFocus()

    def quick_create(self):
        node = self.vault.get(self.current)
        self.create_page('book' if not node else 'chapter' if node['kind'] == 'book' else 'note')

    def create_page(self, kind, parent_id=None):
        if parent_id is None and kind != 'book':
            parent_id = self.current
        title, ok = QInputDialog.getText(self, 'New ' + kind, 'Title:')
        if not ok:
            return
        node = new_node(kind, title.strip() or 'Untitled')
        def action():
            parent = self.vault.get(parent_id)
            target = parent['children'] if parent and kind != 'book' else self.vault.data['roots']
            target.append(node)
        if self.modify(action):
            self.open_page(node['id'], save=False)
            self.editor.setFocus()

    def rename_page(self, ident):
        node = self.vault.get(ident)
        if not node:
            return
        title, ok = QInputDialog.getText(self, 'Rename page', 'Title:', text=node['title'])
        if not ok or not title.strip():
            return
        def action():
            target = self.vault.get(ident)
            target['title'] = title.strip()
            target['updated'] = now()
        if self.modify(action) and ident == self.current:
            self.loading = True
            self.title.setText(title.strip())
            self.loading = False
            path = next((p for n, p in walk(self.vault.data['roots']) if n['id'] == ident), ())
            self.breadcrumb.setText(' / '.join(path))

    def toggle_favorite(self):
        node = self.vault.get(self.current)
        if node:
            ident = self.current
            def action():
                target = self.vault.get(ident)
                target['favorite'] = not target.get('favorite', False)
            if self.modify(action):
                favorite = self.vault.get(ident).get('favorite')
                self.favorite_button.setChecked(favorite)
                self.favorite_button.setText('★' if favorite else '☆')

    def toggle_focus(self):
        self.focused = not self.focused
        self.side.setVisible(not self.focused)
        self.details.setVisible(not self.focused)
        self.focus_button.setText('Exit focus' if self.focused else 'Focus')
        self.editor.setFocus()

    def tree_menu(self, point):
        item = self.tree.itemAt(point)
        ident = item.data(0, ROLE) if item else None
        menu = QMenu(self)
        menu_action(menu, 'New book', lambda: self.create_page('book'))
        menu_action(menu, 'New chapter here', lambda: self.create_page('chapter', ident))
        menu_action(menu, 'New note here', lambda: self.create_page('note', ident))
        if item:
            menu.addSeparator()
            menu_action(menu, 'Rename', lambda: self.rename_page(ident))
            menu_action(menu, 'Expand branch', lambda: item.setExpanded(True))
            menu_action(menu, 'Collapse branch', lambda: item.setExpanded(False))
            menu.addSeparator()
            menu_action(menu, 'Move to bin', lambda: self.bin_page(ident))
        menu.exec(self.tree.viewport().mapToGlobal(point))

    def tree_moved(self):
        if self.rebuilding:
            return
        by_id = {n['id']: n for n, _ in walk(self.vault.data['roots'])}
        def build(item):
            ident = item.data(0, ROLE)
            if ident not in by_id:
                raise ValueError('The moved page could not be identified.')
            node = dict(by_id[ident])
            node['children'] = [build(item.child(i)) for i in range(item.childCount())]
            return node
        try:
            if not self.flush():
                self.render_tree()
                return
            roots = [build(self.tree.topLevelItem(i)) for i in range(self.tree.topLevelItemCount())]
            count = len(list(walk(roots)))
            if count != len(by_id):
                raise ValueError('The move would lose or duplicate a page.')
            self.vault.change(lambda: self.vault.data.__setitem__('roots', roots))
            self.render_tree()
            if self.current:
                path = next((p for n, p in walk(roots) if n['id'] == self.current), ())
                self.breadcrumb.setText(' / '.join(path))
        except Exception as exc:
            self.error(exc)
            self.render_tree()

    def bin_page(self, ident):
        if not self.vault.get(ident) or not self.flush():
            return
        try:
            self.vault.bin_page(ident)
            if not self.vault.get(self.current):
                self.current = None
                self.render_tree()
                self.open_page(self.first_page(), save=False)
            else:
                self.render_tree()
            self.refresh_totals()
            self.refresh_details()
            self.update_search()
            self.statusBar().showMessage('Moved to the bin. Restore it whenever you need it.', 7000)
        except Exception as exc:
            self.error(exc)

    def bin_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Bin - recover your pages')
        dialog.resize(650, 440)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('Nothing disappears in a hurry.', 'Big'))
        layout.addWidget(label('Restoring a branch restores all of its nested pages and content.'))
        listing = QListWidget()
        layout.addWidget(listing, 1)
        def refresh():
            listing.clear()
            for index, record in enumerate(self.vault.data['trash']):
                if not record.get('restored'):
                    count = len(list(walk([record['node']])))
                    item = QListWidgetItem(
                        f"{record['node']['title']}    ·    {count} pages\n"
                        f"Binned {record.get('at', '')[:19].replace('T', ' ')}"
                    )
                    item.setData(ROLE, index)
                    listing.addItem(item)
        def restore():
            selected = listing.currentItem()
            if not selected or not self.flush():
                return
            try:
                ident = self.vault.restore_page(selected.data(ROLE))
                self.render_tree()
                self.open_page(ident, save=False)
                self.refresh_totals()
                refresh()
            except Exception as exc:
                self.error(exc)
        layout.addWidget(row(None, button('Restore selected', restore, 'Accent'), button('Close', dialog.accept)))
        listing.itemDoubleClicked.connect(lambda item: restore())
        refresh()
        dialog.exec()

    def set_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(int(QFont.Weight.Bold if self.bold.isChecked() else QFont.Weight.Normal))
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def set_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(self.italic.isChecked())
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def set_heading(self, level):
        if self.loading or not self.current:
            return
        cursor = self.editor.textCursor()
        block = QTextBlockFormat(cursor.blockFormat())
        block.setHeadingLevel(level)
        block.setTopMargin(16 if level else 5)
        block.setBottomMargin(8)
        cursor.mergeBlockFormat(block)
        fmt = QTextCharFormat()
        fmt.setFontPointSize({0: 14, 1: 25, 2: 19}[level])
        fmt.setFontWeight(int(QFont.Weight.Bold if level else QFont.Weight.Normal))
        cursor.mergeCharFormat(fmt)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def sync_format(self):
        fmt = self.editor.currentCharFormat()
        self.bold.setChecked(fmt.fontWeight() >= int(QFont.Weight.Bold))
        self.italic.setChecked(fmt.fontItalic())
        self.heading.blockSignals(True)
        self.heading.setCurrentIndex(min(2, self.editor.textCursor().blockFormat().headingLevel()))
        self.heading.blockSignals(False)

    def toggle_checkbox(self):
        cursor = self.editor.textCursor()
        text = cursor.block().text()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.beginEditBlock()
        if text.startswith(('☐ ', '☑ ')):
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText('☑' if text.startswith('☐') else '☐')
        else:
            cursor.insertText('☐ ')
        cursor.endEditBlock()
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def make_list(self):
        cursor = self.editor.textCursor()
        fmt = QTextListFormat()
        fmt.setStyle(QTextListFormat.Style.ListDisc)
        cursor.createList(fmt)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def insert_link(self):
        if not self.current:
            return
        cursor = QTextCursor(self.editor.textCursor())
        dialog = QDialog(self)
        dialog.setWindowTitle('Link to a page')
        dialog.resize(540, 450)
        layout = QVBoxLayout(dialog)
        search = QLineEdit()
        search.setPlaceholderText('Search pages...')
        listing = QListWidget()
        layout.addWidget(search)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        def refresh():
            listing.clear()
            query = search.text().casefold()
            for node, path in walk(self.vault.data['roots']):
                if query in ' / '.join(path).casefold():
                    item = QListWidgetItem(' / '.join(path))
                    item.setData(ROLE, node['id'])
                    listing.addItem(item)
            if listing.count():
                listing.setCurrentRow(0)
        search.textChanged.connect(refresh)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        listing.itemDoubleClicked.connect(lambda item: dialog.accept())
        refresh()
        if dialog.exec() != QDialog.DialogCode.Accepted or not listing.currentItem():
            return
        target = self.vault.get(listing.currentItem().data(ROLE))
        if not target:
            return
        text = cursor.selectedText().replace('\u2029', ' ') or target['title']
        original = QTextCharFormat(cursor.charFormat())
        fmt = QTextCharFormat(original)
        fmt.setAnchor(True)
        fmt.setAnchorHref('beastnote:' + target['id'])
        fmt.setForeground(QColor('#bea3ff'))
        fmt.setFontUnderline(True)
        cursor.insertText(text, fmt)
        original.setAnchor(False)
        original.setAnchorHref('')
        original.setFontUnderline(False)
        self.editor.setTextCursor(cursor)
        self.editor.setCurrentCharFormat(original)
        self.editor.setFocus()
        self.schedule_save()

    def follow_link(self, address):
        url = QUrl(address)
        if url.scheme().lower() in ('beastnote', 'beastnotes', 'note'):
            ident = unquote(address.split(':', 1)[1].lstrip('/')).split('?', 1)[0].split('#', 1)[0]
            if self.vault.get(ident):
                self.open_page(ident)
            else:
                QMessageBox.information(
                    self, 'Page unavailable',
                    'That page is unavailable. If it is in the bin, restore it to reconnect this link.'
                )
        elif url.scheme().lower() in ('https', 'http', 'mailto'):
            QDesktopServices.openUrl(url)

    def pick_image(self):
        if not self.current:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, 'Insert images', '',
            'Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)'
        )
        try:
            for path in paths:
                self.editor.add_image(self.editor.read_image(path))
        except Exception as exc:
            self.error(exc)

    def open_graph(self):
        if not self.flush():
            return
        graph = Graph(self)
        self.graphs.append(graph)
        graph.show()

    def export_page(self):
        if not self.current or not self.flush():
            return
        node = self.vault.get(self.current)
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', node['title'])[:100] or 'Page'
        path, selected = QFileDialog.getSaveFileName(
            self, 'Export this page', str(Path.home() / (safe_name + '.html')),
            'Portable HTML (*.html);;Plain text (*.txt)'
        )
        if not path:
            return
        try:
            if selected.startswith('Plain'):
                content = node['text']
            else:
                def replace(match):
                    name = Path(unquote(match.group(1)).lstrip('/')).name
                    image = self.vault.images / name
                    if not image.exists():
                        raise ValueError('A page image is missing: ' + name)
                    return 'data:image/png;base64,' + base64.b64encode(image.read_bytes()).decode('ascii')
                content = MEDIA_RE.sub(replace, node['html'])
            atomic_write(Path(path), content.encode('utf-8'))
            self.statusBar().showMessage('Page exported to ' + path, 8000)
        except Exception as exc:
            self.error(exc)

    def import_text(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import a page', '', 'Text and Markdown (*.txt *.md *.markdown)'
        )
        if not path:
            return
        try:
            source = Path(path)
            text = source.read_text(encoding='utf-8-sig')
            doc = QTextDocument()
            if source.suffix.lower() in ('.md', '.markdown'):
                doc.setMarkdown(text)
            else:
                doc.setPlainText(text)
            node = new_node('note', source.stem, doc.toHtml())
            parent_id = self.current
            def action():
                parent = self.vault.get(parent_id)
                (parent['children'] if parent else self.vault.data['roots']).append(node)
            if self.modify(action):
                self.open_page(node['id'], save=False)
        except Exception as exc:
            self.error(exc)

    def import_old(self):
        if not self.flush():
            return
        guesses = []
        for base in (os.environ.get('APPDATA'), os.environ.get('LOCALAPPDATA')):
            if base:
                guesses.extend([
                    Path(base) / 'BeastNotes' / 'BeastNotes' / 'notes_tree.json',
                    Path(base) / 'BeastNotes' / 'notes_tree.json'
                ])
        start = next((str(p) for p in guesses if p.exists()), r'C:\BeastNotes')
        path, _ = QFileDialog.getOpenFileName(
            self, 'Copy your original notes_tree.json into V4', start, 'JSON files (*.json)'
        )
        if not path:
            return
        try:
            source = Path(path)
            raw = json.loads(source.read_text(encoding='utf-8-sig'))
            roots = legacy_nodes(raw)
            old_ids = {n['id'] for n, _ in walk(roots)}
            existing = {n['id'] for n in all_stored_nodes(self.vault.data)}
            if old_ids & existing:
                raise ValueError('Some of these pages are already in V4. No duplicate import was made.')
            pending = []
            skipped_bin = 0
            used = set(old_ids) | existing
            bin_folder = source.parent / 'bin'
            if bin_folder.is_dir():
                for file in sorted(bin_folder.glob('*.json')):
                    try:
                        record = json.loads(file.read_text(encoding='utf-8-sig'))
                        if not isinstance(record, dict):
                            skipped_bin += 1
                            continue
                        if record.get('restored') or record.get('restored_at'):
                            continue
                        item = record.get('node', record.get('item'))
                        if not isinstance(item, dict):
                            skipped_bin += 1
                            continue
                        converted = legacy_nodes([item])[0]
                        ids = {n['id'] for n, _ in walk([converted])}
                        if ids & used:
                            skipped_bin += 1
                            continue
                        used.update(ids)
                        pending.append({
                            'node': converted,
                            'parent': record.get('parent', record.get('original_parent_id')),
                            'index': int(record.get('index', record.get('original_index', 0))),
                            'at': str(record.get('at', record.get('deleted_at', record.get('timestamp', now())))),
                            'restored': False
                        })
                    except Exception:
                        skipped_bin += 1

            temporary = {
                'schema': 3, 'roots': roots, 'trash': pending,
                'layout': {}, 'prefs': {}, 'scores': []
            }
            validate(temporary)
            imported = list(all_stored_nodes(temporary))
            requested = set().union(*(image_names(n['html']) for n in imported)) if imported else set()
            assets = {}
            for name in requested:
                candidate = source.parent / 'images' / name
                if not candidate.is_file():
                    raise ValueError(
                        'An old image is missing: ' + name +
                        '\nChoose the notes_tree.json from the original data folder, beside its images folder.'
                    )
                assets[name] = candidate
            total = len(list(walk(roots)))
            question = (
                f'Copy {total} active pages and {len(pending)} bin entries into V4?\n\n'
                'Your current V4 pages will stay. The original files will only be read.'
            )
            if skipped_bin:
                question += (
                    f'\n\n{skipped_bin} old bin files were not recognised or overlap existing pages. '
                    'They will remain available in your original app.'
                )
            if QMessageBox.question(self, 'Import a copy', question) != QMessageBox.StandardButton.Yes:
                return
            write_bundle(
                self.vault.data, self.vault.images,
                self.vault.root / 'backups' / ('Before-import-' + file_stamp() + '.zip')
            )
            mapping = {}
            for name, asset in assets.items():
                image = self.editor.read_image(asset)
                new_name = token() + '.png'
                if not image.save(str(self.vault.images / new_name), 'PNG'):
                    raise OSError('Could not copy old image: ' + name)
                mapping[name] = new_name
            for node in imported:
                def replace(match):
                    name = Path(unquote(match.group(1)).lstrip('/')).name
                    return 'beastimage:' + mapping[name]
                node['html'] = MEDIA_RE.sub(replace, node['html'])
                node['text'] = plain(node['html'])
            layout_data = {}
            layout_file = source.parent / 'graph_layout.json'
            if layout_file.exists():
                try:
                    candidate = json.loads(layout_file.read_text(encoding='utf-8-sig'))
                    if isinstance(candidate, dict):
                        candidate = candidate.get('positions', candidate)
                        if isinstance(candidate, dict):
                            layout_data = {
                                k: v for k, v in candidate.items()
                                if k in old_ids and isinstance(v, (list, tuple)) and len(v) == 2
                            }
                except Exception:
                    pass
            def action():
                self.vault.data['roots'].extend(roots)
                self.vault.data['trash'].extend(pending)
                self.vault.data['layout'].update(layout_data)
            if self.modify(action):
                if roots:
                    self.open_page(roots[0]['id'], save=False)
                QMessageBox.information(
                    self, 'Import complete',
                    f'Copied {total} active pages and {len(pending)} bin entries into V4.\n'
                    'Your original BeastNotes files were not changed.'
                )
        except Exception as exc:
            self.error(exc)

    def start_backup(self):
        if self.worker is not None:
            return
        destination = self.vault.backup_dir() / ('BeastNotes-' + file_stamp() + '.zip')
        worker = BackupThread(
            copy.deepcopy(self.vault.data), self.vault.images, destination, self
        )
        self.worker = worker
        worker.done.connect(self.backup_done)
        worker.finished.connect(self.clear_worker)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def clear_worker(self):
        self.worker = None

    def backup_done(self, path, error):
        self.last_backup = time.monotonic()
        if error:
            self.statusBar().showMessage('Backup failed: ' + error)
            if getattr(self, 'manual_backup', False):
                self.error('Notes are saved, but the backup failed:\n\n' + error)
        else:
            self.statusBar().showMessage('Complete backup saved: ' + path, 10000)
        self.manual_backup = False

    def backup_now(self):
        if not self.flush():
            return
        self.manual_backup = True
        if self.worker is None:
            self.start_backup()
        else:
            self.statusBar().showMessage('A complete backup is already being created.', 6000)

    def choose_backup_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, 'Choose where complete backups are saved', str(self.vault.backup_dir())
        )
        if path and self.modify(lambda: self.vault.data['prefs'].__setitem__('backup_dir', path)):
            self.statusBar().showMessage('Backup folder set to ' + path, 8000)

    def backup_browser(self):
        if not self.flush():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Complete backups')
        dialog.resize(780, 490)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('A way back.', 'Big'))
        hint = label('Backups include pages, bin entries, images, graph positions and typing history.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        listing = QListWidget()
        layout.addWidget(listing, 1)

        def refresh():
            listing.clear()
            paths = set()
            for folder in {self.vault.root / 'backups', self.vault.backup_dir()}:
                if folder.is_dir():
                    paths.update(folder.glob('*.zip'))
            for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
                size = path.stat().st_size / (1024 * 1024)
                item = QListWidgetItem(f'{path.name}    ·    {size:.1f} MB')
                item.setData(ROLE, str(path))
                item.setToolTip(str(path))
                listing.addItem(item)

        def restore_path(path):
            answer = QMessageBox.question(
                dialog, 'Restore this complete backup?',
                'This replaces the V4 workspace with the selected backup.\n\n'
                'A complete safety backup of the current workspace will be created first.'
            )
            if answer != QMessageBox.StandardButton.Yes or not self.flush():
                return
            try:
                if self.worker is not None:
                    self.worker.wait()
                install_bundle(self.vault, path, safety=True)
                self.current = None
                self.render_tree()
                self.open_page(self.first_page(), save=False)
                self.game.new_round()
                self.game.refresh_history()
                self.refresh_totals()
                dialog.accept()
                QMessageBox.information(self, 'Restored', 'The complete V4 workspace has been restored.')
            except Exception as exc:
                self.error(exc)

        def selected_restore():
            item = listing.currentItem()
            if item:
                restore_path(item.data(ROLE))

        def browse():
            path, _ = QFileDialog.getOpenFileName(dialog, 'Open a V4 backup', '', 'V4 backups (*.zip)')
            if path:
                restore_path(path)

        layout.addWidget(row(
            button('Back up now', self.backup_now),
            button('Refresh', refresh),
            button('Open backup file...', browse), None,
            button('Restore selected', selected_restore, 'Accent')
        ))
        listing.itemDoubleClicked.connect(lambda item: selected_restore())
        refresh()
        dialog.exec()

    def open_data_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.vault.root)))

    def about(self):
        QMessageBox.information(
            self, APP,
            'BeastNotes V4 / Studio\n\n'
            'Rich notes, paint, quick switching, page history, a visual graph and typing practice.\n\n'
            'V4 data: ' + str(self.vault.root) + '\n\n'
            'Automatic complete backups run during editing at most once every five minutes. '
            'Use Back up now for an immediate copy. Choose another drive or folder for an external copy.'
        )

    def closeEvent(self, event):
        self.vault.data['prefs']['window_size'] = [self.width(), self.height()]
        self.vault.data['prefs']['splitter'] = self.splitter.sizes()
        self.vault.data['prefs']['last'] = self.current
        for graph in self.graphs:
            graph.save_timer.stop()
            graph.save_positions()
        if not self.flush():
            event.ignore()
            return
        if self.worker is not None:
            self.worker.wait()
        event.accept()

def make_icon(path):
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#242031'))
    painter.drawRoundedRect(4, 4, 120, 120, 28, 28)
    painter.setBrush(QColor('#b199ec'))
    painter.drawRoundedRect(28, 27, 72, 78, 9, 9)
    painter.setBrush(QColor('#8060bc'))
    painter.drawRect(28, 37, 12, 58)
    painter.setPen(QPen(QColor('#eee5ff'), 5))
    painter.drawLine(51, 47, 83, 47)
    painter.drawLine(51, 63, 83, 63)
    painter.drawLine(51, 79, 72, 79)
    painter.end()
    return pixmap.save(path, 'ICO')

def self_test(app):
    with tempfile.TemporaryDirectory(prefix='BeastNotesV4-check-') as folder:
        root = Path(folder)
        vault = Vault(root / 'vault')
        window = Window(vault, testing=True)
        ident = window.first_page()
        window.open_page(ident, save=False)
        window.editor.setPlainText('hello world')
        image = QImage(12, 8, QImage.Format.Format_ARGB32)
        image.fill(QColor('#aa88ee'))
        window.editor.add_image(image)
        assert window.flush(), 'Initial save failed'
        assert vault.get(ident)['text'].strip() == 'hello world', 'Image was counted as text'

        reopened = Vault(root / 'vault')
        assert reopened.get(ident)['text'].strip() == 'hello world', 'Text did not persist'
        names = image_names(reopened.get(ident)['html'])
        assert len(names) == 1, 'Image reference did not persist'
        filename = next(iter(names))
        doc = MediaDocument(reopened)
        doc.setHtml(reopened.get(ident)['html'])
        resource = doc.resource(
            QTextDocument.ResourceType.ImageResource,
            QUrl('beastimage:' + filename)
        )
        assert isinstance(resource, QImage) and not resource.isNull(), 'Image reload failed'

        target = new_node('note', 'Linked destination', '<p>Destination content</p>')
        vault.change(lambda: vault.data['roots'].append(target))
        window.editor.moveCursor(QTextCursor.MoveOperation.End)
        window.editor.insertHtml('<a href="beastnote:' + target['id'] + '">destination</a>')
        assert window.flush()
        assert target['id'] in links(vault.get(ident)['html']), 'Page link was not stored'
        vault.change(lambda: vault.get(target['id']).__setitem__('title', 'Renamed destination'))
        assert target['id'] in links(vault.get(ident)['html']), 'Rename broke a link'
        vault.bin_page(target['id'])
        assert vault.get(target['id']) is None, 'Bin did not remove active page'
        restored = vault.restore_page(len(vault.data['trash']) - 1)
        assert restored == target['id'] and vault.get(restored), 'Bin restore changed the page ID'

        vault.bin_page(target['id'])
        archive = root / 'complete.zip'
        write_bundle(vault.data, vault.images, archive)
        snapshot, media = read_bundle(archive)
        assert filename in media, 'Backup omitted images'
        assert any(not r.get('restored') for r in snapshot['trash']), 'Backup omitted bin'
        second = Vault(root / 'restored')
        install_bundle(second, archive)
        assert second.get(ident), 'Backup restore omitted active pages'
        assert (second.images / filename).is_file(), 'Backup restore omitted media'
        assert second.data['trash'], 'Backup restore omitted bin records'

        invalid = copy.deepcopy(vault.data)
        invalid['roots'].append(copy.deepcopy(invalid['roots'][0]))
        rejected = False
        try:
            validate(invalid)
        except ValueError:
            rejected = True
        assert rejected, 'Duplicate IDs were accepted'

        converted = legacy_nodes({'roots': [{
            'id': 'old-book', 'type': 'book', 'title': 'Old book', 'text': 'book content',
            'children': [{
                'id': 'old-note', 'type': 'note', 'title': 'Old note',
                'html': '<p>old text</p>', 'children': []
            }]
        }]})
        assert converted[0]['children'][0]['id'] == 'old-note', 'Legacy import changed IDs'
        assert converted[0]['text'].strip() == 'book content', 'Book content was lost'

        graph = Graph(window)
        graph.nodes[ident].setPos(123, 234)
        graph.save_positions()
        assert vault.data['layout'][ident] == [123, 234], 'Graph positions were not captured'
        graph.save_timer.stop()
        graph.close()
        assert speed(300, 60) == 60, 'Typing score formula failed'

        corrupt = root / 'corrupt'
        corrupt.mkdir()
        raw = b'{"broken":'
        (corrupt / 'vault.json').write_bytes(raw)
        try:
            Vault(corrupt)
        except Exception:
            pass
        else:
            raise AssertionError('Corrupt data was silently replaced')
        assert (corrupt / 'vault.json').read_bytes() == raw, 'Corrupt data was overwritten'

        window.current = None
        window.close()
        app.processEvents()
    from v4_checks import run_checks
    run_checks(app)
    print('BEASTNOTES_SELF_TEST_OK')
    return 0

def configure_app():
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setOrganizationName('BeastNotesV4')
    app.setStyle('Fusion')
    app.setFont(QFont('Segoe UI', 10))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor('#101117'))
    palette.setColor(QPalette.ColorRole.WindowText, QColor('#e7e7f0'))
    palette.setColor(QPalette.ColorRole.Base, QColor('#191b26'))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor('#232536'))
    palette.setColor(QPalette.ColorRole.Text, QColor('#e7e7f0'))
    palette.setColor(QPalette.ColorRole.Button, QColor('#232536'))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor('#e7e7f0'))
    palette.setColor(QPalette.ColorRole.Highlight, QColor('#60458e'))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor('#282b3d'))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor('#f1edff'))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor('#72788f'))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
    QImageReader.setAllocationLimit(128)
    return app

def main():
    app = configure_app()
    if '--self-test' in sys.argv:
        return self_test(app)
    if '--make-icon' in sys.argv:
        index = sys.argv.index('--make-icon')
        return 0 if make_icon(sys.argv[index + 1]) else 1

    DATA.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(DATA / 'workspace.lock'))
    if not lock.tryLock(100):
        QMessageBox.information(None, APP, 'BeastNotes V4 is already running.')
        return 0

    def exception_hook(exc_type, exc, tb):
        details = ''.join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(DATA / 'error.log', 'a', encoding='utf-8') as log:
                log.write('\n' + now() + '\n' + details)
        except Exception:
            pass
        QMessageBox.critical(
            None, APP,
            str(exc) + '\n\nDetails have been written to Data\\error.log.'
        )
    sys.excepthook = exception_hook

    try:
        vault = Vault(DATA)
    except Exception as exc:
        QMessageBox.warning(
            None, 'Workspace recovery',
            'V4 could not open its data:\n\n' + str(exc) +
            '\n\nChoose a complete V4 backup to restore. The existing file will be preserved.'
        )
        path, _ = QFileDialog.getOpenFileName(
            None, 'Restore a complete V4 backup', str(DATA / 'backups'), 'V4 backups (*.zip)'
        )
        if not path:
            return 1
        if (DATA / 'vault.json').exists():
            shutil.copy2(DATA / 'vault.json', DATA / ('vault.unreadable-' + file_stamp() + '.json'))
        vault = Vault(DATA, load=False)
        try:
            install_bundle(vault, path, safety=False)
        except Exception as recovery_error:
            QMessageBox.critical(None, 'Recovery failed', str(recovery_error))
            return 1

    window = Window(vault)
    icon_path = INSTALL_ROOT / 'BeastNotesV4.ico'
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    if sys.platform == 'win32':
        try:
            import ctypes
            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(window.winId()), 20, ctypes.byref(dark), ctypes.sizeof(dark)
            )
        except Exception:
            pass
    if '--smoke-test' in sys.argv:
        QTimer.singleShot(300, window.close)
    result = app.exec()
    lock.unlock()
    return result

if __name__ == '__main__':
    sys.exit(main())