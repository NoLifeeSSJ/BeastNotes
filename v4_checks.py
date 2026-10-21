"""Functional Qt checks run by app.py --self-test, including the Windows installer."""
import json
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest


def run_checks(application):
    from app import (Vault, Window, write_bundle, read_bundle, install_bundle,
                     image_names, new_node, walk, validate)
    from paint import Canvas, PaintDialog, save_png
    from studio import FindDialog
    checks = []
    with tempfile.TemporaryDirectory(prefix='BeastNotesV4-check-') as temp:
        root = Path(temp)
        vault = Vault(root / 'Data')
        window = Window(vault, testing=True)
        window.error = lambda exc: (_ for _ in ()).throw(AssertionError(str(exc)))
        window.show()
        application.processEvents()
        try:
            first = window.current
            window.editor.setPlainText('Find the quiet. Find the flow. find the spark.')
            assert window.flush()
            assert list((vault.root / 'history').rglob('*.json')), 'No recovery snapshot'
            checks.append('page revision saved')
            dialog = FindDialog(window)
            dialog.query.setText('Find')
            dialog.replacement.setText('Keep')
            dialog.case.setChecked(True)
            dialog.replace_all()
            assert window.editor.toPlainText() == 'Keep the quiet. Keep the flow. find the spark.'
            window.editor.undo()
            assert window.editor.toPlainText().startswith('Find the quiet. Find'), 'Replace all was not one undo operation'
            dialog.case.setChecked(False)
            dialog.replacement.setText('Find again')
            dialog.replace_all()
            assert window.editor.toPlainText().count('Find again') == 3, 'Replacement loop or case matching failed'
            dialog.close()
            checks.append('case-sensitive and insensitive replace, single-step undo')
            assert window.flush()
            original = window.current
            window.duplicate_page()
            duplicate = window.current
            assert duplicate != original
            assert vault.get(duplicate)['title'].endswith('(copy)')
            assert vault.get(duplicate)['text'] == vault.get(original)['text']
            window.navigate(-1)
            assert window.current == original
            window.navigate(1)
            assert window.current == duplicate
            checks.append('duplicate and back/forward navigation')
            window.search.setText('spark')
            QTest.qWait(180)
            assert window.results.count() >= 2, 'Debounced search failed'
            window.search.clear()
            checks.append('debounced full-text search')
            for difficulty in ('Easy', 'Moderate', 'Hard'):
                window.game.difficulty.setCurrentText(difficulty)
                window.game.new_round()
                assert window.game.prompt and window.game.prompt.islower()
            window.game.mode.setCurrentIndex(1)
            assert window.game.difficulty.isHidden()
            window.game.mode.setCurrentIndex(0)
            assert not window.game.difficulty.isHidden()
            checks.append('typing difficulty and mode switching')
            canvas = Canvas()
            canvas.resize(1280, 800)
            canvas.show()
            application.processEvents()
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
            QTest.mouseMove(canvas, QPoint(90, 30))
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(90, 30))
            assert canvas.image.pixelColor(60, 30) != QColor('white'), 'Pen did not draw'
            painted = canvas.image.copy()
            canvas.undo()
            assert canvas.image.pixelColor(60, 30) == QColor('white')
            canvas.redo()
            assert canvas.image == painted
            checks.append('paint stroke, undo and redo')
            canvas.tool = 'Eraser'
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(60, 30))
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(60, 30))
            assert canvas.image.pixelColor(60, 30) == QColor('white')
            for tool in ('Line', 'Rectangle', 'Ellipse'):
                canvas.tool = tool
                before = canvas.image.copy()
                QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
                QTest.mouseMove(canvas, QPoint(160, 160))
                QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(160, 160))
                assert canvas.image != before, tool + ' did not draw'
                canvas.undo()
            checks.append('eraser and three shape tools')
            canvas.scale = .5
            canvas.sync_size()
            canvas.tool = 'Pen'
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
            assert canvas.image.pixelColor(200, 200) != QColor('white'), 'Zoom coordinates incorrect'
            checks.append('zoom coordinate mapping')
            draft = root / 'draft.png'
            paint = PaintDialog(window, draft)
            paint.canvas.image = canvas.image.copy()
            paint.canvas.notify()
            assert paint.persist() and draft.exists()
            recovered = PaintDialog(window, draft)
            assert recovered.canvas.image == paint.canvas.image, 'Draft recovery failed'
            recovered.insert()
            assert recovered.inserted_image is not None
            window.editor.add_image(recovered.inserted_image)
            assert window.flush()
            reopened = Vault(vault.root)
            names = image_names(reopened.get(duplicate)['html'])
            assert names, 'Sketch insertion not persisted'
            image = QImage(str(reopened.images / next(iter(names))))
            assert image.pixelColor(200, 200) != QColor('white')
            checks.append('draft recovery and drawing insertion/reload')
            archive = root / 'drawing-backup.zip'
            write_bundle(vault.data, vault.images, archive)
            restored = Vault(root / 'restore')
            install_bundle(restored, archive)
            assert restored.get(duplicate)['html'] == vault.get(duplicate)['html']
            assert (restored.images / next(iter(names))).exists()
            checks.append('paint backup and restore')
            import zipfile
            bad = root / 'bad.zip'
            with zipfile.ZipFile(bad, 'w') as z:
                z.writestr('../escape.png', b'bad')
            try:
                read_bundle(bad)
            except ValueError:
                pass
            else:
                raise AssertionError('Unsafe backup accepted')
            checks.append('unsafe backup paths rejected')
            window.vault.data['prefs']['theme'] = 'Dusk'
            window.apply_display()
            assert '232235' in window.editor.styleSheet()
            window.vault.data['prefs']['theme'] = 'Midnight'
            window.apply_display()
            window.flush()
            checks.append('display preferences')
            # Drive the actual migration handler, including its safety backup.
            from unittest.mock import patch
            source = Vault(root / 'v3-source')
            source.data = json.loads(json.dumps(vault.data))
            source.save()
            for asset in vault.images.iterdir():
                (source.images / asset.name).write_bytes(asset.read_bytes())
            before_source = source.path.read_bytes()
            old_active = window.current
            marker = new_node('note', 'V4 safety backup sentinel', '<p>Keep me</p>')
            vault.change(lambda: vault.data['roots'].append(marker))
            with patch('studio.QFileDialog.getOpenFileName', return_value=(str(source.path), '')), patch('studio.QMessageBox.question', return_value=__import__('PySide6.QtWidgets', fromlist=['QMessageBox']).QMessageBox.StandardButton.Yes):
                window.import_workspace()
            assert source.path.read_bytes() == before_source, 'Import modified V3 source'
            assert vault.get(marker['id']) is None, 'Workspace was not replaced'
            safety = sorted((vault.root / 'backups').glob('Before-import-*.zip'))
            assert safety, 'Import safety backup missing'
            snapshot, _ = read_bundle(safety[-1])
            assert any(n['id'] == marker['id'] for n, _ in walk(snapshot['roots']))
            checks.append('V3 workspace import, original preservation and V4 safety backup')
            before = json.loads(json.dumps(vault.data))
            committed = vault.path.read_bytes()
            with patch('app.atomic_write', side_effect=OSError('simulated full disk')):
                try:
                    vault.change(lambda: vault.data['roots'].append(new_node('note', 'Must roll back')))
                except OSError:
                    pass
                else:
                    raise AssertionError('Disk error was ignored')
            assert vault.data == before and vault.path.read_bytes() == committed
            checks.append('failed write preserves committed disk and in-memory data')
            # Capture a real Qt render for development review; optional and outside user data.
            import os
            screenshot = os.environ.get('BEASTNOTES_TEST_SCREENSHOT')
            if screenshot:
                window.grab().save(screenshot)
            canvas.close()
            paint.timer.stop()
            recovered.timer.stop()
            paint.deleteLater()
            recovered.deleteLater()
        finally:
            window.game.timer.stop()
            window.save_timer.stop()
            window.close()
            window.deleteLater()
            application.processEvents()
    for name in checks:
        print('PASS: ' + name)
    print(f'BEASTNOTES_V4_CHECKS_OK ({len(checks)} groups)')
