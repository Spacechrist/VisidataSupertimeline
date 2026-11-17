# Permanent parser Category menu

Install these two modules alongside the existing timeline extension:

```bash
mkdir -p ~/.config/visidata
cp autorunsc.py dfir_categories.py ~/.config/visidata/
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
replace personal settings. Both modules must be installed together.

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

**Category → Supertimeline** and the other reserved parser entries currently open
an informational page marked **Rules pending**. Their parser review logic is not
yet implemented. Existing experimental timeline commands remain available through
their current bindings; this menu does not change their behavior.

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
python3 -m unittest discover -v
```

Install VisiData 3.5 to run the new integration tests; they report skipped if the
package is unavailable. No forensic CSVs are distributed in this repository.

To uninstall the menu, remove its loader block from your active configuration and
restart VisiData. Keep the existing timeline loader if you still use it.
