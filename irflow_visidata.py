"""Timeline Explorer-compatible Plaso colors and IRFlow colors for other profiles.

Copy this entire file into ~/.visidatarc, or execute it from ~/.visidatarc:
    exec(compile(open('/absolute/path/irflow_visidata.py', encoding='utf-8').read(),
                 '/absolute/path/irflow_visidata.py', 'exec'))

IRFlow source reference (main, checked 2026-11-11):
    src/constants/timeline-palette.js
    src/utils/color-rules.js
    src/constants/kape-profiles.js
    src/constants/presets.js

For an ordinary Plaso supertimeline the detection columns are:
    date, time, macb, source, sourcetype, type
and Timeline Explorer classifies its desc text (not the source column).

Exact rule matching and color order; hex colors approximated to xterm-256.
"""
from visidata import TableSheet, RowColorizer, CellColorizer, Column, options, vd
from pathlib import Path
import hashlib
import json
import os
import re
import tempfile

# A stable neutral grey canvas keeps black DeletedData cells distinct from
# the surrounding timeline in both light and dark terminal/host themes.
# xterm-256 index 242 is RGB (108, 108, 108), approximately #6C6C6C.
# The seven Timeline Explorer artifact colors are separate and unchanged.
IRFLOW_BASE_COLOR = 'white on 242'

options.theme = 'asciimono'
options.color_default = IRFLOW_BASE_COLOR

# VisiData 3.5 renamed color_longname to color_longname_status / _guide,
# but its bundled asciimono theme still contains the obsolete option.
# Also disable the theme's reverse-video *entire-row* cursor highlighting.
# VisiData applies the theme during run(), after the user config is loaded,
# so adjust the theme definition rather than options.color_current_row here.
def _irflow_configure_asciimono_theme(theme):
    theme.pop('color_longname', None)
    theme.setdefault('color_longname_status', '')
    theme.setdefault('color_longname_guide', '')
    # Highlight only the active cell, not the full row or active column.
    theme['color_current_row'] = ''
    theme['color_current_col'] = ''
    theme['color_current_cell'] = 'bold reverse'
    # VisiData applies asciimono during run(), after config.py is executed.
    # Set the canvas in the theme as well, or the theme resets it to '' and
    # the host terminal's black/white background bleeds into uncolored cells.
    theme['color_default'] = IRFLOW_BASE_COLOR


if getattr(vd, 'themes', None) is not None:
    from visidata.themes import asciimono as _irflow_asciimono_theme
    _theme = vd.themes.get('asciimono')
    if _theme is not None:
        _irflow_configure_asciimono_theme(_theme)

# User-preferred IRFlow light palette. IRFlow's automatic profile detection
# uses the dark palette upstream; both original palette tables remain intact.
IRFLOW_THEME = 'light'  # set to 'dark' to restore IRFlow's automatic default
IRFLOW_AUTO_MAX_RULES = 150
# Non-Plaso IRFlow profiles sample the initial 5,000 imported rows (2,500 > 5 GiB).
IRFLOW_SAMPLE_ROWS = 5000
IRFLOW_LARGE_SAMPLE_ROWS = 2500
IRFLOW_LARGE_FILE_BYTES = 5 * 1024 * 1024 * 1024
IRFLOW_ENABLE_DFIR_PRESETS = False  # IRFlow's presets are NOT enabled by default

# Plaso view-only layout: show one datetime column while retaining original fields.
IRFLOW_COMBINE_PLASO_DATETIME = True
IRFLOW_HIDE_SPLIT_PLASO_DATE_TIME = True

