from __future__ import annotations

from lxml import etree


def bool_str(value: bool) -> str:
    """Return Moodle-style boolean strings."""
    return "true" if value else "false"


def add_cdata_text(parent: etree._Element, html: str) -> etree._Element:
    """Create a <text> child with CDATA content."""
    text_el = etree.SubElement(parent, "text")
    text_el.text = etree.CDATA(html)
    return text_el


def add_simple_text(parent: etree._Element, tag: str, value: str) -> etree._Element:
    el = etree.SubElement(parent, tag)
    el.text = value
    return el
