# Sample interview templates

The three standard interview templates exactly as the app makes them (PRD v1.10 Appendix F.9),
saved here so they can be checked in Word:

- `interview-template-landscape.docx` — Landscape, 60 minutes (team leads, contract holders,
  cross-functional owners)
- `interview-template-practice.docx` — Practice, 60 minutes (people who do the work)
- `interview-template-follow-up.docx` — Follow-up, 30 minutes (anyone already interviewed)

In the app they download from the home screen (**Interview templates**) and from an engagement's
**Interview** screen, in Word or Markdown. They are made from
`backend/app/prompts/question_bank.json` (question bank v1.0) with no AI and no engagement data,
so every copy is the same.

## Sample tailored guides

Two guides made by the app for interviewees of the illustrative load-control engagement (PRD
Appendix A), saved so the filled-in version can be checked in Word too:

- `interview-guide-practice-sample.docx` — Practice guide for the Ramp role (group "Ramp agents",
  referred by the Load controller): the header and opener are filled in, and M6.5 asks about the
  one step only the documents describe ("Approve load plan").
- `interview-guide-follow-up-sample.docx` — Follow-up guide for the Load controller: the opener
  says what earlier interviews covered, and the five blank rows take one question in turn from the
  SME's own words to play back (F2), the coverage report's gaps (for example M2.1, what sets the
  process off), the open validation questions (F6) and the lane boundaries (F4: "On “Load and
  return LIR”, how does your team work with Ramp?") and how often each exception route happens
  (M5.s2, "How often does something like that happen?", about "Special loads OK? → No").
- `interview-guide-landscape-sample.docx` — Landscape guide for the Ramp group: the role module
  holds four questions Claude drafted (RM1–RM4, illustrative offline answers) that passed the app's
  checks; a fifth, which quoted the SOP, was left out.

The question IDs, wording and minutes are the same as in the standard templates.

## Data request template (system records)

What you send to a system owner (IT) to ask for an event-log extract (PRD §3.13.2), made by the
app with no engagement data, so every copy is the same:

- `data-request-template.docx` and `data-request-template.md`: purpose, process scope, date
  window, the columns (required ones marked, with a sample row), privacy requirements, format, and
  the data owner's approval with the retention promise. Fill in the [bracketed] parts.
- `data-request-header.csv`: the header row only, ready for the system owner to fill.