# Exact background/foreground hex strings from src/constants/timeline-palette.js
IRFLOW_DARK_HEX = [
    ('#1a3a2a', '#6ee7b7'), ('#1e3a5f', '#93c5fd'),
    ('#3b1f4b', '#d8b4fe'), ('#4a2c17', '#fdba74'),
    ('#3b2020', '#fca5a5'), ('#1a3344', '#67e8f9'),
    ('#3b3417', '#fde68a'), ('#2d1b3d', '#f0abfc'),
    ('#1b3031', '#5eead4'), ('#1f2937', '#e5e7eb'),
    ('#312e18', '#d6d3a4'), ('#1c2b3a', '#7dd3fc'),
    ('#2e1e1e', '#f9a8d4'), ('#1c331c', '#86efac'),
    ('#332211', '#f5c78e'), ('#262640', '#a5b4fc'),
]
IRFLOW_LIGHT_HEX = [
    ('#d1fae5', '#065f46'), ('#dbeafe', '#1e40af'),
    ('#ede9fe', '#5b21b6'), ('#ffedd5', '#9a3412'),
    ('#fee2e2', '#991b1b'), ('#cffafe', '#155e75'),
    ('#fef9c3', '#854d0e'), ('#fae8ff', '#86198f'),
    ('#ccfbf1', '#115e59'), ('#f3f4f6', '#374151'),
    ('#fef3c7', '#78350f'), ('#e0f2fe', '#075985'),
    ('#fce7f3', '#9d174d'), ('#dcfce7', '#166534'),
    ('#fff7ed', '#7c2d12'), ('#eef2ff', '#3730a3'),
]

# KAPE timeline profiles with automatic row coloring from kape-profiles.js.
# Order intentionally follows the IRFlow profile order.
IRFLOW_TIMELINE_PROFILES = [
    (('DateTime', 'TimestampInfo', 'ArtifactName', 'Tool', 'Description'), 'ArtifactName'),
    (('date', 'time', 'macb', 'source', 'sourcetype', 'type'), 'source'),
    (('Timestamp', 'Macb', 'SourceName', 'LongDescription', 'FileName'), 'SourceName'),
    (('Timestamp', 'DataType', 'ComputerName', 'UserSource', 'Message'), 'DataType'),
    (('Timestamp', 'TimestampDescription', 'Source', 'SourceLong'), 'Source'),
]

# These are the eight official UI presets, NOT default automatic coloring.
# Enable with IRFLOW_ENABLE_DFIR_PRESETS = True; preset priority comes first.
IRFLOW_DFIR_PRESETS = [
    ('Process', 'contains', 'powershell', '#7f1d1d', '#fca5a5'),
    ('Message', 'contains', 'mimikatz', '#581c87', '#d8b4fe'),
    ('Process', 'contains', 'psexec', '#713f12', '#fde68a'),
    ('Message', 'contains', 'lsass', '#064e3b', '#6ee7b7'),
    ('Level', 'equals', 'Critical', '#991b1b', '#ffffff'),
    ('Level', 'equals', 'Error', '#92400e', '#fde68a'),
    ('Message', 'contains', 'c2.', '#1e3a5f', '#93c5fd'),
    ('Message', 'contains', 'encoded', '#4c1d95', '#c4b5fd'),
]

# Analyst-defined rules, in IRFlow order: first matching rule wins.
# Example: ('source', 'equals', 'EVT', '#7f1d1d', '#fca5a5')
IRFLOW_CUSTOM_RULES = []


def _irflow_rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def _irflow_xterm_256(hex_color):
    """Nearest xterm 256 palette entry (indices 16..255)."""
    rgb = _irflow_rgb(hex_color)
    shades = (0, 95, 135, 175, 215, 255)
    candidates = []
    for r in range(6):
        for g in range(6):
            for b in range(6):
                candidates.append((16 + 36 * r + 6 * g + b, (shades[r], shades[g], shades[b])))
    for n in range(24):
        shade = 8 + n * 10
        candidates.append((232 + n, (shade, shade, shade)))
    # Minimum RGB distance; RGB hex remains the canonical saved representation.
    return min(candidates, key=lambda e: sum((a - b) ** 2 for a, b in zip(rgb, e[1])))[0]


def _irflow_term_color(bg_hex, fg_hex):
    return '%d on %d' % (_irflow_xterm_256(fg_hex), _irflow_xterm_256(bg_hex))


def _irflow_str(value):
    return '' if value is None else str(value)


def _irflow_detect_col(sheet):
    # IRFlow detectKapeProfile matches the complete header set, case-insensitively.
    col_by_lower = {str(c.name).lower(): c for c in sheet.columns}
    for required, auto_col in IRFLOW_TIMELINE_PROFILES:
        if all(n.lower() in col_by_lower for n in required):
            return col_by_lower[auto_col.lower()], col_by_lower
    return None, col_by_lower


