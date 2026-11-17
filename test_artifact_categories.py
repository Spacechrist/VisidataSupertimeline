"""Pure catalog checks and integration tests against real VisiData in subprocesses."""
import csv
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from dfir_catalog import catalog_zip, describe_report

ROOT=Path(__file__).parent


def write_zip(path,reports):
    with zipfile.ZipFile(path,'w') as z:
        for name,content in reports.items():z.writestr(name,content)


class CatalogTests(unittest.TestCase):
    def test_profiles_are_dynamic_not_fixed_case_usernames(self):
        info=describe_report('evidence_SBECmd_jane.doe_UsrClass.dat_ShellBags.csv',['BagPath'])
        self.assertEqual(info['Profile'],'jane.doe')
        self.assertEqual(info['Parser'],'EZTools - File and Folder')
        self.assertEqual(describe_report('evidence_SQLECmd_AnotherUser_ActivitiesCache_Activities.csv')['Profile'],'AnotherUser')

    def test_pairs_empty_reports_and_unpaired_raw_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'reports.zip'
            reports={'x_SRUM_SRUDB_NetworkData_Raw.csv':'AutoIncId,AppId,UserId,TimeStamp\n1,2,3,4\n',
                'x_SRUM_SRUDB_NetworkData_Resolved.csv':'AutoIncId,AppId,UserId,TimeStamp,AppIdResolved\n1,2,3,4,a\n',
                'x_SRUM_SRUDB_EnergyUsage_Raw.csv':'AutoIncId,AppId,UserId,TimeStamp\n',
                'x_SRUM_SRUDB_System_MSysObjects_Raw.csv':'Name\nSystem\n',
                'x_EvtxECmd.csv':'EventId,Channel\n4624,Security\n',
                'x_EvtxECmd_timesketch.csv':'datetime,timestamp_desc,EventId,Channel\nt,Creation,4624,Security\n'}
            write_zip(path,reports);before=path.read_bytes();catalog={r['Report']:r for r in catalog_zip(path)}
            self.assertEqual(catalog['x_SRUM_SRUDB_NetworkData_Raw.csv']['View'],'Alternate')
            self.assertEqual(catalog['x_SRUM_SRUDB_NetworkData_Resolved.csv']['View'],'Primary')
            self.assertEqual(catalog['x_SRUM_SRUDB_EnergyUsage_Raw.csv']['View'],'Primary')
            self.assertEqual(catalog['x_SRUM_SRUDB_EnergyUsage_Raw.csv']['State'],'Empty')
            self.assertEqual(catalog['x_SRUM_SRUDB_System_MSysObjects_Raw.csv']['View'],'Reference')
            self.assertEqual(catalog['x_EvtxECmd.csv']['View'],'Alternate')
            self.assertEqual(path.read_bytes(),before)


class RealVisiDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if subprocess.run([sys.executable,'-c','import visidata'],capture_output=True).returncode:
            raise unittest.SkipTest('Real VisiData is required')

    def check(self,script):
        process=subprocess.run([sys.executable,'-c',textwrap.dedent(script)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)

    def test_zip_navigation_grouping_snapshot_isolation_and_reload(self):
        self.check('''
            import tempfile,zipfile
            from pathlib import Path
            from visidata import vd,Path as VDPath,Sheet
            import dfir_categories as d
            import artifact_categories as a
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'reports.zip'
                with zipfile.ZipFile(path,'w') as z:
                    z.writestr('e_SBECmd_jane_UsrClass.dat_ShellBags.csv','BagPath,ShellType,Value\\nBagMRU,Directory,Folder\\nBagMRU,Drive letter,C:\\\\\\n')
                    z.writestr('e_SBECmd_jane_NTUSER.DAT_ShellBags.csv','BagPath,ShellType,Value\\n')
                original=path.read_bytes()
                catalog=vd.openSource(VDPath(str(path)),filetype='dfirzip');catalog.reload();vd.sync();vd.push(catalog)
                assert len(catalog.rows)==2 and len(catalog.columns)==9
                catalog.reload();vd.sync();assert len(catalog.rows)==2 and len(catalog.columns)==9
                catalog.open_report();vd.sync();report=vd.activeSheet
                assert len(report.rows)==2 and len(report.columns)==3
                report.dfir_review_current();category=vd.activeSheet
                assert category.rows[0]['Rows']==2
                category.open_view();review=vd.activeSheet
                review.rows[0]['Value']='edited'
                assert report.rows[0]['Value']=='Folder'
                review.dfir_categories();assert vd.activeSheet._dfir_source_sheet is report
                group=a.ArtifactGroups(report,'EZTools - File and Folder','ShellType',category.records,category.original_columns)
                vd.push(group);group.open_group();assert len(vd.activeSheet.rows)==1
                assert path.read_bytes()==original
                assert Sheet('').getCommand('F5').longname!='dfir-zip-primary' if Sheet('').getCommand('F5') else True
        ''')

    def test_event_provider_guard_native_flags_and_wrong_parser_rejection(self):
        self.check('''
            from visidata import vd,Sheet,ColumnItem
            import dfir_categories
            import artifact_categories as a
            assert 'Authentication and logons' in a.row_categories('EVTXECmd',{'EventId':'4624','Channel':'Security'},'events.csv')
            assert a.row_categories('EVTXECmd',{'EventId':'4624','Channel':'Application','Provider':'unrelated'},'events.csv')==('Other event records',)
            flags=a.row_categories('MFTECmd',{'InUse':'False','IsDirectory':'True','SI<FN':'True'},'mft.csv')
            assert 'Unallocated records' in flags and 'Native SI<FN flag set' in flags
            assert a.truth('') is None and a.truth('False') is False
            source=Sheet('evidence_SRUM_SRUDB_NetworkData_Resolved.csv')
            for name in ['AutoIncId','AppId','UserId','TimeStamp','AppIdResolved']:
                source.addColumn(ColumnItem(name,name))
            source.rows=[dict(AutoIncId='1',AppId='2',UserId='3',TimeStamp='4',AppIdResolved='a')]
            menu=a.ArtifactCategories(source,'SRUM')
            assert any(r.get('field')=='AppIdResolved' for r in menu.rows)
            try: a.ArtifactCategories(source,'SQLECmd')
            except Exception: pass
            else: raise AssertionError('Wrong parser accepted')
        ''')

if __name__=='__main__':unittest.main()
