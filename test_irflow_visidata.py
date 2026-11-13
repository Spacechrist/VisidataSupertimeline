"""Offline behavioral tests for the IRFlow VisiData color rules.

Run with: python -m unittest discover -v
VisiData is stubbed; these do not validate terminal rendering.
"""
import importlib.util
import sys
import types
import unittest
from copy import copy
from pathlib import Path
from unittest.mock import patch

stub = types.ModuleType("visidata")
stub.options = types.SimpleNamespace(theme="default", color_default="white on black")

class FakeVD:
    def __init__(self):
        self.warnings = []
        self.views = []
        self.statuses = []
        self.globals = {}

    def warning(self, message):
        self.warnings.append(message)

    def status(self, message):
        self.statuses.append(message)

    def push(self, view):
        self.views.append(view)

    def addGlobals(self, **kwargs):
        self.globals.update(kwargs)

stub.vd = FakeVD()

class TableSheet:
    colorizers = []
    commands = []

    @classmethod
    def addCommand(cls, *args):
        cls.commands.append(args)

    @classmethod
    def after(cls, func):
        setattr(cls, "_after_" + func.__name__, func)
        return func


class Column:
    def __init__(self, name, getter=None, setter=None, width=None, type=str):
        self.name = name
        self.getter = getter
        self.setter = setter
        self.width = width
        self.hidden = False
        self.defer = False

    def getValue(self, row):
        return self.getter(self, row)

    def setValue(self, row, value, setModified=True):
        if self.setter is None:
            raise ValueError('readonly')
        self.setter(self, row, value)

class RowColorizer:
    def __init__(self, precedence, coloropt, func):
        self.precedence, self.coloropt, self.func = precedence, coloropt, func

stub.TableSheet = TableSheet
stub.RowColorizer = RowColorizer
stub.CellColorizer = RowColorizer
stub.Column = Column
sys.modules["visidata"] = stub

