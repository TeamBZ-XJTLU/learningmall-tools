from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence

from lxml import etree

from utils import add_cdata_text, add_simple_text, bool_str


class Question:
    """Base protocol for all question types."""

    def to_xml(self) -> etree._Element:
        raise NotImplementedError


@dataclass
class EmbeddedFile:
    """File embedded inside a questiontext node (used for images)."""

    name: str
    content: bytes
    path: str = "/"
    encoding: str = "base64"

    @classmethod
    def from_path(cls, path: Path) -> "EmbeddedFile":
        path = Path(path)
        return cls(name=path.name, content=path.read_bytes())

    @classmethod
    def from_path_with_name(cls, path: Path, name: str, path_attr: str = "/") -> "EmbeddedFile":
        path = Path(path)
        return cls(name=name, content=path.read_bytes(), path=path_attr)

    @classmethod
    def from_base64(cls, name: str, data_base64: str, path: str = "/") -> "EmbeddedFile":
        return cls(name=name, content=base64.b64decode(data_base64), path=path)

    def to_xml(self) -> etree._Element:
        el = etree.Element("file", name=self.name, path=self.path, encoding=self.encoding)
        el.text = base64.b64encode(self.content).decode("ascii")
        return el


@dataclass
class AnswerOption:
    text: str
    fraction: float
    feedback_html: str = ""
    files: List[EmbeddedFile] = field(default_factory=list)

    def to_xml(self) -> etree._Element:
        el = etree.Element("answer", fraction=str(self.fraction), format="html")
        add_cdata_text(el, self.text)
        for file in self.files:
            el.append(file.to_xml())
        feedback = etree.SubElement(el, "feedback", format="html")
        add_cdata_text(feedback, self.feedback_html)
        return el


@dataclass
class CategoryQuestion(Question):
    """Moodle category question that groups subsequent items."""

    category: str

    def to_xml(self) -> etree._Element:
        q = etree.Element("question", type="category")
        category_el = etree.SubElement(q, "category")
        add_simple_text(category_el, "text", self.category)
        info = etree.SubElement(q, "info", format="html")
        add_simple_text(info, "text", "")
        add_simple_text(q, "idnumber", "")
        return q


@dataclass
class DescriptionQuestion(Question):
    name: str
    question_html: str
    defaultgrade: float = 0.0
    penalty: float = 0.0

    def to_xml(self) -> etree._Element:
        q = etree.Element("question", type="description")
        name_el = etree.SubElement(q, "name")
        add_simple_text(name_el, "text", self.name)
        questiontext = etree.SubElement(q, "questiontext", format="html")
        add_cdata_text(questiontext, self.question_html)
        general_feedback = etree.SubElement(q, "generalfeedback", format="html")
        add_cdata_text(general_feedback, "")
        add_simple_text(q, "defaultgrade", f"{self.defaultgrade:.7f}")
        add_simple_text(q, "penalty", f"{self.penalty:.7f}")
        add_simple_text(q, "hidden", "0")
        add_simple_text(q, "idnumber", "")
        return q


@dataclass
class MultiChoiceQuestion(Question):
    name: str
    question_html: str
    answers: List[AnswerOption]
    general_feedback_html: str = ""
    defaultgrade: float = 1.0
    penalty: float = 0.3333333
    single: bool = True
    shuffleanswers: bool = True
    answernumbering: str = "abc"
    showstandardinstruction: bool = True
    correctfeedback_html: str = "<p>Your answer is correct.</p>"
    partiallycorrectfeedback_html: str = "<p>Your answer is partially correct.</p>"
    incorrectfeedback_html: str = "<p>Your answer is incorrect.</p>"
    files: List[EmbeddedFile] = field(default_factory=list)

    def to_xml(self) -> etree._Element:
        q = etree.Element("question", type="multichoice")

        name_el = etree.SubElement(q, "name")
        add_simple_text(name_el, "text", self.name)

        questiontext = etree.SubElement(q, "questiontext", format="html")
        add_cdata_text(questiontext, self.question_html)
        for file in self.files:
            questiontext.append(file.to_xml())

        general_feedback = etree.SubElement(q, "generalfeedback", format="html")
        add_cdata_text(general_feedback, self.general_feedback_html)

        add_simple_text(q, "defaultgrade", f"{self.defaultgrade:.7f}")
        add_simple_text(q, "penalty", f"{self.penalty:.7f}")
        add_simple_text(q, "hidden", "0")
        add_simple_text(q, "idnumber", "")
        add_simple_text(q, "single", bool_str(self.single))
        add_simple_text(q, "shuffleanswers", bool_str(self.shuffleanswers))
        add_simple_text(q, "answernumbering", self.answernumbering)
        add_simple_text(q, "showstandardinstruction", "1" if self.showstandardinstruction else "0")

        correct_feedback = etree.SubElement(q, "correctfeedback", format="html")
        add_cdata_text(correct_feedback, self.correctfeedback_html)
        partially_correct = etree.SubElement(q, "partiallycorrectfeedback", format="html")
        add_cdata_text(partially_correct, self.partiallycorrectfeedback_html)
        incorrect_feedback = etree.SubElement(q, "incorrectfeedback", format="html")
        add_cdata_text(incorrect_feedback, self.incorrectfeedback_html)

        etree.SubElement(q, "shownumcorrect")

        for answer in self.answers:
            q.append(answer.to_xml())

        return q


@dataclass
class Quiz:
    questions: Sequence[Question]

    def to_etree(self) -> etree._ElementTree:
        root = etree.Element("quiz")
        for question in self.questions:
            root.append(question.to_xml())
        return etree.ElementTree(root)

    def to_xml_bytes(self, pretty_print: bool = True) -> bytes:
        tree = self.to_etree()
        return etree.tostring(
            tree,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=pretty_print,
        )

    def save(self, path: Path | str, pretty_print: bool = True) -> Path:
        out_path = Path(path)
        out_path.write_bytes(self.to_xml_bytes(pretty_print=pretty_print))
        return out_path
