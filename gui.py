#!/usr/bin/env python3
"""
Simple PySide6 GUI for authoring Learning Mall Markdown quizzes.

Layout:
- Left: Markdown source editor.
- Middle: Rendered preview (Markdown → HTML).
- Right: Question map with controls to move/delete/add between.
- Bottom: Quick action buttons to append new items.

Usage:
    python scripts/gui_editor.py path/to/questions.md

PySide6 is provided as an optional dependency via the `gui` extra.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import List, Tuple

import md2moodle
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView

from md2moodle import parse_markdown
from models import CategoryQuestion, ClozeQuestion, DescriptionQuestion, MultiChoiceQuestion
from preview import markdown_to_preview_html


ACCENT = "#2563eb"
SURFACE = "#f8fafc"
CANVAS = "#ffffff"
TEXT_PRIMARY = "#0f172a"


def render_markdown(md_text: str) -> str:
    """Convert markdown to HTML for preview."""
    html = md2moodle.md2moodle(
        md_text,
        extensions=["extra", "codehilite"],
        extension_configs={
            "codehilite": {
                "noclasses": True,
                "linenums": False,
                "guess_lang": False,
                "pygments_style": "friendly",
            }
        },
    )
    style = """
    <style>
    body { background: #f7f9fb; color: #0f172a; font-family: 'Inter','Segoe UI',sans-serif; line-height: 1.6; padding: 16px; margin: 0; }
    h1, h2, h3 { color: #0f172a; font-weight: 700; margin-top: 24px; }
    p { margin: 0 0 12px; color: #1f2937; }
    a { color: #1d4ed8; }
    ul, ol { padding-left: 20px; }
    pre { background: #f3f4f6; color: #111827; padding: 12px; border: 1px solid #e5e7eb; border-radius: 10px; }
    code { font-family: 'JetBrains Mono','Fira Code',monospace; }
    blockquote { border-left: 3px solid #2563eb; padding-left: 12px; color: #374151; }
    hr { border: none; border-top: 1px solid #e5e7eb; margin: 16px 0; }
    </style>
    """
    return style + html


def parse_question_map(md_text: str) -> List[Tuple[str, int]]:
    """Return list of (title, line_number) for level-2 headings."""
    entries: List[Tuple[str, int]] = []
    for idx, line in enumerate(md_text.splitlines()):
        if line.startswith("## "):
            entries.append((line[3:].strip() or f"Question {len(entries)+1}", idx))
    return entries


class QuizEditor(QtWidgets.QWidget):
    def __init__(self, path: Path | None = None):
        super().__init__()
        self.path = path
        self._pending_preview_row: int = -1
        self.setWindowTitle("LearningMall Markdown Editor")
        self.setObjectName("AppWindow")
        self.resize(1400, 900)
        self.apply_modern_theme()
        self._build_ui()
        if path and path.exists():
            self.load_file(path)
        self.update_preview()
        self.update_map()
        self.update_status_bar()

    def apply_modern_theme(self) -> None:
        QtWidgets.QApplication.setStyle("Fusion")
        base_font = QtGui.QFont("Inter", 10)
        base_font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        self.setFont(base_font)

        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(CANVAS))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#f7f9fb"))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#eef2f7"))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(TEXT_PRIMARY))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#e5e7eb"))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(TEXT_PRIMARY))
        QtWidgets.QApplication.setPalette(palette)

        self.setStyleSheet(
            f"""
            #AppWindow {{
                background-color: {CANVAS};
            }}
            QFrame#Hero {{
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                color: {TEXT_PRIMARY};
            }}
            QFrame#Toolbar {{
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
            }}
            QFrame#Card {{
                background-color: {SURFACE};
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding-top: 4px;
            }}
            QLabel#CardTitle {{
                color: {TEXT_PRIMARY};
                font-weight: 600;
                font-size: 12pt;
            }}
            QLabel#CardHint {{
                color: #6b7280;
                margin-bottom: 4px;
            }}
            QPlainTextEdit, QTextBrowser {{
                background-color: #ffffff;
                color: {TEXT_PRIMARY};
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 10px;
                selection-background-color: {ACCENT};
                selection-color: #0b1220;
            }}
            QListWidget {{
                background-color: #ffffff;
                color: {TEXT_PRIMARY};
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 6px;
            }}
            QListWidget::item {{
                border-radius: 8px;
                padding: 8px;
            }}
            QListWidget::item:selected {{
                background: #dbeafe;
                color: #0b1220;
            }}
            QPushButton {{
                background-color: #ffffff;
                color: {TEXT_PRIMARY};
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 600;
            }}
            QPushButton#PrimaryButton {{
                background-color: {ACCENT};
                border-color: {ACCENT};
                color: #f8fafc;
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
            }}
            QPushButton:pressed {{
                background-color: #1d4ed8;
            }}
            QSplitter::handle {{
                background: #e5e7eb;
                width: 10px;
                margin-top: 6px;
                margin-bottom: 6px;
                border-radius: 4px;
            }}
            QFrame#StatusBar {{
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 8px 12px;
            }}
            QLabel#StatusLabel {{
                color: #1f2937;
                font-weight: 600;
            }}
            """
        )

    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        hero = QtWidgets.QFrame()
        hero.setObjectName("Hero")
        hero.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        hero_layout = QtWidgets.QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(6)
        title = QtWidgets.QLabel("Learning Mall Quiz Studio")
        title_font = QtGui.QFont(self.font())
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        hero_layout.addWidget(title)
        main_layout.addWidget(hero)

        toolbar = QtWidgets.QFrame()
        toolbar.setObjectName("Toolbar")
        toolbar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        actions_layout = QtWidgets.QVBoxLayout(toolbar)
        actions_layout.setContentsMargins(12, 12, 12, 12)
        actions_layout.setSpacing(10)
        main_layout.addWidget(toolbar)

        row_primary = QtWidgets.QHBoxLayout()
        row_primary.setSpacing(8)
        for label, slot, primary in [
            ("New", self.new_document, True),
            ("Load Template", self.load_template, True),
            ("Validate", self.validate_document, False),
            ("Save", self.save_file, True),
            ("Export Preview HTML", self.export_preview_html, False),
            ("Export Moodle XML", self.export_moodle_xml, False),
        ]:
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(slot)
            self._style_button(btn, primary=primary)
            row_primary.addWidget(btn)
        row_primary.addStretch()

        row_secondary = QtWidgets.QHBoxLayout()
        row_secondary.setSpacing(8)
        for label, template in [
            ("Add Description", "description"),
            ("Add MCQ", "mcq"),
            ("Add Cloze", "cloze"),
        ]:
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(lambda _=None, tmpl=template: self.append_template(tmpl))
            self._style_button(btn)
            row_secondary.addWidget(btn)
        row_secondary.addStretch()

        actions_layout.addLayout(row_primary)
        actions_layout.addLayout(row_secondary)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left: editor
        self.editor = QtWidgets.QPlainTextEdit()
        self.editor.setPlaceholderText("Write quiz markdown here...")
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.setWordWrapMode(QtGui.QTextOption.NoWrap)
        self.editor.setFont(QtGui.QFont("JetBrains Mono", 10))
        self.editor_card = self._wrap_card("Markdown Editor", "Source with live preview")
        editor_layout = self.editor_card.layout()
        self.editor.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        editor_layout.addWidget(self.editor)
        editor_layout.setStretch(editor_layout.count() - 1, 1)
        splitter.addWidget(self.editor_card)

        # Middle: preview (full HTML via WebEngine)
        self.preview = QWebEngineView()
        self.preview_card = self._wrap_card("Preview", "Rendered Markdown → XML → HTML")
        preview_layout = self.preview_card.layout()
        self.preview.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        preview_layout.addWidget(self.preview)
        preview_layout.setStretch(preview_layout.count() - 1, 1)
        splitter.addWidget(self.preview_card)

        # Right: question map and controls
        right_container = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_container)
        self.map_list = QtWidgets.QListWidget()
        self.map_list.currentRowChanged.connect(self.on_map_selection)
        self.map_list.setSpacing(4)
        self.map_list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        right_layout.addWidget(self.map_list)

        btn_move_up = QtWidgets.QPushButton("Move Up")
        btn_move_up.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowUp))
        btn_move_up.clicked.connect(lambda: self.move_question(-1))
        btn_move_down = QtWidgets.QPushButton("Move Down")
        btn_move_down.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowDown))
        btn_move_down.clicked.connect(lambda: self.move_question(1))
        btn_delete = QtWidgets.QPushButton("Delete")
        btn_delete.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon))
        btn_delete.clicked.connect(self.delete_question)

        controls_row = QtWidgets.QHBoxLayout()
        controls_row.setSpacing(8)
        for btn in (btn_move_up, btn_move_down, btn_delete):
            self._style_button(btn)
            controls_row.addWidget(btn)
        controls_row.addStretch()
        right_layout.addLayout(controls_row)
        right_layout.addStretch()
        right_layout.setContentsMargins(0, 0, 0, 0)

        map_card = self._wrap_card("Question Map", "Jump between sections and reorder quickly")
        map_layout = map_card.layout()
        right_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        map_layout.addWidget(right_container)
        map_layout.setStretch(map_layout.count() - 1, 1)
        splitter.addWidget(map_card)
        splitter.setSizes([4, 3, 2])
        splitter.setHandleWidth(10)
        splitter.setChildrenCollapsible(False)
        main_layout.setStretch(0, 0)
        main_layout.setStretch(1, 0)
        main_layout.setStretch(2, 1)

        # Status bar
        self.status_bar = QtWidgets.QFrame()
        self.status_bar.setObjectName("StatusBar")
        status_layout = QtWidgets.QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(10, 8, 10, 8)
        status_layout.setSpacing(12)
        self.status_label = QtWidgets.QLabel("Questions: MCQ 0 | Cloze 0 | Description 0 | Total 0")
        self.status_label.setObjectName("StatusLabel")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addWidget(self.status_bar)

    def load_file(self, path: Path) -> None:
        self.editor.setPlainText(path.read_text())
        self.path = path
        self.highlight_section(self.map_list.currentRow())

    def save_file(self) -> None:
        target = self.path
        if not target:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save Markdown File",
                str(self.path.parent if self.path else Path.cwd()),
                "Markdown Files (*.md *.markdown *.txt);;All Files (*)",
            )
            if not file_path:
                return
            target = Path(file_path)
            self.path = target
        try:
            target.write_text(self.editor.toPlainText())
        except Exception as exc:  # pragma: no cover - UI path
            QtWidgets.QMessageBox.warning(self, "Save failed", f"Could not save file:\n{exc}")
            return
        QtWidgets.QMessageBox.information(self, "Saved", f"Saved to {target}")

    def validate_document(self) -> None:
        try:
            parse_markdown(self.editor.toPlainText())
        except Exception as exc:  # pragma: no cover - UI path
            QtWidgets.QMessageBox.warning(self, "Validation failed", str(exc))
            return
        QtWidgets.QMessageBox.information(self, "Validation passed", "Markdown looks valid.")

    def export_preview_html(self) -> None:
        target_path = self._pick_save_path(
            title="Export Preview HTML",
            filter_str="HTML Files (*.html);;All Files (*)",
            default_suffix=".html",
            suggested_name="preview.html",
        )
        if not target_path:
            return
        try:
            html_content = markdown_to_preview_html(self.editor.toPlainText())
            target_path.write_text(html_content, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - UI path
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not export preview:\n{exc}")
            return
        QtWidgets.QMessageBox.information(self, "Exported", f"Preview saved to {target_path}")

    def export_moodle_xml(self) -> None:
        target_path = self._pick_save_path(
            title="Export Moodle XML",
            filter_str="XML Files (*.xml);;All Files (*)",
            default_suffix=".xml",
            suggested_name="quiz.xml",
        )
        if not target_path:
            return
        try:
            quiz = parse_markdown(self.editor.toPlainText())
            quiz.save(target_path)
        except Exception as exc:  # pragma: no cover - UI path
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not export XML:\n{exc}")
            return
        QtWidgets.QMessageBox.information(self, "Exported", f"Moodle XML saved to {target_path}")

    def on_text_changed(self) -> None:
        self.update_preview()
        self.update_map()
        self.update_status_bar()

    def update_preview(self) -> None:
        try:
            html_content = markdown_to_preview_html(self.editor.toPlainText())
        except Exception as exc:  # pragma: no cover - UI path
            error = html.escape(str(exc))
            html_content = (
                "<html><body>"
                "<div style='background:#fef2f2; color:#b91c1c; border:1px solid #fecdd3; "
                "padding:12px; border-radius:10px;'>"
                f"Preview unavailable: {error}"
                "</div></body></html>"
            )
        row = self.map_list.currentRow()
        self._pending_preview_row = row

        def after_load(_ok: bool) -> None:
            try:
                self.preview.loadFinished.disconnect(after_load)
            except Exception:
                pass
            self.highlight_preview_card(self._pending_preview_row)

        try:
            self.preview.loadFinished.connect(after_load)
        except Exception:
            pass

        self.preview.setHtml(html_content)

    def update_map(self) -> None:
        current = self.map_list.currentRow()
        new_row = -1
        self.map_list.blockSignals(True)
        self.map_list.clear()
        for title, _ in parse_question_map(self.editor.toPlainText()):
            self.map_list.addItem(title)
        if current >= 0 and self.map_list.count():
            new_row = min(current, self.map_list.count() - 1)
            self.map_list.setCurrentRow(new_row)
        self.map_list.blockSignals(False)
        self.highlight_section(new_row)

    def update_status_bar(self) -> None:
        """Refresh counts of question types in the status bar."""
        md_text = self.editor.toPlainText()
        try:
            quiz = parse_markdown(md_text)
        except Exception:
            self.status_label.setText("Counts unavailable (fix Markdown to see totals)")
            return

        mcq = sum(isinstance(q, MultiChoiceQuestion) for q in quiz.questions)
        cloze = sum(isinstance(q, ClozeQuestion) for q in quiz.questions)
        desc = sum(isinstance(q, DescriptionQuestion) for q in quiz.questions)
        total = sum(1 for q in quiz.questions if not isinstance(q, CategoryQuestion))

        self.status_label.setText(
            f"Questions: MCQ {mcq} | Cloze {cloze} | Description {desc} | Total {total}"
        )

    def on_map_selection(self, row: int) -> None:
        if row < 0:
            self.editor.setExtraSelections([])
            return
        entries = parse_question_map(self.editor.toPlainText())
        if row >= len(entries):
            return
        _, line_no = entries[row]
        cursor = self.editor.textCursor()
        block = self.editor.document().findBlockByNumber(line_no)
        cursor.setPosition(block.position())
        self.editor.setTextCursor(cursor)
        self.highlight_section(row)

    def move_question(self, delta: int) -> None:
        entries = parse_question_map(self.editor.toPlainText())
        idx = self.map_list.currentRow()
        if idx < 0 or idx >= len(entries):
            return
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(entries):
            return
        md_lines = self.editor.toPlainText().splitlines()

        def block_bounds(i: int) -> Tuple[int, int]:
            start = entries[i][1]
            end = entries[i + 1][1] if i + 1 < len(entries) else len(md_lines)
            return start, end

        start_a, end_a = block_bounds(idx)
        start_b, end_b = block_bounds(new_idx)

        block_a = md_lines[start_a:end_a]
        block_b = md_lines[start_b:end_b]

        if delta > 0:
            new_lines = md_lines[:start_a] + block_b + block_a + md_lines[end_b:]
        else:
            new_lines = md_lines[:start_b] + block_a + block_b + md_lines[end_a:]

        self.editor.setPlainText("\n".join(new_lines))
        self.update_map()
        self.map_list.setCurrentRow(new_idx)
        self.highlight_section(new_idx)

    def delete_question(self) -> None:
        entries = parse_question_map(self.editor.toPlainText())
        idx = self.map_list.currentRow()
        if idx < 0 or idx >= len(entries):
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete question",
            "Delete the selected question?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        md_lines = self.editor.toPlainText().splitlines()
        start = entries[idx][1]
        end = entries[idx + 1][1] if idx + 1 < len(entries) else len(md_lines)
        new_lines = md_lines[:start] + md_lines[end:]
        self.editor.setPlainText("\n".join(new_lines))
        self.update_map()
        self.highlight_section(self.map_list.currentRow())

    def new_document(self) -> None:
        self.editor.clear()
        self.preview.setHtml("")
        self.update_map()

    def load_template(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Markdown Template",
            str(Path.cwd()),
            "Markdown Files (*.md *.markdown *.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            text = Path(file_path).read_text()
        except Exception as exc:  # pragma: no cover - UI path
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load file:\n{exc}")
            return
        self.editor.setPlainText(text)
        self.path = Path(file_path)
        self.update_map()
        if self.map_list.count():
            self.map_list.setCurrentRow(self.map_list.count() - 1)

    def insert_question(self, template: str, above: bool = False) -> None:
        entries = parse_question_map(self.editor.toPlainText())
        md_lines = self.editor.toPlainText().splitlines()
        idx = self.map_list.currentRow()
        insert_at = len(md_lines)
        if above and idx >= 0 and idx < len(entries):
            insert_at = entries[idx][1]
        snippet = self.build_template(template)
        new_lines = md_lines[:insert_at] + snippet.splitlines() + [""] + md_lines[insert_at:]
        self.editor.setPlainText("\n".join(new_lines))
        self.update_map()
        if self.map_list.count():
            self.map_list.setCurrentRow(min(self.map_list.count() - 1, idx + (1 if above else 0)))
            self.highlight_section(self.map_list.currentRow())

    def append_template(self, template: str) -> None:
        md = self.editor.toPlainText().rstrip()
        snippet = self.build_template(template)
        new_md = f"{md}\n\n{snippet}\n"
        self.editor.setPlainText(new_md)
        self.update_map()
        if self.map_list.count():
            self.map_list.setCurrentRow(self.map_list.count() - 1)
            self.highlight_section(self.map_list.currentRow())

    @staticmethod
    def build_template(kind: str) -> str:
        if kind == "description":
            return "\n".join(
                [
                    "## Description",
                    "Type: Description",
                    "Type your description here.",
                ]
            )
        if kind == "cloze":
            return "\n".join(
                [
                    "## Fill in the blank",
                    "Type: Cloze",
                    "Complete the sentence: {{answer}} goes here.",
                ]
            )
        # default MCQ
        return "\n".join(
            [
                "## New MCQ",
                "Question text here.",
                "- [x] Correct answer",
                "- [ ] Incorrect answer",
            ]
        )

    def _wrap_card(self, title: str, hint: str | None = None) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("Card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        label = QtWidgets.QLabel(title)
        label.setObjectName("CardTitle")
        layout.addWidget(label, alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        if hint:
            hint_label = QtWidgets.QLabel(hint)
            hint_label.setObjectName("CardHint")
            layout.addWidget(hint_label, alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        return card

    def _style_button(self, btn: QtWidgets.QPushButton, primary: bool = False) -> None:
        if primary:
            btn.setObjectName("PrimaryButton")
        btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

    def _pick_save_path(
        self, title: str, filter_str: str, default_suffix: str, suggested_name: str
    ) -> Path | None:
        base_dir = self.path.parent if self.path else Path.cwd()
        suggested = suggested_name
        if self.path:
            suggested = self.path.with_suffix(default_suffix).name
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            title,
            str(base_dir / suggested),
            filter_str,
        )
        if not file_path:
            return None
        path = Path(file_path)
        if not path.suffix:
            path = path.with_suffix(default_suffix)
        return path

    def highlight_section(self, row: int) -> None:
        """Highlight the selected question section in the editor."""
        entries = parse_question_map(self.editor.toPlainText())
        selections: list[QtWidgets.QTextEdit.ExtraSelection] = []
        if row >= 0 and row < len(entries):
            doc = self.editor.document()
            start_line = entries[row][1]
            end_line = entries[row + 1][1] if row + 1 < len(entries) else doc.blockCount()
            start_block = doc.findBlockByNumber(start_line)
            end_block = doc.findBlockByNumber(end_line)
            start_pos = start_block.position()
            end_pos = end_block.position() if end_block.isValid() else doc.characterCount() - 1

            cursor = self.editor.textCursor()
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QtGui.QTextCursor.KeepAnchor)

            highlight = QtWidgets.QTextEdit.ExtraSelection()
            color = QtGui.QColor("#dbeafe")
            color.setAlpha(120)
            highlight.format.setBackground(color)
            highlight.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            highlight.cursor = cursor
            selections.append(highlight)

        self.editor.setExtraSelections(selections)
        self.highlight_preview_card(row)

    def highlight_preview_card(self, row: int) -> None:
        """Visually highlight the preview card that matches the selected question."""
        if row < 0:
            return
        js = f"""
        (() => {{
            const head = document.head || document.documentElement;
            if (!document.getElementById('lm-preview-highlight-style')) {{
                const style = document.createElement('style');
                style.id = 'lm-preview-highlight-style';
                style.textContent = `
                  .card.question {{
                    transition: box-shadow 150ms ease, border-color 150ms ease;
                  }}
                  .card.question.lm-selected {{
                    border-color: {ACCENT};
                    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18);
                  }}
                  .card.question.lm-selected {{
                    border-color: {ACCENT};
                    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18);
                  }}
                  .card.question.lm-selected:focus-within {{
                    outline: none;
                  }}
                `;
                head.appendChild(style);
            }}
            const cards = Array.from(document.querySelectorAll('.card.question'));
            cards.forEach((c, idx) => c.classList.toggle('lm-selected', idx === {row}));
            const target = cards[{row}];
            if (target) {{
              target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }})();
        """
        try:
            self.preview.page().runJavaScript(js)
        except Exception:
            pass


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    editor = QuizEditor(path)
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
