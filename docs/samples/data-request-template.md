# System records: data request

Process Map Studio · event-log extract request

## 1. Purpose

We are mapping how the [process] process works today. We would like an extract of the system's event records to measure volumes and waiting times in [process].
The records are used for the process only: no individual performance analysis, and no figure is ever shown for a person.

## 2. Process scope

- Process: [process].
- Start event: [the event that starts a case, for example 'order created'].
- End event: [the event that ends a case, for example 'invoice paid'].
- Please include every event a case goes through between the two, including any loops, corrections or cancellations.

## 3. Date window

- From [date] to [date].
- 3 to 6 months is ideal; at least 4 weeks. Cases that start before the window or end after it may be included as they are.

## 4. Columns

Required columns are marked Yes. One row per event; the sample row shows the expected form.

| Column | Required | What it holds | Sample row |
|---|---|---|---|
| case_id | Yes | The work item each event belongs to (for example a flight, purchase order or contract) | PO-10421 |
| activity | Yes | The recorded event or status change, as the system names it | Order approved |
| timestamp | Yes | When the event happened (its start, if end_timestamp is given), with date and time | 2026-03-02 09:15 |
| end_timestamp | No | When the activity finished, if the system records it (lets work and waiting time be told apart) | 2026-03-02 09:40 |
| resource | No | The user ID in the system; only if no role can be given (converted to a role on import and discarded) | — |
| role | No | The role or team that performed the event (preferred over user IDs) | Buyer |
| system | No | The source system's name, if the extract combines several systems | ERP |
| case attributes | No | Any extra columns useful as filters (for example region, product or amount band); no personal data | Region: North |

## 5. Privacy requirements

- Please give the role or team for each event rather than user IDs wherever the system allows it.
- If user IDs are included, they are converted to roles when the file is imported and then discarded: they are never stored.
- No free-text comment fields.
- No customer personal data (names, addresses, contact details or account numbers).

## 6. Format

- CSV (UTF-8) or Excel (.xlsx), with the column names in the first row.
- One file per system. If the same case has different IDs in different systems, please add a small file that links the IDs.
- Dates and times in one consistent format; please tell us the time zone.

## 7. Data owner approval

- Data owner name: ______
- Data owner role: ______
- Date approved: ______
- Approved for this purpose ☐:

The extract is stored only on the analyst's computer and deleted with the engagement. It is not shared with anyone else.
