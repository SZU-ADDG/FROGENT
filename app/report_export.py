"""Deterministic Markdown, PDF, and Word exports for persisted chat reports."""

import html
import json
import os
import shutil
import subprocess
from io import BytesIO
from pathlib import Path


EXPORTS = {
    "md": ("text/markdown; charset=utf-8", "md"),
    "pdf": ("application/pdf", "pdf"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
}


def export_report(chat, format_name, script_root):
    if format_name not in EXPORTS:
        raise ValueError("report format must be md, pdf, or docx")
    payload = _payload(chat)
    if format_name == "md":
        return markdown_report(payload).encode("utf-8")
    if format_name == "pdf":
        return pdf_report(payload)
    return docx_report(payload, Path(script_root) / "scripts" / "export_chat_report.js")


def markdown_report(payload):
    lines = [f"# {payload['title']}", "", "FROGENT Agent report", ""]
    lines.extend([
        f"- Conversation: `{payload['id']}`",
        f"- Created: {payload['created_at']}",
        f"- Updated: {payload['updated_at']}",
        "",
        "## Conversation",
        "",
    ])
    for item in payload["messages"]:
        lines.extend([f"### {item['role']}", "", item["content"] or "(empty)", ""])
        if item["attachments"]:
            lines.extend(["Attachments:", *[f"- `{name}`" for name in item["attachments"]], ""])
    if payload["structures"]:
        lines.extend(["## Molecular structures", ""])
        lines.extend(f"- `{item['filename']}` ({item['format'] or 'unknown'})" for item in payload["structures"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def pdf_report(payload):
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    font_name = "Helvetica"
    candidates = [
        os.environ.get("FROGENT_REPORT_FONT"),
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in filter(None, candidates):
        try:
            pdfmetrics.registerFont(TTFont("FrogentUnicode", candidate))
            font_name = "FrogentUnicode"
            break
        except Exception:
            continue
    styles = getSampleStyleSheet()
    base = ParagraphStyle("FrogentBody", parent=styles["BodyText"], fontName=font_name,
                          fontSize=10, leading=15, spaceAfter=6)
    title = ParagraphStyle("FrogentTitle", parent=base, fontSize=18, leading=23,
                           alignment=TA_CENTER, spaceAfter=12)
    heading = ParagraphStyle("FrogentHeading", parent=base, fontSize=13, leading=18,
                             spaceBefore=9, spaceAfter=5)
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                                 topMargin=18 * mm, bottomMargin=18 * mm,
                                 title=payload["title"], author="FROGENT Agent")
    story = [Paragraph(html.escape(payload["title"]), title),
             Paragraph("FROGENT Agent report", base),
             Paragraph(html.escape(f"Conversation: {payload['id']}"), base),
             Paragraph(html.escape(f"Created: {payload['created_at']}"), base),
             Paragraph(html.escape(f"Updated: {payload['updated_at']}"), base),
             Spacer(1, 8), Paragraph("Conversation", heading)]
    for item in payload["messages"]:
        story.append(Paragraph(html.escape(item["role"]), heading))
        text = html.escape(item["content"] or "(empty)").replace("\n", "<br/>")
        story.append(Paragraph(text, base))
        if item["attachments"]:
            story.append(Paragraph(html.escape("Attachments: " + ", ".join(item["attachments"])), base))
    if payload["structures"]:
        story.append(Paragraph("Molecular structures", heading))
        for item in payload["structures"]:
            story.append(Paragraph(html.escape(f"{item['filename']} ({item['format'] or 'unknown'})"), base))
    document.build(story)
    return output.getvalue()


def docx_report(payload, script_path):
    node = os.environ.get("FROGENT_NODE_BIN") or shutil.which("node")
    if not node:
        raise RuntimeError("Word export requires Node.js")
    result = subprocess.run(
        [node, str(script_path)], input=json.dumps(payload).encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30,
    )
    if result.returncode or not result.stdout.startswith(b"PK"):
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError("Word export failed" + (f": {detail}" if detail else ""))
    return result.stdout


def _payload(chat):
    messages = []
    for message in chat.get("messages", ()):
        if not isinstance(message, dict):
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "") for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            )
        if not isinstance(content, str):
            content = str(content)
        names = message.get("fileNames", ())
        if isinstance(names, str):
            names = (names,)
        attachments = [str(item) for item in names if item] if isinstance(names, (list, tuple)) else []
        messages.append({"role": "User" if message.get("isUser") else "FROGENT",
                         "content": content, "attachments": attachments})
    structures = []
    for item in chat.get("molecules", ()):
        if isinstance(item, dict):
            structures.append({"filename": str(item.get("filename") or "structure"),
                               "format": str(item.get("format") or "")})
    return {
        "id": str(chat.get("id") or "unknown"),
        "title": str(chat.get("title") or "FROGENT report"),
        "created_at": str(chat.get("createdAt") or "not_recorded"),
        "updated_at": str(chat.get("updatedAt") or "not_recorded"),
        "messages": messages,
        "structures": structures,
    }
