"""Test helper (P10b R11): a working spreadsheet and an email thread built in code, so no binary
file is checked in and every test reads the same content. Names and addresses are invented."""

from __future__ import annotations

import io
from datetime import date, datetime
from email.message import EmailMessage

from openpyxl import Workbook

SHEET_TITLE = "Load plan tracker"


def make_xlsx() -> bytes:
    """Two sheets: a title row, then a header row and two rows; a sheet whose name has a space."""
    book = Workbook()
    plan = book.active
    assert plan is not None
    plan.title = "Plan"
    plan.append([SHEET_TITLE])
    plan.append([])
    plan.append(["Flight", "Step", "Owner", "Minutes", "Date"])
    plan.append(["SQ 221", "Draft load plan", "Load controller", 20, date(2026, 3, 2)])
    plan.append(["SQ 221", "Weight check", "Ramp", 12.5, datetime(2026, 3, 2, 9, 14)])
    log = book.create_sheet("Shift log")
    log.append(["Shift", "Note", None])
    log.append(["Night", "Plan revised twice; captain called LC", "extra"])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


CSV = b'Flight;Step;Minutes\r\nSQ 221;Draft load plan;20\r\n\r\nSQ 222;"Weight check; ramp";12\r\n'


def _forwarded() -> EmailMessage:
    """An email attached to the thread: a forward whose body quotes an Outlook header block."""
    inner = EmailMessage()
    inner["From"] = "Ramp Lead <ramp.lead@example.com>"
    inner["To"] = "Load Control <lc@example.com>"
    inner["Date"] = "Mon, 02 Mar 2026 21:05:00 +0800"
    inner["Subject"] = "FW: Late bags"
    inner.set_content(
        "Forwarding for the record.\n"
        "\n"
        "From: Ops Desk <ops.desk@example.com>\n"
        "Sent: Monday, 2 March 2026 21:00\n"
        "To: Load Control; Kumar, Ravi\n"
        "Subject: Late bags\n"
        "\n"
        "Bags for SQ 221 will be 20 minutes late.\n"
    )
    return inner


def make_eml() -> bytes:
    """A reply with a signature and a quoted message, an attached email and a PDF attachment."""
    message = EmailMessage()
    message["From"] = '"Tan, Wei Ming" <weiming.tan@example.com>'
    message["To"] = "LC Ops Desk <lc.ops@example.com>, ramp.lead@example.com"
    message["Cc"] = "Priya Nair <priya.nair@example.com>"
    message["Date"] = "Tue, 03 Mar 2026 09:14:00 +0800"
    message["Subject"] = "Load plan revision SQ 221"
    message.set_content(
        "Hi team,\n"
        "\n"
        "The plan for SQ 221 was revised twice last night\n"
        "because the bags came late. We held the bags until the second wave.\n"
        "\n"
        "-- \n"
        "Wei Ming\n"
        "Load Control | +65 6000 0000\n"
        "\n"
        "On Mon, 2 Mar 2026 at 22:10, Priya Nair <priya.nair@example.com> wrote:\n"
        "> Can we release the plan before the final figures?\n"
        "> The captain is asking.\n"
    )
    message.add_attachment(b"%PDF-1.4 not read", maintype="application", subtype="pdf",
                           filename="loadsheet.pdf")  # fmt: skip
    message.add_attachment(_forwarded())
    return bytes(message)


def make_html_eml() -> bytes:
    """An HTML-only email (no plain part), with a style block and a Gmail-style quote."""
    message = EmailMessage()
    message["From"] = "Ops Desk <ops.desk@example.com>"
    message["Subject"] = "Gate change"
    message.set_content(
        "<html><head><style>p {color: red}</style></head><body>"
        "<p>Gate changed to <b>C24</b> &amp; plan reissued.</p>"
        "<div>On Tue, 3 Mar 2026 at 08:00, Ravi Kumar &lt;ravi.kumar@example.com&gt; wrote:</div>"
        "<blockquote><p>Is the gate final?</p></blockquote></body></html>",
        subtype="html",
    )
    return bytes(message)
