"""Validation and sanitisation for model-generated SVG samples."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET


_SVG_RE = re.compile(r"<svg\b[^>]*>.*?</svg\s*>", re.IGNORECASE | re.DOTALL)
_BAD_ELEMENTS = {"script", "foreignobject", "iframe", "object", "embed", "audio", "video"}
_MAX_BYTES = 200 * 1024
ET.register_namespace("", "http://www.w3.org/2000/svg")


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1].lower()


def _bad_style(value: str) -> bool:
    lower = value.lower()
    if "@import" in lower or "javascript:" in lower or "data:" in lower:
        return True
    for url in re.findall(r"url\s*\(\s*(['\"]?)(.*?)\1\s*\)", value, re.IGNORECASE):
        target = url[1].strip()
        if not target.startswith("#"):
            return True
    return False


def sanitize_svg(reply: str) -> tuple[str | None, bool]:
    matches = list(_SVG_RE.finditer(reply))
    if not matches:
        return None, False
    text = matches[-1].group(0)
    if len(text.encode("utf-8")) > _MAX_BYTES:
        return None, False
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", reply, re.IGNORECASE):
        return None, False
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, False
    if _local_name(root.tag) != "svg":
        return None, False
    namespace = "http://www.w3.org/2000/svg"
    if root.tag.startswith("{") and root.tag.split("}", 1)[0][1:] != namespace:
        return None, False
    if not root.tag.startswith("{"):
        root.set("xmlns", namespace)
    for element in root.iter():
        tag = _local_name(element.tag)
        if tag in _BAD_ELEMENTS or tag == "style" and _bad_style(element.text or ""):
            return None, False
        if tag.startswith("animate") or tag == "set":
            for attr in element.attrib:
                if _local_name(attr) == "attributename" and element.attrib[attr].lower() in {"href", "xlink:href"}:
                    return None, False
                if attr.lower().startswith("on"):
                    return None, False
        for attr, value in element.attrib.items():
            attr_name = _local_name(attr)
            if attr_name.startswith("on"):
                return None, False
            if attr_name in {"href", "xlink:href"} and not value.startswith("#"):
                return None, False
            if attr_name == "style" and _bad_style(value):
                return None, False
    serialised = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    if len(serialised.encode("utf-8")) > _MAX_BYTES:
        return None, False
    return serialised, True
