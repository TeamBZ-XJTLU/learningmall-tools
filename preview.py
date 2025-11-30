from __future__ import annotations

import mimetypes
import re
from html import escape
from typing import Dict

from lxml import etree

from md2moodle import parse_markdown

PLUGIN_PREFIX = "@@PLUGINFILE@@"
CLOZE_FIELD_PATTERN = re.compile(r"{(\d+)\s*:SAC:[^}]+}")


def _cloze_placeholders_to_inputs(html_text: str) -> str:
    """Render cloze placeholders as visible markers with answers for preview clarity."""
    counter = 0

    def replace(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        # Extract the first answer after "=..."
        raw = match.group(0)
        answer = ""
        parts = raw.split(":SAC:")
        if len(parts) > 1:
            answer_part = parts[1].strip("{}")
            if answer_part.startswith("="):
                answer = answer_part[1:].split("~", 1)[0]
        label = answer or f"#{counter}"
        return f'<span class="cloze-blank">{label}</span>'

    return CLOZE_FIELD_PATTERN.sub(replace, html_text)


def _pluginfile_lookup(question_el: etree._Element) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for file_el in question_el.findall(".//file"):
        name = file_el.get("name") or ""
        if not name:
            continue
        path_attr = file_el.get("path") or "/"
        if not path_attr.startswith("/"):
            path_attr = f"/{path_attr}"
        if not path_attr.endswith("/"):
            path_attr = f"{path_attr}/"
        token = f"{PLUGIN_PREFIX}{path_attr}{name}"
        encoding = (file_el.get("encoding") or "").lower()
        payload = file_el.text or ""
        if encoding == "base64":
            mime, _ = mimetypes.guess_type(name)
            mime = mime or "application/octet-stream"
            lookup[token] = f"data:{mime};base64,{payload}"
        else:
            lookup[token] = payload
    return lookup


def _replace_plugin_tokens(html_text: str, lookup: Dict[str, str]) -> str:
    for token, uri in lookup.items():
        html_text = html_text.replace(token, uri)
    return html_text


def _extract_text(parent: etree._Element, tag: str) -> str:
    """
    Fetch CDATA text from Moodle-style nodes.

    Works for nested <questiontext><text> as well as direct <text> under <answer>.
    """
    node = parent.find(tag)
    if node is None and parent.tag == tag:
        node = parent
    if node is None:
        return ""
    if node.tag == "text":
        return node.text or ""
    text_el = node.find("text")
    if text_el is None:
        return ""
    return text_el.text or ""


def quiz_xml_to_html(xml_bytes: bytes) -> str:
    """Convert quiz XML bytes into a styled HTML preview."""
    root = etree.fromstring(xml_bytes)
    rendered_questions: list[str] = []

    for idx, question_el in enumerate(root.findall("question"), start=1):
        q_type = question_el.get("type")
        if q_type == "category":
            continue

        lookup = _pluginfile_lookup(question_el)
        title = _extract_text(question_el, "name") or f"Question {idx}"
        body_html = _replace_plugin_tokens(_extract_text(question_el, "questiontext"), lookup)
        body_html = _cloze_placeholders_to_inputs(body_html) if q_type == "cloze" else body_html

        if q_type == "description":
            rendered_questions.append(
                f"""
                <div class="card question description">
                  <div class="question-title">{escape(title)}</div>
                  <div class="question-body">{body_html}</div>
                </div>
                """
            )
            continue

        if q_type == "multichoice":
            single_raw = (question_el.findtext("single") or "true").lower()
            is_single = single_raw in {"true", "1", "yes"}
            answers_data = []
            for answer_el in question_el.findall("answer"):
                fraction = float(answer_el.get("fraction", "0") or 0)
                ans_html = _replace_plugin_tokens(_extract_text(answer_el, "text"), lookup)
                answers_data.append({"html": ans_html, "fraction": fraction})
            correct_count = sum(1 for ans in answers_data if ans["fraction"] > 0)
            if correct_count > 1:
                is_single = False
            input_type = "radio" if is_single else "checkbox"
            answers: list[str] = []
            for ans_idx, ans in enumerate(answers_data):
                checked = ans["fraction"] > 0
                icon_class = "checked" if checked else "unchecked"
                if input_type == "radio":
                    icon = "&#9673;" if checked else "&#9711;"  # ◉ / ◯
                else:
                    icon = "&#9745;" if checked else "&#9744;"  # ☑ / ☐
                bullet = f'<span class="choice-icon {icon_class}" aria-hidden="true">{icon}</span>'
                answers.append(
                    f'<div class="answer-row">{bullet}<span class="answer-text">{ans["html"]}</span></div>'
                )
            answers_html = "\n".join(answers)
            rendered_questions.append(
                f"""
                <div class="card question multichoice">
                  <div class="question-title">{escape(title)}</div>
                  <div class="question-body">{body_html}</div>
                  <div class="answers">
                    {answers_html}
                  </div>
                </div>
                """
            )
            continue

        rendered_questions.append(
            f"""
            <div class="card question generic">
              <div class="question-title">{escape(title)}</div>
              <div class="question-body">{body_html}</div>
            </div>
            """
        )

    questions_html = "\n".join(rendered_questions) or "<p>No questions to preview.</p>"
    return f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body {{
            margin: 0;
            padding: 24px;
            background: #f8fafc;
            color: #0f172a;
            font-family: "Inter","Segoe UI",system-ui,-apple-system,sans-serif;
          }}
          .preview {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 14px;
          }}
          .card {{
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px 18px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
          }}
          .question-title {{
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 8px;
          }}
          .question-body p {{
            margin: 0 0 10px;
            line-height: 1.6;
          }}
          .question-body pre,
          .question-body .highlight pre {{
            line-height: 1.8 !important;
          }}
          .answers {{
            list-style: none;
            padding: 0;
            margin: 12px 0 0;
          }}
          .answer-row {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            padding: 10px 12px;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            background: #f8fafc;
            margin-bottom: 8px;
            line-height: 1.6;
            white-space: normal;
          }}
          .choice-icon {{
            display: inline-block;
            margin-right: 8px;
            width: 18px;
            font-size: 15px;
            line-height: 1.2;
            margin-top: 2px;
            vertical-align: top;
          }}
          .choice-icon.checked {{
            color: #2563eb;
          }}
          .choice-icon.unchecked {{
            color: #94a3b8;
          }}
          .answer-text {{
            display: inline-block;
            line-height: 1.5;
            vertical-align: top;
            max-width: calc(100% - 30px);
          }}
          .answer-text p {{
            display: inline;
            margin: 0;
          }}
          .cloze-blank {{
            padding: 6px 8px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            background: #fff;
            min-width: 120px;
            line-height: 1.4;
            display: inline-block;
            vertical-align: middle;
          }}
        </style>
      </head>
      <body>
        <div class="preview">
          {questions_html}
        </div>
      </body>
    </html>
    """


def markdown_to_preview_html(md_text: str) -> str:
    """
    Generate a full HTML preview by converting Markdown → XML → HTML.

    Raises:
        Exception: If Markdown parsing fails.
    """
    quiz = parse_markdown(md_text)
    xml_bytes = quiz.to_xml_bytes()
    return quiz_xml_to_html(xml_bytes)
