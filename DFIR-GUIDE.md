# VisiData 3.5 — Practical DFIR Investigation Guide

A practical guide for investigating **Plaso supertimelines** and other forensic CSV exports with [VisiData](https://www.visidata.org/) and the [VisiData Supertimeline extension](./README.md).

> **Evidence safety:** Filtering, grouping and pivoting do not delete events from the original CSV. Always export findings under **new filenames**.

## 1. Basic navigation

Open a case CSV from your shell:

```fish
vd /path/to/supertimeline.csv
```

All shortcuts below are pressed **inside VisiData**, not in Fish. `gF` means press `g`, then uppercase `F`. `z_` means press `z`, then underscore (usually Shift+hyphen).

| Shortcut | Action |
|---|---|
| Arrow keys or `h`, `j`, `k`, `l` | Move between cells |
| `q` | Return to previous sheet |
| `Space` | Open command search |
| `Shift+C` | Columns Sheet |
| `F` / `Shift+F` | Frequency Table for current column |
| `W` / `Shift+W` | Pivot Table |
| `!` | Mark/unmark current column as a key |
| `s`, `t`, `u` | Select, toggle, unselect current row |
| `gs`, `gu` | Select all / unselect all |
| `"` | Open selected events as a new sheet |
| `Ctrl+S` | Save sheet to a new path |
| `e` | Edit a writable cell |

## 2. Filter a column

Move to the column to filter, such as `source`, `host`, `sourcetype` or `desc`.

| Keys | Action |
|---|---|
| `\|` | Select rows matching a regular expression in the active column |
| `\` | Unselect rows matching a regular expression in the active column |
| `g\|` | Select rows matching a regex in any visible column |
| `gs` | Select all rows |
| `gu` | Clear selections |
| `"` | Open selected events in a separate sheet |

Useful regular expressions:

```regex
^EVT$
^(EVT|FILE|REG)$
(?i)powershell
^(?!EVT$).*
```

To keep **only EVT** events, move to `source`, press `|`, enter `^EVT$`, then press `"`.

To **exclude EVT, FILE and REG**, move to `source`, press `gs` (select all), then `\`, type `^(EVT|FILE|REG)$` and press Enter. Open the remaining selected rows with `"`.

Searching (`/` or `?`) moves between matches without selecting events. Press `n` / `N` for next / previous match.

## 3. Frequency Tables

Move to `source`, press `F` (Shift+F). The result lists each distinct source and its count/percentage.

**Group by multiple columns:**

1. Move to `host` and press `!` to mark it as a key.
2. Move to `source` and press `!` to mark a second key.
3. Press `gF` to group by both keys.

You can mark three or more key columns, e.g. `host`, `source` and `sourcetype`.

**Drill into or exclude Frequency Table groups:**

| Keys | Action |
|---|---|
| `Enter` | Open underlying source rows for the current group |
| `s` | Select group |
| `g Enter` | Open source rows for all selected groups |
| `z Enter` | Open source rows except those in the current group |
| `gz Enter` | Open source rows except those in the selected groups |

These commands open views, not delete evidence.

## 4. Pivot Tables with two or more columns

A pivot uses **key columns as row dimensions** and the **current column as the pivot dimension**.

### Example A — source counts by host

1. Move to `host`, press `!`.
2. Move to `source`.
3. Press `W` (Shift+W).

Each host is a row; each distinct source becomes a count column.

### Example B — host and source by timestamp type

1. Mark `host` with `!`.
2. Mark `source` with `!`.
3. Move to `type` and press `W`.

Illustrative result:

| host | source | Creation Time | Content Modification |
|---|---|---:|---:|
| RD01 | EVT | 4820 | 0 |
| RD01 | FILE | 1320 | 2410 |
| RD02 | EVT | 3650 | 0 |

**Without a configured aggregator, VisiData counts events by default.**

If a numeric column such as `bytes` exists, convert it to an integer using `#` and add an aggregator using `+` (e.g. `sum`), then pivot on the desired dimension.

**Drill down:** `Enter` opens underlying rows for a pivot group; `z Enter` opens the events behind the specific pivot cell. Use `q` to return.

**Large dataset advice:** Avoid pivoting on `desc`. Descriptions can contain thousands of distinct values and create unwieldy output. Use `host`, `source`, `sourcetype` and `type` first.

## 5. Column width and layout

| Keys | Action |
|---|---|
| `_` | Auto-fit current column |
| `z_` | Set exact width for current column |
| `g_` | Auto-fit all visible columns |
| `gz_` | Set uniform width for all visible columns |
| `-` | Hide current column |
| `gv` | Unhide columns |
| `H` / `L` | Move current column left / right |
| `Shift+C` | Manage columns, including widths |

Example: move to `desc`, press `z_`, enter `100`, then Enter.

## 6. Search and sort

| Keys | Action |
|---|---|
| `/` / `?` | Search forward / backward |
| `n` / `N` | Next / previous match |
| `[` / `]` | Sort active column ascending / descending |
| `g[` / `g]` | Sort by marked key columns |

The extension's synthetic `datetime` is a **display string**, not automatically a parsed timezone-aware timestamp. Verify chronological sorting, particularly across different dates.

## 7. Experimental Windows Event views

The logon and other Windows Event views are unfinished. Results can miss records or contain incomplete field extraction. Verify findings against the original EVTX records.

| Keys | Event ID | Investigation |
|---|---:|---|
| `gz1` | 4624 | Successful logon |
| `gz2` | 4625 | Failed logon |
| `gz3` | 4688 | Process creation |
| `gz4` | 7045 | Service installation |
| `gz5` | 1102 | Security log cleared |
| `gz0` | Custom | Enter another numeric Event ID |

These views require an explicit Event ID in the source export. An empty result does **not** prove an event was absent from the endpoint.

They are separate from the Timeline Explorer artifact-color rules; there are **no extra Event ID-specific color classifications**.

## 8. Timeline Explorer artifact colors

On recognized Plaso supertimelines only the `desc` cell receives a semantic color. The seven original categories and background values are:

| Category | Hex background |
|---|---|
| DeletedData | `#000000` |
| WebHistory | `#FFC000` |
| FolderOpening | `#00B050` |
| FileOpening | `#92D050` |
| Device/USBUsage | `#548DD4` |
| LogFile | `#F3F1EA` |
| Execution | `#CA0002` |

The matching rules run in that order, and **later matches override earlier categories**. Colors indicate activity patterns, not a maliciousness verdict.

See [the main README](./README.md#8-how-the-colors-and-datetime-work) for the complete rule logic and source references.

## 9. Change the canvas: gray, light or dark

Open the locally installed plugin:

```fish
nano ~/.config/visidata/irflow_visidata.py
```

Find `IRFLOW_BASE_COLOR` near the top:

```python
IRFLOW_BASE_COLOR = 'white on 242'
```

Choose a canvas appearance:

| Appearance | Example |
|---|---|
| Gray (default) | `white on 242` |
| Light | `black on 253` |
| Dark | `white on 235` |

Save the file, then **restart VisiData**. This only changes ordinary VisiData cells; the seven artifact colors are unchanged.

Downloading a new plugin version will overwrite local changes.

## 10. Tags, Comments and evidence preservation

Move to the plugin's `Tags` or `Comment` column and press `e`. Tags can contain comma-separated labels such as `Review, Persistence, Confirmed`.

Notes are stored in separate JSON sidecars, usually at:

```text
~/.local/share/visidata/irflow-annotations/
```

The source CSV is not rewritten by these annotation fields. Keep the JSON sidecars with your case notes. If you move or recreate a source CSV, old notes may not match its new path or row fingerprints.

## 11. Export your analysis

From the current filtered, frequency or pivot sheet, press `Ctrl+S` and specify a **new file path**, such as:

```text
/home/spacey/analysis/host-source-pivot.csv
```

Do not overwrite original evidence. A CSV export and the annotation JSON sidecar are separate files.

## 12. Suggested large-timeline workflow

1. Open a preserved CSV.
2. Review `source`, `sourcetype`, `host` and `type` using `F`.
3. Mark `host` and `source` with `!` and press `gF`.
4. Pivot on `type` with `W`.
5. Drill down into significant groups or cells.
6. Exclude noise in new sheets, not by deleting source rows.
7. Tag findings and write supporting comments.
8. Export relevant views to new filenames.

## References

- [VisiData documentation](https://www.visidata.org/docs/)
- [VisiData grouping and pivot tables](https://www.visidata.org/docs/group/)
- [VisiData Frequency Tables](https://www.visidata.org/docs/freq/)
- [VisiData columns](https://www.visidata.org/docs/columns/)
- [VisiData Supertimeline setup and color rules](./README.md)
- [Visual cheat-sheet image](./visidata-dfir-cheat-sheet.svg)

*Scope: VisiData 3.5, VisiData Supertimeline extension, November 2026.*
