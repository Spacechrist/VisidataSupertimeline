"""Schema-aware, read-only VisiData category views for the supplied CSV exports."""
import csv
import io
import re
import zipfile
from pathlib import Path as LocalPath
from visidata import Sheet, ColumnItem, vd
from dfir_catalog import catalog_zip, describe_report

READY = ('EVTXECmd', 'MFTECmd', 'RECmd', 'EZTools - Execution',
         'EZTools - File and Folder', 'SQLECmd', 'SRUM', 'Hayabusa', 'Chainsaw')
GROUP_FIELDS = {
    'EVTXECmd': ('Channel', 'Provider', 'EventId', 'Computer', 'UserId'),
    'MFTECmd': ('Extension', 'ParentPath', 'NameType', 'UpdateReasons', 'InUse'),
    'RECmd': ('Category', 'HivePath', 'HiveType', 'BatchKeyPath', 'UserName', 'StartMode', 'ServiceType'),
    'EZTools - Execution': ('ExecutableName', 'AppIdDescription', 'DriverCompany', 'Class', 'Executed', 'FromSlack'),
    'EZTools - File and Folder': ('ShellType', 'HasExplored', 'AppIdDescription', 'SourceFile'),
    'SQLECmd': ('ActivityType', 'Platform', 'PackageName', 'AppId', 'IsLocalOnly'),
    'SRUM': ('UserIdResolved', 'AppIdResolved', 'provider', 'UserId', 'AppId'),
    'Hayabusa': ('Level', 'Channel', 'EventID', 'Computer', 'RuleFile', 'MitreTactics'),
    'Chainsaw': ('detections', 'Computer', 'computer', 'Event ID', 'event id', 'User', 'username'),
}
NOTES = {
    'MFTECmd': 'Native allocation and SI/FN flags are review categories, not proof of deletion or timestomping.',
    'RECmd': 'Use native Category values in batch reports. Detail reports retain artifact-specific fields and timestamp meanings.',
    'EZTools - Execution': 'Prefetch, inventory, Shimcache and LNK records have different evidentiary meanings; category membership is not a verdict.',
    'EZTools - File and Folder': 'Shellbag profile labels identify source hives; header-only reports contain no recorded rows.',
    'SQLECmd': 'ActivityPackages are associations, not additional executions. Preserve the source profile and Activity IDs.',
    'SRUM': 'Prefer resolved providers for review; raw providers and ESE system tables remain available separately.',
    'EVTXECmd': 'Event categories qualify event IDs by channel/provider. Native and Timesketch versions overlap.',
    'Hayabusa': 'Rule detections require investigation; severity is a tool label, not confirmation of compromise.',
    'Chainsaw': 'Rule matches require investigation; a detection is not confirmation of compromise.',
}


def truth(value):
    text = str(value).strip().casefold()
    return True if text in ('true', '1', 'yes') else False if text in ('false', '0', 'no') else None


def source_name(sheet):
    return getattr(sheet, '_dfir_report_name', '') or LocalPath(str(getattr(sheet, 'source', '') or sheet.name)).name


def infer_parser(name, columns):
    info = describe_report(name, columns)
    parser = info['Parser']
    c = set(columns)
    valid = {
        'EVTXECmd': {'EventId', 'Channel'} <= c,
        'MFTECmd': {'EntryNumber', 'InUse', 'FileName'} <= c or {'UpdateReasons', 'UpdateTimestamp'} <= c,
        'RECmd': 'BatchKeyPath' in c or {'HivePath', 'Category', 'KeyPath'} <= c,
        'EZTools - Execution': ({'ExecutableName', 'RunCount'} <= c or 'CacheEntryPosition' in c
            or {'SourceFile', 'TargetCreated'} <= c or info['Tool'] == 'AmcacheParser' and bool(c & {'KeyName', 'SHA1'})),
        'EZTools - File and Folder': ({'BagPath', 'ShellType'} <= c or {'AppIdDescription', 'TargetCreated'} <= c
            or bool(c & {'DeletedOn', 'DeletionTime', 'CachedFilePath'})),
        'SQLECmd': 'SourceFile' in c and bool(c),
        'SRUM': {'AutoIncId', 'AppId', 'UserId', 'TimeStamp'} <= c or info['Representation'] == 'System table' and bool(c),
        'Hayabusa': {'EventID', 'RuleFile', 'Level'} <= c,
        'Chainsaw': 'detections' in c,
    }
    if parser != 'Unknown': return parser if valid.get(parser) else 'Unknown'
    if {'BagPath', 'ShellType'} <= c or {'AppIdDescription', 'TargetCreated'} <= c: return 'EZTools - File and Folder'
    if {'EntryNumber', 'InUse', 'FileName'} <= c or {'UpdateReasons', 'UpdateTimestamp'} <= c: return 'MFTECmd'
    if {'HivePath', 'Category', 'KeyPath'} <= c or 'BatchKeyPath' in c: return 'RECmd'
    if {'EventId', 'Channel'} <= c: return 'EVTXECmd'
    if {'EventID', 'RuleFile'} <= c: return 'Hayabusa'
    if 'detections' in c: return 'Chainsaw'
    if {'ExecutableName', 'RunCount'} <= c or 'CacheEntryPosition' in c: return 'EZTools - Execution'
    if {'ActivityId', 'PackageName'} <= c or {'Id', 'ActivityType', 'Payload'} <= c: return 'SQLECmd'
    if {'AutoIncId', 'AppId', 'UserId', 'TimeStamp'} <= c or 'SruDbIdMapTable' in name: return 'SRUM'
    return 'Unknown'