spec = importlib.util.spec_from_file_location(
    "irflow_visidata", Path(__file__).with_name("irflow_visidata.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Col:
    def __init__(self, name):
        self.name = name

    def getValue(self, row):
        return row.get(self.name, "")


class Sheet:
    def __init__(self, headers, rows, source=None):
        self.columns = [Col(n) for n in headers]
        self.rows = rows
        self.source = source
        self.name = 'supertimeline'
        self.hasBeenModified = False

    def __copy__(self):
        out = Sheet([], list(self.rows), self.source)
        out.columns = [copy(c) for c in self.columns]
        return out

    def addColumn(self, col, index=None):
        self.columns.insert(0 if index is None else index, col)
        self.hasBeenModified = True


PLASO_COLS = ["date", "time", "macb", "source", "sourcetype", "type"]
NONPLASO_COLS = ["Timestamp", "Macb", "SourceName", "LongDescription", "FileName"]


class Tests(unittest.TestCase):
    def test_palette_exact_source_hex(self):
        self.assertEqual(mod.IRFLOW_DARK_HEX[0], ("#1a3a2a", "#6ee7b7"))
        self.assertEqual(len(mod.IRFLOW_DARK_HEX), 16)
        self.assertEqual(len(mod.IRFLOW_LIGHT_HEX), 16)

    def test_kitty_dux_theme_defaults(self):
        self.assertEqual(mod.IRFLOW_THEME, "light")
        self.assertEqual(stub.options.theme, "asciimono")
        self.assertEqual(mod.IRFLOW_BASE_COLOR, 'white on 242')
        self.assertEqual(stub.options.color_default, mod.IRFLOW_BASE_COLOR)

    def test_asciimono_cursor_only_highlights_active_cell(self):
        theme = {
            'color_current_row': 'reverse',
            'color_current_col': 'bold',
            'color_current_cell': '',
            'color_longname': '',
        }
        mod._irflow_configure_asciimono_theme(theme)
        self.assertEqual(theme['color_current_row'], '')
        self.assertEqual(theme['color_current_col'], '')
        self.assertEqual(theme['color_current_cell'], 'bold reverse')
        self.assertEqual(theme['color_default'], mod.IRFLOW_BASE_COLOR)
        self.assertNotIn('color_longname', theme)
        self.assertIn('color_longname_status', theme)
        self.assertIn('color_longname_guide', theme)

    def test_tle_black_deletion_background_distinct_from_canvas(self):
        self.assertEqual(mod.IRFLOW_TLE_PLASO_COLORS['DeletedData'],
                         ('#000000', '#FFFFFF'))
        self.assertEqual(mod.IRFLOW_BASE_COLOR, 'white on 242')
        self.assertNotEqual(mod._irflow_xterm_256('#000000'), 242)

    def test_tle_light_background_has_dark_foreground_in_terminal(self):
        for category in ('LogFile', 'Device|USBUsage', 'FileOpening',
                         'FolderOpening'):
            bg, original_fg = mod.IRFLOW_TLE_PLASO_COLORS[category]
            self.assertIsNone(original_fg)
            self.assertEqual(mod._IRFLOW_TLE_TERMINAL_COLORS[category],
                             mod._irflow_term_color(bg, '#000000'))
        self.assertEqual(mod.IRFLOW_TLE_PLASO_COLORS['Execution'],
                         ('#CA0002', '#FFFFFF'))
        self.assertEqual(mod._IRFLOW_TLE_TERMINAL_COLORS['Execution'],
                         mod._irflow_term_color('#CA0002', '#FFFFFF'))
        self.assertEqual(mod._IRFLOW_TLE_TERMINAL_COLORS['WebHistory'],
                         mod._irflow_term_color('#FFC000', '#000000'))

    def test_timeline_requires_exact_columns(self):
        s = Sheet(["source", "sourcetype", "type"], [{"source": "A"}])
        self.assertIsNone(mod._irflow_color_row(s, None, s.rows[0], None))

    def test_non_plaso_irflow_source_first_seen(self):
        s = Sheet(NONPLASO_COLS, [
            {"SourceName": "EVT"}, {"SourceName": "FILE"}, {"SourceName": "evt"}
        ])
        c1 = mod._irflow_color_row(s, None, s.rows[0], None)
        c2 = mod._irflow_color_row(s, None, s.rows[1], None)
        c3 = mod._irflow_color_row(s, None, s.rows[2], None)
        self.assertEqual(c1, mod._irflow_term_color(*mod.IRFLOW_LIGHT_HEX[0]))
        self.assertEqual(c2, mod._irflow_term_color(*mod.IRFLOW_LIGHT_HEX[1]))
        self.assertEqual(c3, c1)

    def test_non_plaso_irflow_palette_cycles_after_16(self):
        s = Sheet(NONPLASO_COLS, [
            {"SourceName": f"SRC{i}"} for i in range(18)
        ])
        self.assertEqual(
            mod._irflow_color_row(s, None, s.rows[0], None),
            mod._irflow_color_row(s, None, s.rows[16], None),
        )

    def test_non_plaso_irflow_first_150_only(self):
        s = Sheet(NONPLASO_COLS, [
            {"SourceName": f"SRC{i}"} for i in range(152)
        ])
        self.assertIsNotNone(mod._irflow_color_row(s, None, s.rows[149], None))
        self.assertIsNone(mod._irflow_color_row(s, None, s.rows[150], None))

    def test_non_plaso_irflow_first_window_only(self):
        rows = [{"SourceName": "EVT"}] * 5000 + [{"SourceName": "LATE"}]
        s = Sheet(NONPLASO_COLS, rows)
        self.assertIsNotNone(mod._irflow_color_row(s, None, rows[0], None))
        self.assertIsNone(mod._irflow_color_row(s, None, rows[-1], None))

    def test_rows_remain_unchanged(self):
        r = {"source": "EVT", "desc": "Prefetch {"}
        s = Sheet(PLASO_COLS + ["desc"], [r])
        mod._irflow_tle_color_cell(s, next(c for c in s.columns if c.name == "desc"), r, None)
        self.assertEqual(r, {"source": "EVT", "desc": "Prefetch {"})

    def test_non_plaso_custom_rule_overrides(self):
        mod.IRFLOW_CUSTOM_RULES[:] = [
            ("SourceName", "contains", "EV", "#7f1d1d", "#fca5a5")
        ]
        try:
            s = Sheet(NONPLASO_COLS, [{"SourceName": "EVT"}])
            got = mod._irflow_color_row(s, None, s.rows[0], None)
            expected = mod._irflow_term_color("#7f1d1d", "#fca5a5")
            self.assertEqual(got, expected)
        finally:
            mod.IRFLOW_CUSTOM_RULES[:] = []

    def test_non_plaso_presets_not_enabled_by_default(self):
        s = Sheet(
            NONPLASO_COLS + ["Process"],
            [{"SourceName": "EVT", "Process": "powershell.exe"}],
        )
        self.assertEqual(
            mod._irflow_color_row(s, None, s.rows[0], None),
            mod._irflow_term_color(*mod.IRFLOW_LIGHT_HEX[0]),
        )

    def test_tle_exact_seven_categories_and_hex(self):
        self.assertEqual(mod.IRFLOW_TLE_PLASO_COLORS, {
            'LogFile': ('#F3F1EA', None),
            'DeletedData': ('#000000', '#FFFFFF'),
            'Device|USBUsage': ('#548DD4', None),
            'Execution': ('#CA0002', '#FFFFFF'),
            'FileOpening': ('#92D050', None),
            'FolderOpening': ('#00B050', None),
            'WebHistory': ('#FFC000', '#000000'),
        })

    def test_tle_original_super_timeline_fixture(self):
        # From EricZimmerman/TLEFilePlugins/TLEFile.Test/TestFiles/SuperTimelinePlaso.csv
        fixture = [
            ("C:/Users/a/x.lnk", "FILE", "NTFS $MFT", "FileOpening"),
            ("https://example.com visited", "WEBHIST", "Chrome History", "WebHistory"),
            ("Event Level: 4", "EVT", "WinEVTX", "LogFile"),
        ]
        for description, source, sourcetype, expected in fixture:
            with self.subTest(description=description):
                self.assertEqual(
                    mod._irflow_tle_plaso_category(description, source, sourcetype),
                    expected)

    def test_tle_plaso_classification_examples(self):
        # All seven source categories and representative C# conditions.
        fixture = [
            ("DELETED file", "FILE", "", "DeletedData"),
            ("$Recycle.Bin", "FILE", "", "DeletedData"),
            ("http://EXAMPLE.com", "WEB", "", "WebHistory"),
            ("VISITED", "WEBHIST", "", "WebHistory"),
            ("Cookie", "FILE", "", "WebHistory"),
            ("BagMRU", "REG", "", "FolderOpening"),
            ("ordinary entry", "FILE", "File entry shell item", "FolderOpening"),
            ("ShellNoRoam/Bags", "REG", "", "FolderOpening"),
            ("RecentDocs", "REG", "", "FileOpening"),
            ("file.LNK", "FILE", "", "FileOpening"),
            ("Recently opened file", "FILE", "", "FileOpening"),
            ("MountPoints2", "REG", "", "Device|USBUsage"),
            ("Enum/USBSTOR/Disk", "REG", "", "Device|USBUsage"),
            ("Event Level: 4", "EVT", "", "LogFile"),
            ("ordinary", "EVT", "", "LogFile"),
            ("Prefetch {", "FILE", "", "Execution"),
            ("AppCompatCache", "REG", "", "Execution"),
            ("UserAssist key", "REG", "", "Execution"),
            ("C:/Windows/PREFETCH/APP.PF", "FILE", "", "Execution"),
            ("[PROCESS] created", "FILE", "", "Execution"),
        ]
        for description, source, sourcetype, expected in fixture:
            with self.subTest(description=description):
                self.assertEqual(
                    mod._irflow_tle_plaso_category(description, source, sourcetype),
                    expected)

    def test_tle_case_sensitive_and_case_insensitive_matching(self):
        self.assertIsNone(mod._irflow_tle_plaso_category("prefetch", "file", ""))
        self.assertIsNone(mod._irflow_tle_plaso_category("cookie", "file", ""))
        self.assertEqual(mod._irflow_tle_plaso_category("HTTPS://EXAMPLE.COM", "", ""),
                         "WebHistory")
        self.assertEqual(mod._irflow_tle_plaso_category("FILE.pF", "", ""),
                         "Execution")
        self.assertIsNone(mod._irflow_tle_plaso_category("visited", "webhist", ""))
        self.assertIsNone(mod._irflow_tle_plaso_category(None, "EVT", ""))

    def test_tle_boolean_and_source_exceptions(self):
        self.assertIsNone(mod._irflow_tle_plaso_category("URL", "FILE", ""))
        self.assertEqual(mod._irflow_tle_plaso_category("URL", "file", ""),
                         "WebHistory")
        self.assertIsNone(mod._irflow_tle_plaso_category("LSO", "REG", ""))
        self.assertEqual(mod._irflow_tle_plaso_category("LSO", "reg", ""),
                         "WebHistory")
        self.assertIsNone(mod._irflow_tle_plaso_category("Recently", "FILE", "Firefox"))
        self.assertIsNone(mod._irflow_tle_plaso_category("file://", "FILE", "Firefox"))
        self.assertEqual(mod._irflow_tle_plaso_category("file://", "FILE", "Other"),
                         "FileOpening")

    def test_tle_rules_overwrite_in_original_order(self):
        self.assertEqual(mod._irflow_tle_plaso_category("BagMRU File Opened", "FILE", ""),
                         "FileOpening")
        self.assertEqual(mod._irflow_tle_plaso_category("URL Event Level:", "EVT", ""),
                         "LogFile")
        self.assertEqual(mod._irflow_tle_plaso_category("RECYCLE Prefetch", "FILE", ""),
                         "Execution")
        self.assertEqual(mod._irflow_tle_plaso_category("USB Prefetch", "FILE", ""),
                         "Execution")

    def test_tle_plaso_only_desc_cell_is_colored(self):
        row = {'source': 'FILE', 'sourcetype': 'WinPrefetch', 'desc': 'Prefetch {'}
        sheet = Sheet(PLASO_COLS + ['desc', 'extra'], [row])
        desc_col = next(c for c in sheet.columns if c.name == 'desc')
        extra_col = next(c for c in sheet.columns if c.name == 'extra')
        got = mod._irflow_tle_color_cell(sheet, desc_col, row, None)
        expected_bg = mod._irflow_xterm_256('#CA0002')
        expected_fg = mod._irflow_xterm_256('#FFFFFF')
        self.assertEqual(got, f'{expected_fg} on {expected_bg}')
        self.assertIsNone(mod._irflow_tle_color_cell(sheet, extra_col, row, None))
        self.assertIsNone(mod._irflow_color_row(sheet, None, row, None))
        self.assertIsNotNone(got)

    def test_tle_null_desc_does_not_color_even_evtx(self):
        row = {'source': 'EVT', 'sourcetype': 'WinEVTX', 'desc': None}
        sheet = Sheet(PLASO_COLS + ['desc'], [row])
        col = next(c for c in sheet.columns if c.name == 'desc')
        self.assertIsNone(mod._irflow_tle_color_cell(sheet, col, row, None))

    def test_tle_no_event_id_specific_extensions(self):
        row = {'source': 'EVT', 'sourcetype': 'WinEVTX', 'desc': 'Event ID: 4688'}
        sheet = Sheet(PLASO_COLS + ['desc'], [row])
        col = next(c for c in sheet.columns if c.name == 'desc')
        self.assertEqual(mod._irflow_tle_plaso_category(row['desc'], row['source'],
                          row['sourcetype']), 'LogFile')
        self.assertEqual(
            mod._irflow_tle_color_cell(sheet, col, row, None),
            mod._IRFLOW_TLE_TERMINAL_COLORS['LogFile'])

    def test_tle_colors_late_rows_without_first_seen_sampling(self):
        rows = [{'source': 'FILE', 'sourcetype': '', 'desc': 'plain'}] * 5010
        rows.append({'source': 'FILE', 'sourcetype': '', 'desc': 'Prefetch {'})
        sheet = Sheet(PLASO_COLS + ['desc'], rows)
        col = next(c for c in sheet.columns if c.name == 'desc')
        self.assertEqual(
            mod._irflow_tle_color_cell(sheet, col, rows[-1], None),
            mod._IRFLOW_TLE_TERMINAL_COLORS['Execution'])

    def test_datetime_merges_without_evidence_changes(self):
        row = {"date": "01/01/2023", "time": "11:42:10", "source": "FILE"}
        s = Sheet(PLASO_COLS, [row])
        TableSheet._after_afterLoad(s)
        self.assertEqual(s.columns[0].name, "datetime")
        self.assertEqual(s.columns[0].getValue(row), "01/01/2023 11:42:10")
        self.assertEqual(row["date"], "01/01/2023")
        self.assertEqual(row["time"], "11:42:10")
        self.assertFalse(s.hasBeenModified)
        self.assertTrue(next(c for c in s.columns if c.name == "date").hidden)
        self.assertTrue(next(c for c in s.columns if c.name == "time").hidden)

    def test_datetime_only_on_plaso(self):
        s = Sheet(["date", "time", "source"], [{"date": "01/01/2023", "time": "11:42:10"}])
        TableSheet._after_afterLoad(s)
        self.assertFalse(any(c.name == "datetime" for c in s.columns))

    def test_datetime_not_duplicated_on_reload(self):
        s = Sheet(PLASO_COLS, [{"date": "01/01/2023", "time": "11:42:10"}])
        TableSheet._after_afterLoad(s)
        TableSheet._after_afterLoad(s)
        self.assertEqual(sum(c.name == "datetime" for c in s.columns), 1)

    def test_event_id_detection_requires_event_log_source(self):
        s = Sheet(PLASO_COLS + ['extra'], [
            {'source': 'EVT', 'extra': 'Event ID: 4624, TargetUserName: alice'},
            {'source': 'LOG', 'extra': 'Event ID: 4624'},
            {'source': 'EVT', 'extra': 'Text mentions 4624'},
            {'source': 'EVT', 'extra': 'Event ID: 14624'},
        ])
        self.assertEqual([mod._irflow_event_id(s, r) for r in s.rows],
                         ['4624', '', '', '14624'])

    def test_4624_analysis_view_extracts_username_and_ip(self):
        rows = [
            {'source': 'EVT', 'extra': 'Event ID: 4624, TargetUserName: alice, IpAddress: 192.0.2.10, LogonType: 3'},
            {'source': 'EVT', 'extra': 'Event ID: 4625, TargetUserName: bob'},
        ]
        s = Sheet(PLASO_COLS + ['extra'], rows)
        v = mod._irflow_open_analysis_view(s, '4624')
        self.assertEqual(len(v.rows), 1)
        self.assertEqual(len(s.rows), 2)
        self.assertIsNot(v.columns, s.columns)
        self.assertEqual(next(c for c in v.columns if c.name == 'Event ID').getValue(rows[0]), '4624')
        self.assertEqual(next(c for c in v.columns if c.name == 'Username').getValue(rows[0]), 'alice')
        self.assertEqual(next(c for c in v.columns if c.name == 'Source IP').getValue(rows[0]), '192.0.2.10')
        self.assertEqual(next(c for c in v.columns if c.name == 'Logon Type').getValue(rows[0]), '3')

    def test_analysis_view_xml_and_missing_fields(self):
        r = {'source': 'EVT', 'extra': '<EventID>4624</EventID><Data Name="TargetUserName">alice</Data>'}
        s = Sheet(PLASO_COLS + ['extra'], [r])
        v = mod._irflow_open_analysis_view(s, '4624')
        self.assertEqual(next(c for c in v.columns if c.name == 'Username').getValue(r), 'alice')
        self.assertEqual(next(c for c in v.columns if c.name == 'Source IP').getValue(r), '')

    def test_process_4688_extracts_subject_username_and_command(self):
        row = {'source': 'EVT', 'extra':
               'Event ID: 4688, SubjectUserName: analyst, NewProcessName: cmd.exe, '
               'ProcessCommandLine: cmd.exe /c whoami'}
        s = Sheet(PLASO_COLS + ['extra'], [row])
        v = mod._irflow_open_analysis_view(s, '4688')
        self.assertEqual(next(c for c in v.columns if c.name == 'Username').getValue(row), 'analyst')
        self.assertEqual(next(c for c in v.columns if c.name == 'Process Name').getValue(row), 'cmd.exe')
        self.assertEqual(next(c for c in v.columns if c.name == 'Command Line').getValue(row),
                         'cmd.exe /c whoami')

    def test_security_1102_extracts_subject_username(self):
        row = {'source': 'EVT', 'extra': 'Event ID: 1102, SubjectUserName: administrator'}
        s = Sheet(PLASO_COLS + ['extra'], [row])
        v = mod._irflow_open_analysis_view(s, '1102')
        self.assertEqual(next(c for c in v.columns if c.name == 'Username').getValue(row),
                         'administrator')

    def test_plaso_snake_case_properties(self):
        row = {
            'source': 'EVT',
            'event_identifier': '4624',
            'target_user_name': 'eve',
            'ip_address': '198.51.100.17',
            'logon_type': '10',
        }
        s = Sheet(PLASO_COLS +
                  ['event_identifier', 'target_user_name', 'ip_address', 'logon_type'], [row])
        v = mod._irflow_open_analysis_view(s, '4624')
        self.assertIsNotNone(v)
        self.assertEqual(next(c for c in v.columns if c.name == 'Username').getValue(row), 'eve')
        self.assertEqual(next(c for c in v.columns if c.name == 'Source IP').getValue(row),
                         '198.51.100.17')
        self.assertEqual(next(c for c in v.columns if c.name == 'Logon Type').getValue(row), '10')

    def test_filtered_view_preserves_tle_description_colors(self):
        first = {'source': 'FILE', 'extra': '', 'desc': 'ordinary'}
        second = {'source': 'EVT', 'extra': 'Event ID: 4624', 'desc': 'Event Level: 4'}
        original = Sheet(PLASO_COLS + ['desc', 'extra'], [first, second])
        desc_col = next(c for c in original.columns if c.name == 'desc')
        expected = mod._irflow_tle_color_cell(original, desc_col, second, None)
        view = mod._irflow_open_analysis_view(original, '4624')
        view_desc = next(c for c in view.columns if c.name == 'desc')
        got = mod._irflow_tle_color_cell(view, view_desc, second, None)
        self.assertEqual(got, expected)

    def test_annotation_columns_precede_extra(self):
        columns = PLASO_COLS + ['desc', 'extra', 'more']
        sheet = Sheet(columns, [{'source': 'EVT', 'extra': 'event details'}])
        state = {'indices': {}, 'verified': set(), 'entries': {}}
        with patch.object(mod, '_irflow_annotation_state', return_value=state):
            TableSheet._after_afterLoad(sheet)
        names = [c.name for c in sheet.columns]
        extra_index = names.index('extra')
        self.assertEqual(names[extra_index - 2:extra_index + 1],
                         ['Tags', 'Comment', 'extra'])
        self.assertEqual(names[-1], 'more')
        self.assertFalse(sheet.hasBeenModified)

    def test_annotation_columns_append_without_extra(self):
        sheet = Sheet(PLASO_COLS + ['desc'], [{'source': 'EVT'}])
        state = {'indices': {}, 'verified': set(), 'entries': {}}
        with patch.object(mod, '_irflow_annotation_state', return_value=state):
            TableSheet._after_afterLoad(sheet)
        self.assertEqual([c.name for c in sheet.columns][-2:], ['Tags', 'Comment'])

    def test_analysis_view_shortcuts_registered(self):
        keys = [c[0] for c in TableSheet.commands]
        self.assertTrue(all('gz' + str(x) in keys for x in range(1, 6)))
        self.assertIn('gz0', keys)
        self.assertNotIn('Alt+1', keys)
        self.assertNotIn('Alt+0', keys)

    def test_unknown_event_id_reports_no_records(self):
        stub.vd.warnings.clear()
        s = Sheet(PLASO_COLS + ['extra'], [{'source':'EVT', 'extra':'Event ID: 4624'}])
        self.assertIsNone(mod._irflow_open_analysis_view(s, '4625'))
        self.assertTrue(stub.vd.warnings)


if __name__ == "__main__":
    unittest.main()
