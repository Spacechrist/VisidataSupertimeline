# Permanent parser Category menu

Install these four modules alongside the existing timeline extension:

```bash
mkdir -p ~/.config/visidata
cp autorunsc.py dfir_categories.py artifact_categories.py dfir_catalog.py ~/.config/visidata/
```

Append this loader **once** to your active VisiData configuration, preserving its
existing contents and the timeline extension loader. Usually this is
`~/.config/visidata/config.py` if present, otherwise `~/.visidatarc`:

```python
import sys
from pathlib import Path

dfir_plugin_dir = str(Path.home() / ".config/visidata")
if dfir_plugin_dir not in sys.path:
    sys.path.insert(0, dfir_plugin_dir)
import dfir_categories
```

If you use a custom plugin location, substitute that directory. Restart VisiData
and open your CSV normally. This loader imports the modules once; it does not
replace personal settings. All four modules must be installed together.

## Menus and controls

Use VisiData's native **Category → Autorunsc** menu to open its category counts,
then Enter on a category. **Category → All parsers** opens the parser overview;
Enter opens the selected parser. F2 also opens this overview if F2 is unassigned.
The plugin preserves an existing F2 binding; the native menu remains available.
The command `dfir-categories` is available through Space without any new shortcut.

| Key inside Autorunsc | Action |
| --- | --- |
| 1 | Services |
| 2 | Drivers |
| 3 | Tasks |
| 4 | KnownDLLs |
| 5 | Logon |
| 6 | Explorer |
| 0 | All categories, including categories outside these six |
| F5 | Toggle enabled only |
| F6 | Toggle unverified only, including unknown signers |
| F7 | Toggle missing images only |
| F8 | Clear filters in the current category |
| q | Close the current sheet |

Example: **Category → Autorunsc → 1 → F5 → F6** opens
`Autorunsc - Services - Enabled + Unverified`. Filters combine with AND;
category changes preserve filter settings. Resetting filters restores the
complete category snapshot, including previously hidden entries.

The numeric and filter bindings apply only to the plugin's own sheets. Normal
CSV sheet bindings and the existing timeline shortcuts are unchanged. Additional
commands beginning with `autorunsc-` are available through Space.

Nine artifact modules now have working category and grouping views: EVTXECmd,
MFTECmd, RECmd, EZTools Execution, EZTools File and Folder, SQLECmd, SRUM,
Hayabusa, and Chainsaw. Use **Category → Review this CSV** for automatic
schema-aware selection, or select the parser explicitly. Enter opens category
rows or a grouping. Grouping counts are distinct values; category counts may
overlap. All original CSV columns remain available, and view rows are independent
copies. Parser mismatches are rejected rather than silently applying unrelated
filters.

Supertimeline, Filesystem Timeline, PyrsistenceSniper and YARA-X remain reserved
in this menu because the supplied result archive contains no sample outputs for
them. Existing experimental timeline commands and bindings remain available.

## Open a result ZIP directly

After restarting VisiData with the updated modules loaded:

```bash
vd -f dfirzip /path/to/DESKTOP-SDN1RPT_result_csvs_verified.zip
```

The archive catalog shows parser, artifact, profile, rows, representation and
empty-report state. **Enter** opens a CSV directly from the ZIP without extracting
or changing it. Then use **Category → Review this CSV** (or F2 and the parser).
**q** returns through the views. **F5 in the ZIP catalog only** toggles primary
reports versus all 136 reports.

Primary/alternate is a presentation preference, not an evidence-quality verdict.
The catalog prefers resolved SRUM provider tables and Timesketch EVTX when their
matching alternatives are actually present. Raw-only reports stay primary. SRUM
system tables remain Reference. Combined RECmd batches are Alternate when detail
reports are present. None are deleted, and the archive initially displays all
representations. Physical row totals are never labelled unique events.

Categories preserve native flags and severity labels. Unallocated MFT records
are not automatically labelled user-deleted; the native SI<FN flag is not a
standalone timestomping verdict. Shimcache or Amcache presence is not proof of
execution. SRUM numeric IDs are not labelled resolved usernames.

A static catalog can be created without installing VisiData:

```bash
python3 dfir_catalog.py /path/to/results.zip --output /new/path/SOURCE-CATALOG.csv
```

## Evidence handling

- Review rows are copies of CSV values. The source CSV and sheet remain unchanged.
- Blank Entry rows are collector separators and excluded from review counts.
- The CSV category `Known DLLs` is displayed as `KnownDLLs`.
- Enabled means the Enabled field says `enabled`, ignoring case and whitespace.
  Blank values remain unknown and do not match Enabled.
- Verified means Signer starts with `(Verified)`, ignoring case and whitespace.
  A blank Signer is **Unknown**, not proven unsigned. F6 includes unknown,
  unverified, and explicitly unsigned entries. Original signer text is retained.
- Missing Image matches an explicit `File not found:` diagnostic in Image Path.
  No existence checks run against the analyst's workstation.
- Signed entries are not presumed safe. Autostart configuration does not prove
  execution. The source Time field is retained without interpreting it as an
  installation or execution time.
- Reopen Category → Autorunsc from the original sheet to snapshot reloaded data.
- For UTF-16 collector output, use an appropriately decoded CSV. Preserve the
  original evidence when creating a UTF-8 working copy.

## Adding parsers and testing

`dfir_categories.py` owns the shared menu and `register_parser()` registry.
Each parser gets a unique `dfir-parser-...` command with no global keybinding.
Duplicate parser names and existing command names are rejected. Implement parser
handlers in separate modules with their own sheet subclasses, and register a
handler in place of the pending entry. Keep parser-specific shortcuts on those
subclasses. Use namespaced command names to avoid collisions with other plugins.

The tests use synthetic rows and subprocesses running real VisiData, separately
from the existing timeline tests' mocked interface:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -v
```

The pinned test dependency is VisiData 3.5. All 44 tests should run without
skipping when it is installed. Without VisiData, integration tests explicitly
report skipped. Tests use synthetic evidence and exercise ZIP navigation,
category/group drill-down, original-value preservation, parser guards, and
existing-menu/keybinding compatibility. No forensic CSVs are distributed in
this repository.

To uninstall the menu, remove its loader block from your active configuration and
restart VisiData. Keep the existing timeline loader if you still use it.