def row_categories(parser, row, report):
    categories = []
    if parser == 'RECmd':
        native = row.get('Category', '').strip()
        categories.append(native or describe_report(report, row.keys())['Artifact'] or 'Registry detail')
    elif parser == 'MFTECmd':
        if 'UpdateReasons' in row:
            categories = ['USN journal'] + ['USN: '+v.strip() for v in re.split(r'[,|;]', row['UpdateReasons']) if v.strip()]
        else:
            used = truth(row.get('InUse', ''))
            categories.append('Allocated records' if used is True else 'Unallocated records' if used is False else 'Unknown allocation')
            directory = truth(row.get('IsDirectory', ''))
            if directory is not None: categories.append('Directories' if directory else 'Files')
            if truth(row.get('IsAds', '')) is True: categories.append('Alternate data stream records')
            if truth(row.get('HasAds', '')) is True: categories.append('Records with alternate data streams')
            if truth(row.get('SI<FN', '')) is True: categories.append('Native SI<FN flag set')
    elif parser == 'EVTXECmd':
        channel = row.get('Channel', '').casefold()
        provider = row.get('Provider', '').casefold()
        event = row.get('EventId', '').strip()
        security = channel == 'security' or provider == 'microsoft-windows-security-auditing'
        if security:
            if event in {'4624','4625','4634','4647','4648','4672','4776','4768','4769','4771'}: categories.append('Authentication and logons')
            if event in {'4720','4722','4723','4724','4725','4726','4728','4729','4732','4733','4738','4740','4756','4757'}: categories.append('Accounts and groups')
            if event in {'4688','4689'}: categories.append('Process creation and termination')
            if event in {'4697','4698','4699','4700','4701','4702'}: categories.append('Service and task configuration')
            if event in {'1102','4719'}: categories.append('Audit policy and log clearing')
        if 'powershell' in channel or 'powershell' in provider: categories.append('PowerShell events')
        if 'taskscheduler' in channel or 'taskscheduler' in provider: categories.append('Task Scheduler events')
        if 'terminalservices' in channel or 'remoteconnectionmanager' in provider: categories.append('Remote Desktop events')
        if provider == 'service control manager': categories.append('Service Control Manager events')
        if 'sysmon' in provider: categories.append('Sysmon events')
        if not categories: categories.append('Other event records')
    elif parser == 'EZTools - Execution':
        if 'ExecutableName' in row and 'RunCount' in row: categories.append('Prefetch execution traces')
        elif 'CacheEntryPosition' in row: categories.append('Shimcache records')
        elif 'TargetCreated' in row: categories.append('LNK shortcut targets')
        else: categories.append('Amcache inventory')
    elif parser == 'EZTools - File and Folder':
        if 'BagPath' in row:
            categories.append('ShellBags')
            kind = row.get('ShellType', '').casefold()
            categories.append('ShellBags: directories' if kind == 'directory' else 'ShellBags: drive roots' if 'drive letter' in kind else 'ShellBags: namespace and other items')
        elif 'AppIdDescription' in row: categories.append('Automatic Jump Lists' if 'AutomaticDestinations' in report else 'Custom Jump Lists' if 'CustomDestinations' in report else 'Jump Lists')
        else: categories.append('Recycle Bin / file cache records')
    elif parser == 'SQLECmd':
        categories.append('Activity package associations' if 'ActivityId' in row and 'PackageName' in row else 'Windows Timeline activities' if 'ActivityType' in row else 'Other mapped SQLite records')
    elif parser == 'SRUM':
        info = describe_report(report, row.keys())
        categories.append(info['Artifact'])
    elif parser == 'Hayabusa': categories.append('Severity: ' + (row.get('Level', '').strip() or 'Unknown'))
    elif parser == 'Chainsaw': categories.append(row.get('detections', '').strip() or 'Unlabelled rule match')
    return tuple(dict.fromkeys(categories))


def snapshot(sheet):
    records = tuple({col.name: '' if col.getValue(row) is None else str(col.getValue(row))
                     for col in sheet.columns} for row in sheet.rows)
    return records, tuple(col.name for col in sheet.columns)


class ArtifactReview(Sheet):
    def __init__(self, source, parser, label, records, columns):
        super().__init__(parser + ' - ' + label)
        self._dfir_source_sheet = source
        self._dfir_report_name = source_name(source)
        for name in columns: self.addColumn(ColumnItem(name, name, width=28))
        self.rows = [dict(row) for row in records]