def _irflow_value(col, row):
    try:
        return _irflow_str(col.getValue(row))
    except Exception:
        return ''



# Timeline Explorer's original Plaso/L2TCSV color categories.
# Sources:
#   EricZimmerman/TLEFilePlugins/TLEFileTimelines/Timelines.cs
#     SuperTimelineData(longDesc, sourceName, sourceDesc)
#   EricZimmerman/TLEFilePlugins/Layouts/Default/TLEFileTimelines.SuperTimeline.layout
# The source layout colors colLongDescription only, and defines foreground
# colors only for DeletedData, Execution, and WebHistory.
# Hex pairs are canonical; VisiData's terminal colors approximate them.
IRFLOW_TLE_PLASO_COLORS = {
    'LogFile': ('#F3F1EA', None),
    'DeletedData': ('#000000', '#FFFFFF'),
    'Device|USBUsage': ('#548DD4', None),
    'Execution': ('#CA0002', '#FFFFFF'),
    'FileOpening': ('#92D050', None),
    'FolderOpening': ('#00B050', None),
    'WebHistory': ('#FFC000', '#000000'),
}


def _irflow_is_plaso(sheet):
    """Recognize the Plaso L2TCSV profile; do not use first-seen source colors."""
    names = {str(c.name).casefold() for c in sheet.columns}
    return all(name in names for name in
               ('date', 'time', 'macb', 'source', 'sourcetype', 'type'))


def _irflow_tle_plaso_category(long_desc, source_name, source_desc):
    """Port of Timeline Explorer's SuperTimelineData color logic.

    Match rules use C#'s original case-sensitive Contains/StartsWith behavior,
    except the explicit OrdinalIgnoreCase matches. Independent if-blocks are
    intentional: later matches overwrite earlier categories.
    """
    if long_desc is None:
        return None  # Original constructor returns early on null longDesc.

    d = str(long_desc)
    source = '' if source_name is None else str(source_name)
    srcdesc = '' if source_desc is None else str(source_desc)
    category = None

    if any(x in d for x in
           ('RECYCLE', 'DELETED', 'Deleted Registry', '$Recycle.Bin')):
        category = 'DeletedData'

    if (any(x in d for x in
            ('Expiration Time', 'Cookie', 'Visited', 'Flash Cookie',
             'Location:', 'time(s) [HTTP', 'Last Visited Time'))
            or ('URL' in d and 'FILE' not in source)
            or ('LSO' in d and 'REG' not in source)
            or 'http://' in d.lower()
            or 'https://' in d.lower()
            or source.startswith('WEBHIST')):
        category = 'WebHistory'

    if (any(x in d for x in
            ('lnk/shell_items', 'BagMRU', 'ShellNoRoam/Bags'))
            or 'File entry shell item' in srcdesc):
        category = 'FolderOpening'

    if (any(x in d for x in
            ('visited file://', 'CreateDate', 'URL:file://', 'File Opened',
             'Folder opened', 'Shortcut LNK', 'RecentDocs key',
             'Link target:', 'File attribute flags',
             'Birth droid volume identifier:', 'UserAssist entry',
             'Recently opened file', 'file of extension', 'RecentDocs'))
            or d.lower().endswith('.lnk')
            or ('Recently' in d and 'Firefox' not in srcdesc)
            or d.endswith('LNK')
            or ('file://' in d and 'Firefox' not in srcdesc)):
        category = 'FileOpening'

    if any(x in d for x in (
            'MountPoints2', 'volume mounted', 'USB', '/USB/Vid_',
            'Enum/USBSTOR/Disk', 'RemovableMedia',
            'STORAGE/RemovableMedia', 'drive mounted',
            'Drive last mounted', 'SetupAPI Log')):
        category = 'Device|USBUsage'

    if (any(x in d for x in ('EVT', 'XP Firewall Log', 'Event Level:'))
            or source.startswith('EVT')):
        category = 'LogFile'

    if (any(x in d for x in (
            'Prefetch {', 'AppCompatCache', r'\Software\Sysinternals',
            'typed the following cmd', 'CMD typed', 'Last run', 'RunMRU',
            'MUICache', 'UserAssist key', 'Time of Launch', 'Prefetch',
            'SHIMCACHE', 'Scheduled', 'was run', 'UEME_'))
            or d.lower().endswith('.pf')
            or d.startswith('[PROCESS]')):
        category = 'Execution'

    return category


