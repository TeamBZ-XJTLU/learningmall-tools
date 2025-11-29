#!/usr/bin/env python3
"""
Generate Moodle MCQ XML from a simple Markdown spec.

Markdown format:
- Optional metadata at top:
  - `Category: $course$/top/MyCategory`
  - `Description: Intro text shown above questions`
  - `CodeMode: html` (default) or `CodeMode: image` to choose how fenced code blocks render
- Each question starts with a level-2 heading `## Question title`
- Body text follows until answers.
- Answers are markdown list items using checkboxes:
  - `- [x] Correct answer text`
  - `- [ ] Incorrect answer text`
- Images in the body like `![alt](path/to/image.png)` are embedded and rewritten to `@@PLUGINFILE@@/image.png`.
- Cloze (fill-in-the-blank) questions are supported by adding `Type: Cloze` under the question title
  and writing blanks as `{{answer}}` (or `{{answer1|answer2}}` for multiple fully-correct answers).
  Each blank is exported as a case-sensitive short-answer field worth 1 point.

Example:
Category: $course$/top/Coursework
Description: These are sample MCQs.

## Primary key purpose
What is the primary purpose of a PRIMARY KEY in a relational table?
- [x] Uniquely identify each row
- [ ] Store large text values
- [ ] Improve query caching
- [ ] Control transaction isolation

Usage:
python generate_from_markdown.py examples/questions.md --output examples/generated-from-md.xml
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import textwrap
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Sequence

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter, ImageFormatter
from pygments.formatters.img import FontNotFound
from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models import (
    AnswerOption,
    CategoryQuestion,
    ClozeQuestion,
    DescriptionQuestion,
    EmbeddedFile,
    MultiChoiceQuestion,
    Question,
    Quiz,
)

IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
ANSWER_PATTERN = re.compile(r"^- \[(x|\s)\]\s*(.*)$", re.IGNORECASE)
CODE_BLOCK_PATTERN = re.compile(r"(?m)^[ \t]*```(\w+)?\s*\n(.*?)\n[ \t]*```", re.DOTALL)
CLOZE_PLACEHOLDER_PATTERN = re.compile(r"{{([^{}]+)}}")
CLOZE_FIELD_PATTERN = re.compile(r"{\d+\s*:SAC:[^}]+}")


def markdown_to_html(text: str) -> str:
    return markdown.markdown(text, extensions=["extra"])


def extract_images(md: str) -> tuple[str, List[EmbeddedFile]]:
    files: List[EmbeddedFile] = []

    def replace(match: re.Match) -> str:
        path_str = match.group(1)
        path = Path(path_str)
        files.append(EmbeddedFile.from_path_with_name(path, name=path.name))
        return f"<img src='@@PLUGINFILE@@/{path.name}' />"

    html_like = IMAGE_PATTERN.sub(replace, md)
    return html_like, files


def render_code_to_image(code: str, language: Optional[str], image_name: str) -> EmbeddedFile:
    try:
        lexer = get_lexer_by_name(language) if language else guess_lexer(code)
    except Exception:
        lexer = TextLexer()
    try:
        formatter = ImageFormatter(
            font_name="DejaVu Sans Mono",
            font_size=16,
            line_pad=6,
            image_pad=12,
            line_numbers=True,
            style="friendly",
        )
    except FontNotFound:
        formatter = ImageFormatter(
            font_size=16,
            line_pad=6,
            image_pad=12,
            line_numbers=True,
            style="friendly",
        )
    buffer = BytesIO()
    highlight(code, lexer, formatter, outfile=buffer)
    return EmbeddedFile(name=image_name, content=buffer.getvalue())


def render_code_to_html(code: str, language: Optional[str]) -> str:
    # Protect cloze placeholders so they don't get split by the syntax highlighter.
    placeholders: List[str] = []

    def stash(match: re.Match) -> str:
        placeholders.append(match.group(0))
        return f"__CLOZE_PH_{len(placeholders) - 1}__"

    protected_code = CLOZE_FIELD_PATTERN.sub(stash, code)
    try:
        lexer = get_lexer_by_name(language) if language else guess_lexer(code)
    except Exception:
        lexer = TextLexer()
    formatter = HtmlFormatter(style="friendly", noclasses=True)
    highlighted = highlight(protected_code, lexer, formatter)

    # Replace placeholders back, stripping any spans around them.
    def restore(text: str) -> str:
        for idx, original in enumerate(placeholders):
            token = f"__CLOZE_PH_{idx}__"
            # Remove optional surrounding span wrappers so the placeholder stays intact.
            pattern = re.compile(rf"(?:<span[^>]*>)?{re.escape(token)}(?:</span>)?")
            text = pattern.sub(html.escape(original), text)
        return text

    return restore(highlighted)


def convert_code_blocks(md: str, code_mode: str = "image") -> tuple[str, List[EmbeddedFile]]:
    """
    Replace fenced code blocks either with <img> tags (default) or inline HTML.
    code_mode: "image" or "html".
    """
    files: List[EmbeddedFile] = []

    def replace(match: re.Match) -> str:
        language = (match.group(1) or "").strip() or None
        code = textwrap.dedent(match.group(2))
        if code_mode == "html":
            return render_code_to_html(code, language)
        image_name = f"code-{len(files) + 1}.png"
        files.append(render_code_to_image(code, language, image_name))
        return f"<img src='@@PLUGINFILE@@/{image_name}' />"

    replaced = CODE_BLOCK_PATTERN.sub(replace, md)
    return replaced, files


def process_rich_text(md: str, code_mode: str = "image") -> tuple[str, List[EmbeddedFile]]:
    """Render markdown segment with code blocks and image embedding."""
    md_with_code, code_files = convert_code_blocks(md, code_mode=code_mode)
    md_with_images, image_files = extract_images(md_with_code)
    html = markdown_to_html(md_with_images)
    return html, code_files + image_files


def convert_cloze_placeholders(md: str) -> tuple[str, int]:
    """Replace {{answer}} tokens with Moodle cloze short-answer fields."""
    count = 0

    def replace(match: re.Match) -> str:
        nonlocal count
        count += 1
        raw = match.group(1).strip()
        parts = [part.strip() for part in raw.split("|") if part.strip()]
        if not parts:
            raise ValueError("Empty cloze placeholder found.")
        answer = f"={parts[0]}"
        if len(parts) > 1:
            alternates = "".join(f"~%100%{alt}" for alt in parts[1:])
            answer = f"{answer}{alternates}"
        return f"{{1:SAC:{answer}}}"

    replaced = CLOZE_PLACEHOLDER_PATTERN.sub(replace, md)
    return replaced, count


def parse_markdown(md_text: str) -> Quiz:
    lines = md_text.splitlines()
    idx = 0
    category: Optional[str] = None
    description_text: Optional[str] = None
    default_code_mode = "html"
    questions: List[Question] = []

    # metadata
    while idx < len(lines) and lines[idx].strip():
        line = lines[idx].strip()
        if line.lower().startswith("category:"):
            category = line.split(":", 1)[1].strip()
        elif line.lower().startswith("description:"):
            description_text = line.split(":", 1)[1].strip()
        elif line.lower().startswith("codemode:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in {"html", "image"}:
                default_code_mode = value
        else:
            break
        idx += 1
    # skip blank lines after metadata
    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    def flush_question(
        title: str,
        body_lines: List[str],
        answers: List[AnswerOption],
        files: List[EmbeddedFile],
        question_type: str,
        code_mode: str,
    ):
        if not title:
            return
        body_md = "\n".join(body_lines).strip()
        is_cloze = question_type == "cloze"
        if not answers and CLOZE_PLACEHOLDER_PATTERN.search(body_md):
            is_cloze = True

        if is_cloze:
            cloze_md, blanks = convert_cloze_placeholders(body_md)
            html_body, rich_files = process_rich_text(cloze_md, code_mode="html")
            defaultgrade = float(blanks or 1)
            question = ClozeQuestion(
                name=title.strip(),
                question_html=html_body,
                defaultgrade=defaultgrade,
                files=files + rich_files,
            )
            questions.append(question)
        else:
            if not answers:
                raise ValueError(f"Question '{title}' has no answers.")
            html_body, rich_files = process_rich_text(body_md, code_mode=code_mode)
            question = MultiChoiceQuestion(
                name=title.strip(),
                question_html=html_body,
                answers=answers,
                files=files + rich_files,
                single=True,
            )
            questions.append(question)

    current_title = ""
    current_body: List[str] = []
    current_answers: List[AnswerOption] = []
    current_files: List[EmbeddedFile] = []
    current_type: str = "multichoice"
    current_code_mode: str = default_code_mode

    def consume_answer(start_line: str, start_idx: int) -> tuple[str, int]:
        content_lines = [start_line]
        i = start_idx
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if line.startswith("## "):
                break
            if ANSWER_PATTERN.match(stripped):
                break
            if stripped.startswith("```"):
                fence = stripped
                content_lines.append(line)
                i += 1
                while i < len(lines):
                    content_lines.append(lines[i])
                    if lines[i].strip().startswith("```"):
                        i += 1
                        break
                    i += 1
                continue
            if line.startswith("    ") or line.startswith("\t") or stripped == "":
                content_lines.append(line)
                i += 1
                continue
            else:
                break
        return "\n".join(content_lines).strip(), i

    while idx < len(lines):
        line = lines[idx]
        heading = line.startswith("## ")
        answer_match = ANSWER_PATTERN.match(line.strip())

        if heading:
            # save previous question
            if current_title or current_body or current_answers:
                flush_question(
                    current_title,
                    current_body,
                    current_answers,
                    current_files,
                    current_type,
                    current_code_mode,
                )
            current_title = line[3:].strip()
            current_body = []
            current_answers = []
            current_files = []
            current_type = "multichoice"
            current_code_mode = default_code_mode
        elif answer_match and current_type != "cloze":
            mark = answer_match.group(1).lower()
            answer_text, next_idx = consume_answer(answer_match.group(2).strip(), idx + 1)
            combined = answer_match.group(2).strip()
            if answer_text:
                combined = answer_text
            fraction = 100 if mark == "x" else 0
            html_answer, ans_files = process_rich_text(combined, code_mode=current_code_mode)
            current_answers.append(AnswerOption(text=html_answer, fraction=fraction, files=ans_files))
            idx = next_idx
            continue
        else:
            if line.strip().lower().startswith("type:"):
                current_type = line.split(":", 1)[1].strip().lower()
            elif line.strip().lower().startswith("codemode:"):
                value = line.split(":", 1)[1].strip().lower()
                if value in {"html", "image"}:
                    current_code_mode = value
            else:
                current_body.append(line)
        idx += 1

    if current_title or current_body or current_answers:
        flush_question(
            current_title,
            current_body,
            current_answers,
            current_files,
            current_type,
            current_code_mode,
        )

    if not questions:
        raise ValueError("No questions parsed from Markdown.")

    quiz_questions: List = []
    if category:
        quiz_questions.append(CategoryQuestion(category=category))
    if description_text:
        quiz_questions.append(DescriptionQuestion(name="Description", question_html=markdown_to_html(description_text)))
    quiz_questions.extend(questions)

    return Quiz(quiz_questions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Moodle XML from Markdown.")
    parser.add_argument("input", type=Path, help="Markdown file path.")
    parser.add_argument("--output", type=Path, default=Path("examples/generated-from-md.xml"))
    args = parser.parse_args()

    md_text = args.input.read_text()
    quiz = parse_markdown(md_text)
    out_path = quiz.save(args.output)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
