"""Navigation, recovery and editing tools for the V4 desktop shell."""
import copy
import json
import re
import time
import uuid
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QTextDocument, QTextCursor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QTextEdit, QCheckBox, QLabel, QMessageBox, QFileDialog,
    QComboBox)


def record_revisions(vault, encoded):
    """Store the previous committed page, before replacing the vault. No source data moves."""
    if not vault.saved:
        return
    old = json.loads(vault.saved)
    def nodes(roots):
        for node in roots:
            yield node
            yield from nodes(node['children'])
    previous = {n['id']: n for n in nodes(old['roots'])}
    current = {n['id']: n for n in nodes(vault.data['roots'])}
    for ident, node in previous.items():
        other = current.get(ident)
        if other is None or all(node.get(k) == other.get(k) for k in ('html', 'title', 'tags')):
            continue
        if time.monotonic() - vault._revision_times.get(ident, -1000) < 60:
            continue
        # Never use imported page IDs as filesystem paths.
        import hashlib
        folder = vault.root / 'history' / hashlib.sha256(ident.encode()).hexdigest()
        folder.mkdir(parents=True, exist_ok=True)
        name = str(time.time_ns()) + '.json'
        from app import atomic_write
        atomic_write(folder / name, json.dumps(node, ensure_ascii=False).encode('utf-8'))
        vault._revision_times[ident] = time.monotonic()
        for stale in sorted(folder.glob('*.json'))[:-30]:
            stale.unlink()


class FindDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle('Find & replace in this page')
        self.resize(480, 220)
        layout = QVBoxLayout(self)
        self.query = QLineEdit()
        self.query.setPlaceholderText('Find text')
        self.replacement = QLineEdit()
        self.replacement.setPlaceholderText('Replace with')
        self.case = QCheckBox('Match case')
        self.info = QLabel('Search wraps to the beginning of the page.')
        for widget in (self.query, self.replacement, self.case, self.info):
            layout.addWidget(widget)
        buttons = QHBoxLayout()
        for title, fn in [('Find next', self.find), ('Replace', self.replace), ('Replace all', self.replace_all)]:
            b = QPushButton(title)
            b.clicked.connect(fn)
            buttons.addWidget(b)
        layout.addLayout(buttons)
        self.query.returnPressed.connect(self.find)

    def flags(self):
        return QTextDocument.FindFlag.FindCaseSensitively if self.case.isChecked() else QTextDocument.FindFlag(0)

    def find(self):
        if not self.query.text():
            return False
        editor = self.main.editor
        if editor.find(self.query.text(), self.flags()):
            self.info.setText('Match selected')
            return True
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        editor.setTextCursor(cursor)
        result = editor.find(self.query.text(), self.flags())
        self.info.setText('Wrapped to first match' if result else 'No matches')
        return result

    def replace(self):
        cursor = self.main.editor.textCursor()
        selected, query = cursor.selectedText(), self.query.text()
        matches = selected == query if self.case.isChecked() else selected.casefold() == query.casefold()
        if query and cursor.hasSelection() and matches:
            cursor.insertText(self.replacement.text())
        self.find()

    def replace_all(self):
        query = self.query.text()
        if not query:
            return
        document = self.main.editor.document()
        edit = QTextCursor(document)
        edit.beginEditBlock()
        cursor = QTextCursor(document)
        count = 0
        while True:
            cursor = document.find(query, cursor, self.flags())
            if cursor.isNull():
                break
            cursor.insertText(self.replacement.text())
            count += 1
        edit.endEditBlock()
        self.info.setText(f'Replaced {count} matches · Ctrl+Z to undo')