# Timeline Explorer's Plaso layout leaves foreground unspecified for four
# categories. On a light Windows theme they inherit dark text; in a terminal
# with a dark-host default, inheriting white text makes those pale backgrounds
# unreadable. Resolve the *display* foreground to black in those cases, while
# preserving every original category, match rule, and canonical background.
_IRFLOW_TLE_TERMINAL_COLORS = {
    category: _irflow_term_color(bg, fg or '#000000')
    for category, (bg, fg) in IRFLOW_TLE_PLASO_COLORS.items()
}

def _irflow_tle_color_cell(sheet, col, row, value):
    """Color exactly the Plaso desc cell, like TLE colLongDescription."""
    if row is None or col is None or str(col.name).casefold() != 'desc':
        return None
    source_sheet = getattr(sheet, '_irflow_source_sheet', sheet)
    if not _irflow_is_plaso(source_sheet):
        return None
    cols = {str(c.name).casefold(): c for c in source_sheet.columns}
    if not all(k in cols for k in ('source', 'sourcetype', 'desc')):
        return None
    try:
        description = cols['desc'].getValue(row)
        category = _irflow_tle_plaso_category(
            description, cols['source'].getValue(row),
            cols['sourcetype'].getValue(row))
    except Exception:
        return None
    return _IRFLOW_TLE_TERMINAL_COLORS.get(category)



def _irflow_compile_rules(sheet):
    """Compiled once per sheet, based on source values in original row order."""
    auto_col, columns = _irflow_detect_col(sheet)
    if auto_col is None:
        return None
    ordered = []
    if IRFLOW_ENABLE_DFIR_PRESETS:
        ordered.extend(IRFLOW_DFIR_PRESETS)
    ordered.extend(IRFLOW_CUSTOM_RULES)
    compiled = []
    for col_name, op, match, bg, fg in ordered:
        col = columns.get(col_name.lower())
        if col is None:
            continue
        try:
            regexp = re.compile(match, re.IGNORECASE) if op == 'regex' else None
        except re.error:
            continue
        compiled.append((col, op, match.lower(), regexp, _irflow_term_color(bg, fg)))

    palette = IRFLOW_LIGHT_HEX if IRFLOW_THEME.lower() == 'light' else IRFLOW_DARK_HEX
    palette = [_irflow_term_color(bg, fg) for bg, fg in palette]
    seen = set()
    initial_limit = IRFLOW_SAMPLE_ROWS
    try:
        if os.path.getsize(str(sheet.source)) > IRFLOW_LARGE_FILE_BYTES:
            initial_limit = IRFLOW_LARGE_SAMPLE_ROWS
    except (AttributeError, OSError, ValueError, TypeError):
        pass
    # Unlike the full sheet, IRFlow builds its rules from *only* the first
    # import window; a new source value appearing later remains uncolored.
    for row in sheet.rows[:initial_limit]:
        value = _irflow_value(auto_col, row).strip()
        if value and value not in seen:
            idx = len(seen)
            seen.add(value)
            compiled.append((auto_col, 'equals', value.lower(), None, palette[idx % len(palette)]))
            if len(seen) >= IRFLOW_AUTO_MAX_RULES:
                break
    return compiled


def _irflow_color_row(sheet, col, row, value):
    if row is None:
        return None
    # Derived views should retain the original event-to-color mapping.
    sheet = getattr(sheet, '_irflow_source_sheet', sheet)
    if _irflow_is_plaso(sheet):
        return None  # TLE Plaso uses only a desc-cell colorizer, never row colors.
    try:
        rows = sheet.rows
        cache_sig = (id(rows), len(rows), id(sheet.columns))
        cache = getattr(sheet, '_irflow_color_cache', None)
        if cache is None or cache[0] != cache_sig:
            rules = _irflow_compile_rules(sheet)
            cache = (cache_sig, rules)
            sheet._irflow_color_cache = cache
        for rule_col, op, match, regexp, color in cache[1] or ():
            raw = _irflow_value(rule_col, row)
            norm = raw.lower()
            if (op == 'equals' and norm == match
                    or op == 'contains' and match in norm
                    or op == 'startswith' and norm.startswith(match)
                    or op == 'regex' and regexp.search(raw)):
                return color
    except Exception:
        return None
    return None