class ArtifactGroups(Sheet):
    def __init__(self, source, parser, field, records, columns):
        super().__init__(parser+' - Group by '+field)
        self._dfir_source_sheet = source
        self.parser, self.field, self.records, self.original_columns = parser, field, records, columns
        self.addColumn(ColumnItem('Value', 'Value', width=90)); self.addColumn(ColumnItem('Rows', 'Rows', type=int))
        counts = {}
        for row in records: counts[row.get(field, '')] = counts.get(row.get(field, ''), 0)+1
        self.rows = [{'Value': key, 'Rows': count} for key, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]

    def open_group(self):
        if self.cursorRow is not None:
            value = self.cursorRow['Value']
            vd.push(ArtifactReview(self._dfir_source_sheet, self.parser, self.field+' = '+(value or '[blank]'),
                [r for r in self.records if r.get(self.field, '') == value], self.original_columns))


class ArtifactCategories(Sheet):
    def __init__(self, source, parser):
        records, columns = snapshot(source)
        actual = infer_parser(source_name(source), columns)
        if actual != parser: vd.fail('Open a '+parser+' report first; this sheet is '+actual)
        super().__init__(parser+' - Categories')
        self._dfir_source_sheet = source
        self.parser, self.records, self.original_columns = parser, records, columns
        for field, width in [('View', 62), ('Rows', 12), ('Note', 110)]:
            self.addColumn(ColumnItem(field, field, width=width, type=int if field == 'Rows' else str))
        groups = {}
        for index, row in enumerate(records):
            for label in row_categories(parser, row, source_name(source)): groups.setdefault(label, []).append(index)
        self.rows = [{'View': 'All rows', 'Rows': len(records), 'Note': NOTES[parser], 'kind': 'all'}]
        self.rows += [{'View': name, 'Rows': len(indices), 'Note': 'Categories may overlap.', 'kind':'category', 'indices':indices}
                      for name, indices in sorted(groups.items())]
        self.rows += [{'View': 'Group by '+field, 'Rows':len({r.get(field,'') for r in records}),
                       'Note':'Count is the number of distinct values, including blanks.', 'kind':'group','field':field}
                      for field in GROUP_FIELDS[parser] if field in columns]

    def open_view(self):
        row = self.cursorRow
        if not row: return
        if row['kind']=='group': vd.push(ArtifactGroups(self._dfir_source_sheet,self.parser,row['field'],self.records,self.original_columns))
        else:
            records = self.records if row['kind']=='all' else [self.records[i] for i in row['indices']]
            vd.push(ArtifactReview(self._dfir_source_sheet,self.parser,row['View'],records,self.original_columns))


def open_categories(sheet, parser):
    vd.push(ArtifactCategories(sheet, parser))


class ZipCsvReport(Sheet):
    def __init__(self, archive, member):
        super().__init__(LocalPath(member).name)
        self.archive, self.member = archive, member
        self._dfir_report_name = LocalPath(member).name

    def iterload(self):
        with zipfile.ZipFile(self.archive) as archive:
            with archive.open(self.member) as raw, io.TextIOWrapper(raw,encoding='utf-8-sig',newline='') as text:
                reader=csv.DictReader(text)
                self.columns=[]
                for name in reader.fieldnames or []: self.addColumn(ColumnItem(name,name,width=28))
                for row in reader:
                    if None in row: raise ValueError('Extra CSV fields in '+self.member)
                    yield row


class ResultsZip(Sheet):
    def __init__(self, name, source):
        super().__init__(name,source=source)
        self._catalog=[]
        self.primary_only=False
        self.resetCols()

    def resetCols(self):
        self.columns=[]
        for name,width in [('Parser',25),('Artifact',40),('Profile',18),('Rows',12),('Representation',18),('View',12),('State',12),('Report',75),('Note',100)]:
            self.addColumn(ColumnItem(name,name,width=width,type=int if name=='Rows' else str))

    def iterload(self):
        self._catalog=catalog_zip(str(self.source))
        yield from (r for r in self._catalog if not self.primary_only or r['View']=='Primary')

    def toggle_primary(self):
        self.primary_only=not self.primary_only
        self.rows=[dict(r) for r in self._catalog if not self.primary_only or r['View']=='Primary']
        vd.status('Primary reports only' if self.primary_only else 'All reports, including alternate representations and system tables')

    def open_report(self):
        if self.cursorRow: vd.push(ZipCsvReport(str(self.source),self.cursorRow['Member']))


@vd.api
def open_dfirzip(vd,path):
    return ResultsZip(path.name,source=path)

ArtifactCategories.addCommand('Enter','dfir-artifact-open-view','sheet.open_view()','Open category or grouping')
ArtifactGroups.addCommand('Enter','dfir-artifact-open-group','sheet.open_group()','Open rows for this value')
ResultsZip.addCommand('Enter','dfir-zip-open-report','sheet.open_report()','Open CSV directly from ZIP')
ResultsZip.addCommand('F5','dfir-zip-primary','sheet.toggle_primary()','Toggle primary reports versus all representations')
