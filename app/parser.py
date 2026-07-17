from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

ATX = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
SETEXT = re.compile(r"^[ \t]*(=+|-+)[ \t]*$")

@dataclass
class ParsedNode:
    heading: str
    level: int
    body: str = ""
    position: int = 0
    identity_path: str = ""
    parent: "ParsedNode | None" = None
    children: list["ParsedNode"] = field(default_factory=list)

    @property
    def full_text(self):
        return f"{'#' * self.level} {self.heading}\n\n{self.body}".strip()

    @property
    def content_hash(self):
        normalized = re.sub(r"\s+", " ", self.full_text).strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "untitled"

def parse_markdown(text: str) -> list[ParsedNode]:
    lines = text.splitlines()
    headings: list[tuple[int, str, int]] = []
    in_fence = False
    fence_char = ""
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if not in_fence:
                in_fence, fence_char = True, marker
            elif marker == fence_char:
                in_fence = False
            i += 1
            continue
        if not in_fence:
            match = ATX.match(lines[i])
            if match:
                headings.append((i, len(match.group(1)), match.group(2).strip()))
                i += 1
                continue
            if i + 1 < len(lines) and lines[i].strip() and SETEXT.match(lines[i + 1]):
                level = 1 if lines[i + 1].strip().startswith("=") else 2
                headings.append((i, level, lines[i].strip()))
                i += 2
                continue
        i += 1
    if in_fence:
        raise ValueError("Unclosed fenced code block; refusing potentially incomplete tree")
    if not headings:
        raise ValueError("Document has no headings; refusing to silently drop content")
    if any(line.strip() for line in lines[:headings[0][0]]):
        raise ValueError("Non-empty content before first heading is ambiguous")

    nodes: list[ParsedNode] = []
    stack: list[ParsedNode] = []
    sibling_counts: dict[tuple[str, str], int] = {}
    for pos, (line_no, level, title) in enumerate(headings):
        body_start = line_no + (2 if line_no + 1 < len(lines) and SETEXT.match(lines[line_no + 1]) else 1)
        body_end = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines)
        body = "\n".join(lines[body_start:body_end]).strip()
        while stack and stack[-1].level >= level:
            stack.pop()
        parent = stack[-1] if stack else None
        parent_path = parent.identity_path if parent else ""
        base = slug(title)
        count_key = (parent_path, base)
        sibling_counts[count_key] = sibling_counts.get(count_key, 0) + 1
        segment = f"{base}[{sibling_counts[count_key]}]"
        path = f"{parent_path}/{segment}" if parent_path else segment
        node = ParsedNode(title, level, body, pos, path, parent)
        if parent:
            parent.children.append(node)
        nodes.append(node)
        stack.append(node)
    return nodes