class StudioMixin:
    def setup_studio(self):
        self.navigation = []
        self.navigation_index = -1
        self.navigating = False
        self.page_positions = {}
        if self.current:
            self.navigation.append(self.current)
            self.navigation_index = 0
        self.editor.setAcceptRichText(True)
        self.editor.document().setDefaultFont(self.editor.font())
        self.editor.setStyleSheet('QTextEdit#Editor {font-size:15px; padding:18px 28px; selection-background-color:#60458e;}')
        self.search.setPlaceholderText('Search pages or #tags · Ctrl+K')
        for keys, fn in [('Ctrl+K', self.command_palette), ('Ctrl+H', self.find_replace),
                         ('Ctrl+S', self.flush), ('F11', self.toggle_focus),
                         ('Alt+Left', lambda: self.navigate(-1)), ('Alt+Right', lambda: self.navigate(1)),
                         ('Ctrl+Shift+D', self.duplicate_page), ('Ctrl+Shift+P', self.open_paint)]:
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(fn)
            self.shortcuts.append(shortcut)
        menu = self.menuBar().addMenu('Studio')
        for title, fn in [('Quick switch / commands  ·  Ctrl+K', self.command_palette),
                          ('Find & replace  ·  Ctrl+H', self.find_replace),
                          ('Paint  ·  Ctrl+Shift+P', self.open_paint),
                          ('Duplicate page  ·  Ctrl+Shift+D', self.duplicate_page),
                          ('Page history', self.page_history), ('Display settings', self.display_settings),
                          ('Import V3 / V4 workspace', self.import_workspace)]:
            menu.addAction(title, fn)
        self.apply_display()
        self.editor.setFocus()

    def open_page(self, ident, save=True):
        if hasattr(self, 'navigation') and self.current:
            self.page_positions[self.current] = (self.editor.textCursor().position(), self.editor.verticalScrollBar().value())
        self._open_page(ident, save)
        if not hasattr(self, 'navigation') or self.current != ident:
            return
        if not self.navigating and (not self.navigation or self.navigation[self.navigation_index] != ident):
            self.navigation = self.navigation[:self.navigation_index + 1] + [ident]
            self.navigation = self.navigation[-100:]
            self.navigation_index = len(self.navigation) - 1
        if ident in self.page_positions:
            pos, scroll = self.page_positions[ident]
            cursor = self.editor.textCursor()
            cursor.setPosition(min(pos, self.editor.document().characterCount()-1))
            self.editor.setTextCursor(cursor)
            self.editor.verticalScrollBar().setValue(scroll)

    def navigate(self, direction):
        index = self.navigation_index + direction
        from app import walk
        while 0 <= index < len(self.navigation):
            ident = self.navigation[index]
            if self.vault.get(ident):
                self.navigating = True
                try:
                    self.open_page(ident)
                    if self.current == ident:
                        self.navigation_index = index
                finally:
                    self.navigating = False
                return
            index += direction

    def open_paint(self):
        self.open_paint_image()

    def open_paint_image(self, initial=None):
        if not self.current:
            QMessageBox.information(self, 'Choose a page', 'Create or select a page before drawing.')
            return
        if initial is not None and (self.vault.root / 'paint-draft.png').exists():
            QMessageBox.information(self, 'Unfinished drawing', 'Open Paint and finish or insert your existing draft before editing an image.')
            return
        from paint import PaintDialog
        dialog = PaintDialog(self, self.vault.root / 'paint-draft.png', initial)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.inserted_image is not None:
            try:
                self.switch_tab(0)
                self.editor.add_image(dialog.inserted_image)
                if self.flush():
                    (self.vault.root / 'paint-draft.png').unlink(missing_ok=True)
                    self.editor.setFocus()
            except Exception as exc:
                self.error(exc)

    def find_replace(self):
        self.switch_tab(0)
        dialog = FindDialog(self)
        dialog.exec()

    def duplicate_page(self):
        if not self.current or not self.flush():
            return
        from app import walk, now, LINK_RE
        node = copy.deepcopy(self.vault.get(self.current))
        remap = {n['id']: uuid.uuid4().hex for n, _ in walk([node])}
        for item, _ in walk([node]):
            item['id'] = remap[item['id']]
            item['created'] = item['updated'] = now()
            item['html'] = LINK_RE.sub(lambda m: m.group(0).replace(m.group(1), remap.get(m.group(1), m.group(1))), item['html'])
        node['title'] += ' (copy)'
        loc = self.vault.location(self.current)
        siblings, index, parent = loc
        if self.modify(lambda: siblings.insert(index + 1, node)):
            self.open_page(node['id'], save=False)

    def command_palette(self):
        from app import walk, ROLE
        dialog = QDialog(self)
        dialog.setWindowTitle('Quick switch & commands')
        dialog.resize(650, 480)
        layout = QVBoxLayout(dialog)
        query = QLineEdit()
        query.setPlaceholderText('Find a page or type a command…')
        results = QListWidget()
        layout.addWidget(query)
        layout.addWidget(results)
        entries = [('→ New note', lambda: self.create_page('note')),
                   ('→ Paint', self.open_paint), ('→ Page history', self.page_history),
                   ('→ Focus mode', self.toggle_focus), ('→ Back up now', self.backup_now),
                   ('→ Find and replace', self.find_replace), ('→ Display settings', self.display_settings)]
        entries += [(' / '.join(path), lambda ident=n['id']: self.open_page(ident))
                    for n, path in walk(self.vault.data['roots'])]
        def populate():
            results.clear()
            for index, (name, fn) in enumerate(entries):
                if all(t in name.casefold() for t in query.text().casefold().split()):
                    item = QListWidgetItem(name)
                    item.setData(ROLE, index)
                    results.addItem(item)
            if results.count():
                results.setCurrentRow(0)
        def activate(item=None):
            item = item or results.currentItem()
            if item:
                fn = entries[item.data(ROLE)][1]
                dialog.accept()
                QTimer.singleShot(0, fn)
        query.textChanged.connect(populate)
        query.returnPressed.connect(activate)
        results.itemActivated.connect(activate)
        populate()
        dialog.exec()

    def page_history(self):
        if not self.current or not self.flush():
            return
        import hashlib
        from app import ROLE
        ident = self.current
        folder = self.vault.root / 'history' / hashlib.sha256(ident.encode()).hexdigest()
        records = []
        for file in sorted(folder.glob('*.json'), reverse=True):
            try:
                records.append((file, json.loads(file.read_text(encoding='utf-8'))))
            except (ValueError, OSError):
                continue
        dialog = QDialog(self)
        dialog.setWindowTitle('Page history · up to 30 previous versions')
        dialog.resize(800, 620)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Previous saves, at most once a minute. History is local; complete ZIP backups contain the current workspace.'))
        listing = QListWidget()
        preview = QTextEdit()
        preview.setReadOnly(True)
        for file, node in records:
            listing.addItem(node.get('updated', '') + '  ·  ' + node['title'])
        listing.currentRowChanged.connect(lambda index: preview.setHtml(records[index][1]['html']) if index >= 0 else None)
        layout.addWidget(listing, 1)
        layout.addWidget(preview, 2)
        restore = QPushButton('Restore selected version')
        restore.setEnabled(bool(records))
        layout.addWidget(restore)
        if records:
            listing.setCurrentRow(0)
        else:
            preview.setPlainText('No previous versions yet. Edit and save this page to start its history.')
        def apply():
            index = listing.currentRow()
            if index < 0:
                return
            if QMessageBox.question(dialog, 'Restore version', 'Restore this page? A complete safety backup will be made first.') != QMessageBox.StandardButton.Yes:
                return
            from app import write_bundle, file_stamp
            try:
                write_bundle(self.vault.data, self.vault.images, self.vault.root / 'backups' / ('Before-history-' + file_stamp() + '.zip'))
                snapshot = records[index][1]
                if self.modify(lambda: self.vault.get(ident).update({k: copy.deepcopy(snapshot[k]) for k in ('title','html','text','tags')})):
                    self.open_page(ident, save=False)
                    dialog.accept()
            except Exception as exc:
                self.error(exc)
        restore.clicked.connect(apply)
        dialog.exec()

    def import_workspace(self):
        if not self.flush():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Import a copy of a V3 / V4 workspace', r'C:\BeastnotesV3\Data', 'Workspace / backup (vault.json *.zip);;Legacy notes (*.json)')
        if not path:
            return
        from app import validate, read_bundle, write_bundle, file_stamp, all_stored_nodes, image_names, atomic_write
        try:
            source = Path(path)
            if source.suffix.lower() == '.zip':
                data, media = read_bundle(source)
            else:
                data = json.loads(source.read_text(encoding='utf-8-sig'))
                if data.get('schema') != 3:
                    QMessageBox.information(self, 'Legacy import', 'Use More → Import legacy notes to import notes_tree.json.')
                    return
                validate(data)
                requested = set().union(*(image_names(n['html']) for n in all_stored_nodes(data)))
                media = {name: (source.parent / 'images' / name).read_bytes() for name in requested}
            if QMessageBox.question(self, 'Import workspace', 'Replace the V4 workspace with this copy? A complete safety backup of V4 will be created first. The source remains unchanged.') != QMessageBox.StandardButton.Yes:
                return
            write_bundle(self.vault.data, self.vault.images, self.vault.root / 'backups' / ('Before-import-' + file_stamp() + '.zip'))
            # Use the existing collision-safe bundle importer for JSON and ZIP alike.
            import tempfile
            from app import install_bundle
            with tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                images = folder / 'images'
                images.mkdir()
                for name, raw in media.items():
                    atomic_write(images / name, raw)
                bundle = folder / 'import.zip'
                write_bundle(data, images, bundle)
                install_bundle(self.vault, bundle, safety=False)
            self.current = None
            self.render_tree()
            self.open_page(self.vault.data['prefs'].get('last') or self.first_page(), save=False)
            self.game.refresh_history()
            self.apply_display()
            self.statusBar().showMessage('Workspace imported. Original files unchanged.', 10000)
        except Exception as exc:
            self.error(exc)

    def display_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Make yourself at home')
        layout = QVBoxLayout(dialog)
        theme = QComboBox()
        theme.addItems(['Midnight', 'Dusk'])
        theme.setCurrentText(self.vault.data['prefs'].get('theme', 'Midnight'))
        size = QComboBox()
        size.addItems(['14', '16', '18', '20', '24'])
        size.setCurrentText(str(self.vault.data['prefs'].get('editor_size', 16)))
        for widget in (QLabel('Appearance'), theme, QLabel('Writing size (pixels)'), size):
            layout.addWidget(widget)
        save = QPushButton('Apply')
        layout.addWidget(save)
        def apply():
            self.vault.data['prefs'].update(theme=theme.currentText(), editor_size=int(size.currentText()))
            self.apply_display()
            self.schedule_save()
            dialog.accept()
        save.clicked.connect(apply)
        dialog.exec()

    def apply_display(self):
        prefs = self.vault.data['prefs']
        dusk = prefs.get('theme') == 'Dusk'
        self.setStyleSheet('\nQMainWindow, QWidget#Header, QWidget#Side, QWidget#Details {background:#232235; color:#eeeafa;}\nQLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QListWidget, QTreeWidget {background:#29283d;color:#eeeafa;selection-color:#fff;}\nQLineEdit#Title {background:transparent;color:#eeeafa;}\nQPushButton {background:#35314b;color:#eeeafa;border-color:#5a4d75;}\nQPushButton:checked {background:#53436f;}\n' if dusk else '')
        bg = '#232235' if dusk else '#101117'
        self.editor.setStyleSheet(f'QTextEdit#Editor {{font-size:{prefs.get("editor_size",16)}px; color:#e4e4ee; background:{bg};padding:18px 28px;}}')