# ----- IRFlow forensic annotations (edit-safe, external sidecar) -----
IRFLOW_ENABLE_ANNOTATIONS = True


def _irflow_row_digest(row):
    payload = json.dumps(row, ensure_ascii=False, sort_keys=isinstance(row, dict),
                         default=str, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8', 'surrogatepass')).hexdigest()


def _irflow_annotation_path(source):
    base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    if not base.is_absolute():
        base = Path.home() / '.local/share'
    name = hashlib.sha256(str(source).encode('utf-8')).hexdigest() + '.json'
    return base / 'visidata' / 'irflow-annotations' / name


def _irflow_annotation_source(sheet):
    try:
        raw = getattr(sheet, 'source', None)
        if raw is None:
            return None
        source = Path(str(raw)).expanduser().resolve()
        return source if source.is_file() else None
    except (OSError, TypeError, ValueError):
        return None


def _irflow_normalize_tags(text):
    seen, tags = set(), []
    for part in str(text or '').split(','):
        tag = part.strip()
        if tag and tag.casefold() not in seen:
            tags.append(tag)
            seen.add(tag.casefold())
    return ', '.join(tags)


def _irflow_annotation_state(sheet):
    source = _irflow_annotation_source(sheet)
    if source is None:
        return None
    stat = source.stat()
    location = _irflow_annotation_path(source)
    entries = {}
    if location.exists():
        # Invalid sidecars must not be silently overwritten with empty data.
        obj = json.loads(location.read_text(encoding='utf-8'))
        if (not isinstance(obj, dict) or obj.get('version') != 1
                or obj.get('source') != str(source)
                or not isinstance(obj.get('entries'), dict)):
            raise ValueError(f'IRFlow annotation sidecar has invalid format: {location}')
        entries = obj['entries']
    verified = set()
    unmatched = 0
    for key, entry in entries.items():
        if (isinstance(key, str) and key.isdecimal()
                and int(key) < len(sheet.rows)
                and isinstance(entry, dict)
                and entry.get('row_sha256') == _irflow_row_digest(sheet.rows[int(key)])):
            verified.add(int(key))
        else:
            unmatched += 1
    if unmatched:
        vd.warning(f'IRFlow: {unmatched} annotation(s) do not match source rows; retained in sidecar')
    return {
        'source': source,
        'stat': (stat.st_size, stat.st_mtime_ns),
        'path': location,
        'entries': entries,
        'verified': verified,
        # Row objects keep their identity when sorting or selecting subsets.
        'indices': {id(row): index for index, row in enumerate(sheet.rows)},
    }


def _irflow_save_annotations(state, entries):
    stat = state['source'].stat()
    if (stat.st_size, stat.st_mtime_ns) != state['stat']:
        raise RuntimeError('Source CSV changed since loading; annotations were not saved')
    destination = state['path']
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    body = {
        'version': 1,
        'source': str(state['source']),
        'source_size': stat.st_size,
        'source_mtime_ns': stat.st_mtime_ns,
        'entries': entries,
    }
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix='.irflow-', suffix='.tmp',
                                         dir=destination.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(body, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    finally:
        if temp_path is not None and os.path.exists(temp_path):
            os.unlink(temp_path)


def _irflow_annotated_value(state, row, field):
    index = state['indices'].get(id(row))
    if index is None or index not in state['verified']:
        return ''
    return state['entries'][str(index)].get(field, '')


def _irflow_set_annotation(state, row, field, new_value):
    index = state['indices'].get(id(row))
    if index is None:
        raise ValueError('Cannot annotate an event without an original source row')
    key = str(index)
    digest = _irflow_row_digest(row)
    previous = state['entries'].get(key, {})
    if previous and previous.get('row_sha256') != digest:
        raise ValueError('Source row differs from stored annotation; will not overwrite it')
    value = (_irflow_normalize_tags(new_value) if field == 'tags'
             else '' if new_value is None else str(new_value))
    if value == previous.get(field, ''):
        return
    entry = dict(previous)
    entry['row_sha256'] = digest
    entry[field] = value
    entries = dict(state['entries'])
    if entry.get('tags') or entry.get('comment'):
        entries[key] = entry
    else:
        entries.pop(key, None)
    # Write first: a failed write must not appear as a saved annotation.
    _irflow_save_annotations(state, entries)
    state['entries'] = entries
    if key in entries:
        state['verified'].add(index)
    else:
        state['verified'].discard(index)


class _IRFlowAnnotationColumn(Column):
    """Editable, immediately sidecar-saved column without dirtying evidence CSV."""
    def setValue(self, row, value, setModified=True):
        return super().setValue(row, value, setModified=False)


def _irflow_add_annotation_columns(sheet):
    if not IRFLOW_ENABLE_ANNOTATIONS or _irflow_detect_col(sheet)[0] is None:
        return
    names = {str(c.name).casefold() for c in sheet.columns}
    if 'tags' in names or 'comment' in names:
        return
    try:
        state = _irflow_annotation_state(sheet)
    except (OSError, ValueError, TypeError) as exc:
        vd.warning(f'IRFlow annotations disabled: {exc}')
        return
    if state is None:
        return
    sheet._irflow_annotation_state = state
    was_modified = getattr(sheet, 'hasBeenModified', False)
    # Place investigation annotations immediately before Plaso's extra field.
    # Other IRFlow profiles without extra append annotations at the end.
    index = next((i for i, c in enumerate(sheet.columns)
                  if str(c.name).casefold() == 'extra'), len(sheet.columns))
    for offset, (name, field, width) in enumerate((('Tags', 'tags', 25),
                                                    ('Comment', 'comment', 60))):
        def getter(col, row, field=field):
            return _irflow_annotated_value(state, row, field)

        def setter(col, row, val, field=field):
            _irflow_set_annotation(state, row, field, val)

        col = _IRFlowAnnotationColumn(name, type=str, getter=getter,
                                      setter=setter, width=width)
        sheet.addColumn(col, index=index + offset)
        col.defer = False
    sheet.hasBeenModified = was_modified


def _irflow_add_plaso_datetime(sheet):
    """Combine Plaso date/time for display without touching the evidence rows."""
    if not IRFLOW_COMBINE_PLASO_DATETIME:
        return
    columns = {str(c.name).lower(): c for c in sheet.columns}
    required = ('date', 'time', 'macb', 'source', 'sourcetype', 'type')
    if not all(name in columns for name in required) or 'datetime' in columns:
        return

    date_col, time_col = columns['date'], columns['time']

    def combine_datetime(col, row):
        date_text = _irflow_value(date_col, row).strip()
        time_text = _irflow_value(time_col, row).strip()
        return (date_text + ' ' + time_text).strip()

    # A synthetic display column; do not alter the original date/time values.
    # Restore the modified flag since this happens automatically on load.
    was_modified = getattr(sheet, 'hasBeenModified', False)
    sheet.addColumn(Column('datetime', width=21, getter=combine_datetime), index=0)
    if IRFLOW_HIDE_SPLIT_PLASO_DATE_TIME:
        date_col.hidden = True
        time_col.hidden = True
    sheet.hasBeenModified = was_modified


@TableSheet.after
def afterLoad(sheet):
    _irflow_add_plaso_datetime(sheet)
    _irflow_add_annotation_columns(sheet)


# Matching Plaso timelines receive TLE's desc-cell coloring; other supported
# IRFlow profile formats retain source-based row coloring. The color precedence
# matches the existing 2.5 setting (below the current-cell highlighting).
if not any(getattr(x, '_irflow_autocolor', False) for x in TableSheet.colorizers):
    _irflow_colorizer = RowColorizer(2.5, None, _irflow_color_row)
    _irflow_colorizer._irflow_autocolor = True
    TableSheet.colorizers.insert(0, _irflow_colorizer)
if not any(getattr(x, '_irflow_tle_plaso', False) for x in TableSheet.colorizers):
    _irflow_tle_colorizer = CellColorizer(2.5, None, _irflow_tle_color_cell)
    _irflow_tle_colorizer._irflow_tle_plaso = True
    TableSheet.colorizers.insert(0, _irflow_tle_colorizer)


# ----- Experimental Windows Event Log analysis views (Plaso supertimelines) -----
from copy import copy as _irflow_copy_sheet

IRFLOW_ANALYSIS_VIEWS = {
    '4624': ('Successful Logons', ('Username', 'Source IP', 'Workstation', 'Logon Type')),
    '4625': ('Failed Logons', ('Username', 'Source IP', 'Workstation', 'Logon Type', 'Status')),
    '4688': ('Process Execution', ('Username', 'Process Name', 'Command Line', 'Parent Process')),
    '7045': ('Service Installation', ('Service Name', 'Service Path', 'Service Account')),
    '1102': ('Security Log Cleared', ('Username',)),
}

_IRFLOW_EVENT_ID_RE = re.compile(
    r'\b(?:event[\s_-]*(?:id|identifier)|eventid)\b[\"\']?\s*(?::|=|#|\s)\s*[\"\']?(\d{3,6})\b',
    re.IGNORECASE,
)
_IRFLOW_EVENT_XML_RE = re.compile(r'<EventID>\s*(\d{3,6})\s*</EventID>', re.IGNORECASE)

_IRFLOW_FIELD_NAMES = {
    'Username': ('TargetUserName', 'Target User Name', 'New Logon Account Name',
                 'Target Account Name', 'Target_User_Name', 'target_username', 'Username'),
    'Source IP': ('IpAddress', 'Source Network Address', 'Source IP Address',
                  'Source IP', 'Source Address', 'ip_address', 'source_ip_address'),
    'Workstation': ('WorkstationName', 'Workstation Name', 'workstation_name'),
    'Logon Type': ('LogonType', 'Logon Type', 'logon_type'),
    'Status': ('SubStatus', 'Status', 'FailureReason', 'Failure Reason', 'sub_status'),
    'Process Name': ('NewProcessName', 'New Process Name', 'ProcessName', 'Process Name', 'new_process_name'),
    'Command Line': ('ProcessCommandLine', 'Process Command Line', 'CommandLine', 'Command Line', 'command_line'),
    'Parent Process': ('ParentProcessName', 'Parent Process Name', 'CreatorProcessName', 'parent_process_name'),
    'Service Name': ('ServiceName', 'Service Name', 'service_name'),
    'Service Path': ('ImagePath', 'Service File Name', 'ServiceFileName', 'Image Path', 'service_file_name', 'image_path'),
    'Service Account': ('ServiceAccount', 'Service Account', 'ServiceStartName', 'AccountName', 'service_account'),
}


_IRFLOW_SUBJECT_USERNAME_IDS = {'4688', '1102'}


def _irflow_event_text(sheet, row):
    cols = {str(c.name).casefold(): c for c in sheet.columns}
    return '\n'.join(_irflow_value(cols[field], row) for field in
                     ('extra', 'desc', 'short', 'message') if field in cols)


def _irflow_event_log_row(sheet, row):
    cols = {str(c.name).casefold(): c for c in sheet.columns}
    source = _irflow_value(cols['source'], row).strip().casefold() if 'source' in cols else ''
    if source in ('evt', 'evtx'):
        return True
    for field in ('sourcetype', 'format', 'parser'):
        if field in cols:
            value = _irflow_value(cols[field], row).casefold()
            if 'evtx' in value or 'windows event log' in value or 'winevt' in value:
                return True
    return False


def _irflow_event_id(sheet, row):
    # Event IDs only have meaning in a Windows Event Log context.
    if not _irflow_event_log_row(sheet, row):
        return ''
    cols = {str(c.name).casefold(): c for c in sheet.columns}
    for field in ('event_identifier', 'event_id', 'eventid', 'event identifier', 'event id'):
        if field in cols:
            raw = _irflow_value(cols[field], row).strip()
            if re.fullmatch(r'\d{3,6}', raw):
                return raw
    text = _irflow_event_text(sheet, row)
    match = _IRFLOW_EVENT_ID_RE.search(text) or _IRFLOW_EVENT_XML_RE.search(text)
    return match.group(1) if match else ''


def _irflow_extract_event_field(sheet, row, display):
    cols = {str(c.name).casefold(): c for c in sheet.columns}
    aliases = _IRFLOW_FIELD_NAMES[display]
    if display == 'Username' and _irflow_event_id(sheet, row) in _IRFLOW_SUBJECT_USERNAME_IDS:
        aliases = ('SubjectUserName', 'Subject User Name') + aliases
    for alias in aliases:
        column = cols.get(alias.casefold())
        if column is not None:
            value = _irflow_value(column, row).strip()
            if value and value != '-':
                return value
    text = _irflow_event_text(sheet, row)
    for alias in aliases:
        key = re.escape(alias)
        # Windows EVTX XML and common flattened key=value/JSON-style output.
        xml = re.search(r'<Data\s+Name=["\']' + key +
                        r'["\']\s*>([^<]*)</Data>', text, re.IGNORECASE)
        if xml:
            return xml.group(1).strip()
        keyval = re.search(
            r'(?<![\w])(?:["\']' + key + r'["\']|' + key +
            r')\s*[:=]\s*(?:["\']([^"\'\r\n]*)["\']|([^,;\r\n]+))',
            text, re.IGNORECASE,
        )
        if keyval:
            value = (keyval.group(1) or keyval.group(2) or '').strip()
            if value and value != '-':
                return value
    return ''


def _irflow_open_analysis_view(sheet, event_id):
    event_id = str(event_id).strip()
    if not re.fullmatch(r'\d{3,6}', event_id):
        vd.warning('Enter a numeric Windows Event ID (3-6 digits)')
        return None
    if _irflow_detect_col(sheet)[0] is None:
        vd.warning('IRFlow views require a recognized supertimeline')
        return None
    matched = [row for row in sheet.rows if _irflow_event_id(sheet, row) == event_id]
    if not matched:
        vd.warning(f'No confirmed Windows Event ID {event_id} records found')
        return None
    title, fields = IRFLOW_ANALYSIS_VIEWS.get(event_id, ('Windows Event ' + event_id, ('Username',)))
    view = _irflow_copy_sheet(sheet)
    view._irflow_source_sheet = getattr(sheet, '_irflow_source_sheet', sheet)
    view.name = sheet.name + '_' + title.lower().replace(' ', '_')
    view.rows = matched
    visible = {'datetime', 'date', 'time', 'timezone', 'host', 'hostname',
               'tags', 'comment', 'desc', 'source'}
    for col in view.columns:
        if str(col.name).casefold() not in visible:
            col.hidden = True
    position = 1 if any(str(c.name).casefold() == 'datetime' for c in view.columns) else 0
    fields = ('Event ID',) + fields
    for offset, field in enumerate(fields):
        def getter(col, row, field=field):
            if field == 'Event ID':
                return _irflow_event_id(sheet, row)
            return _irflow_extract_event_field(sheet, row, field)
        view.addColumn(Column(field, type=str, getter=getter, width=24),
                       index=position + offset)
    view.hasBeenModified = False
    vd.push(view)
    vd.status(f'Experimental view: {len(matched)} matching event {event_id} records')
    return view


# Direct VisiData commands, independent of Kitty keypad mappings.
# Alt+0..9 are reserved for switching sheets; use the available gz prefix.
for _num, _eid in enumerate(('4624', '4625', '4688', '7045', '1102'), start=1):
    TableSheet.addCommand('gz' + str(_num), 'open-irflow-event-' + _eid,
                          '_irflow_open_analysis_view(sheet, "' + _eid + '")',
                          'Open experimental Windows Event ID ' + _eid + ' analysis view')
TableSheet.addCommand('gz0', 'open-irflow-event-input',
                      '_irflow_open_analysis_view(sheet, vd.input("Windows Event ID: "))',
                      'Open experimental Windows Event ID analysis view')
vd.addGlobals(_irflow_open_analysis_view=_irflow_open_analysis_view)
