"""Integration checks in fresh interpreters, isolated from the timeline VisiData stub."""
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).parent


class ParserMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run([sys.executable, '-c', 'import visidata'], capture_output=True)
        if result.returncode:
            raise unittest.SkipTest('VisiData is not installed; integration tests require VisiData 3.5')

    def run_check(self, script):
        result = subprocess.run([sys.executable, '-c', textwrap.dedent(script)],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_csv_navigation_filters_and_source_isolation(self):
        self.run_check('''
            import csv
            from tempfile import TemporaryDirectory
            from pathlib import Path
            from visidata import vd, Path as VDPath, Sheet
            import dfir_categories as d
            columns = ['Entry', 'Category', 'Enabled', 'Signer', 'Image Path']
            rows = [
                ['', 'Services', '', '', ''],
                ['unverified-enabled', 'Services', 'enabled', '', 'C:\\service.exe'],
                ['signed', 'Services', 'enabled', '(Verified) Vendor', 'C:\\signed.exe'],
                ['disabled', 'Services', 'disabled', '', 'C:\\disabled.exe'],
                ['unknown-enable', 'Services', '', '', ''],
                ['missing', 'Drivers', 'enabled', '', 'File not found: driver.sys'],
                ['task', 'Tasks', 'disabled', '(Verified) Vendor', 'C:\\task.exe'],
                ['dll', 'Known DLLs', 'enabled', '', 'C:\\example.dll'],
            ]
            with TemporaryDirectory() as tmp:
                path = Path(tmp) / 'synthetic.csv'
                with path.open('w', newline='') as f:
                    writer = csv.writer(f); writer.writerow(columns); writer.writerows(rows)
                original = path.read_bytes()
                source = vd.openSource(VDPath(str(path)))
                source.reload(); vd.sync(); vd.push(source)
                def press(key):
                    sheet = vd.activeSheet
                    command = sheet.getCommand(key)
                    assert command, key
                    assert not sheet.execCommand(command.longname)
                    vd.sync()
                press('F2')
                assert len(vd.activeSheet.rows) == 14
                press('F2')  # repeated overview must retain the original CSV source
                press('Enter')
                assert vd.activeSheet.name == 'Autorunsc - Categories'
                assert vd.activeSheet.rows[0]['All'] == 4
                press('Enter'); press('F5'); press('F6')
                review = vd.activeSheet
                assert review.name == 'Autorunsc - Services - Enabled + Unverified'
                assert [r['Entry'] for r in review.rows] == ['unverified-enabled']
                press('2'); press('F7'); assert len(review.rows) == 1
                press('3'); assert not review.rows
                press('F8'); assert len(review.rows) == 1
                press('4'); press('F6'); assert review.rows[0]['Entry'] == 'dll'
                press('0'); press('F8'); assert len(review.rows) == 7
                review.rows[0]['Entry'] = 'edited-copy'
                assert source.rows[1][0] == 'unverified-enabled'
                assert path.read_bytes() == original
                assert Sheet('').getCommand('e').longname == 'edit-cell'
                assert Sheet('').getCommand('1') is None
        ''')

    def test_existing_binding_native_menu_and_pending_parser(self):
        self.run_check('''
            from visidata import vd, Sheet
            Sheet.addCommand('F2', 'test-existing-f2', 'status("existing")')
            import dfir_categories as d
            sheet = Sheet('ordinary CSV')
            vd.push(sheet)
            assert sheet.getCommand('F2').longname == 'test-existing-f2'
            for name in d.PARSERS:
                assert sheet.getMenuItem(['Category', name])
            assert not sheet.execCommand('dfir-parser-supertimeline')
            assert vd.activeSheet.name == 'Supertimeline - Setup'
            assert 'not been implemented' in vd.activeSheet.rows[1]['Details']
            assert vd.activeSheet._dfir_source_sheet is sheet
            try:
                d.register_parser('Autorunsc', 'duplicate', 'duplicate')
            except ValueError:
                pass
            else:
                raise AssertionError('Duplicate parser was accepted')
            Sheet.addCommand('', 'dfir-parser-collision', 'status("existing")')
            try:
                d.register_parser('Collision', 'collision', 'duplicate command')
            except ValueError:
                pass
            else:
                raise AssertionError('Existing command was overwritten')
        ''')

    def test_coexists_with_timeline_extension_and_repeated_import(self):
        self.run_check('''
            from visidata import vd, TableSheet
            from pathlib import Path
            path = Path('irflow_visidata.py')
            exec(compile(path.read_text(), str(path), 'exec'), vd.getGlobals())
            sheet = TableSheet('timeline')
            before = {key: sheet.getCommand(key).longname for key in ['gz1', 'gz0', 'gzEnter']}
            import dfir_categories
            import dfir_categories
            assert {key: sheet.getCommand(key).longname for key in before} == before
            assert len([m for m in vd.menus if m.title == 'Category']) == 1
            assert sheet.getMenuItem(['Category', 'Autorunsc'])
        ''')


if __name__ == '__main__':
    unittest.main()
