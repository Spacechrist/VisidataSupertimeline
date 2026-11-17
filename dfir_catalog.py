"""Read-only inventory of forensic CSV ZIPs. No VisiData or network dependency."""
import csv
import io
from pathlib import Path
import re
import zipfile

PARSER_TOKENS = (
    ('RECmd', 'RECmd'), ('SQLECmd', 'SQLECmd'), ('SRUM', 'SRUM'),
    ('MFTECmd', 'MFTECmd'), ('EvtxECmd', 'EVTXECmd'), ('Hayabusa', 'Hayabusa'),
    ('Chainsaw', 'Chainsaw'), ('SBECmd', 'EZTools - File and Folder'),
    ('JLECmd', 'EZTools - File and Folder'), ('RBCmd', 'EZTools - File and Folder'),
    ('RecentFileCacheParser', 'EZTools - File and Folder'),
    ('Prefetch', 'EZTools - Execution'), ('LECmd', 'EZTools - Execution'),
    ('AmcacheParser', 'EZTools - Execution'), ('AppCompatCacheParser', 'EZTools - Execution'),
)


def describe_report(name, columns=()):
    basename = Path(name).name
    match = next(((token, parser) for token, parser in PARSER_TOKENS
                  if re.search(r'(?:^|_)' + re.escape(token) + r'(?:_|\.)', basename, re.I)), None)
    token, parser = match or ('', 'Unknown')
    stem = basename[:-4] if basename.lower().endswith('.csv') else basename
    tail = re.split(r'(?:^|_)' + re.escape(token) + r'(?:_|$)', stem, maxsplit=1, flags=re.I)[-1] if token else stem
    profile = ''
    if token in ('RECmd', 'SQLECmd', 'SBECmd'):
        # Export contract: the profile is explicit immediately after the tool.
        source = re.match(r'(.+?)_(NTUSER\.DAT|UsrClass\.dat|ActivitiesCache)(?:_|$)', tail, re.I)
        if source:
            profile = source[1]
            tail = tail[len(source[1])+1:]
        elif tail.startswith('System_'):
            profile, tail = 'System', tail.removeprefix('System_')
        elif tail.startswith('AllHives_'):
            profile, tail = 'All profiles', tail.removeprefix('AllHives_')
    if not tail: tail = {'LECmd': 'LNK shortcut targets', 'Prefetch': 'Prefetch', 'AppCompatCacheParser': 'Shimcache'}.get(token, token or basename)
    representation, view = 'Native', 'Primary'
    note = ''
    if parser == 'EVTXECmd':
        representation = 'Timesketch' if 'datetime' in columns and 'timestamp_desc' in columns else 'Native'
        view = 'Primary' if representation == 'Timesketch' else 'Alternate'
        note = 'Native and Timesketch exports may contain the same events; do not add their counts.'
    elif parser == 'SRUM':
        representation = 'Resolved' if tail.endswith('_Resolved') else 'Raw'
        if '_System_' in basename:
            representation, view = 'System table', 'Reference'
        else:
            view = 'Primary' if representation == 'Resolved' else 'Alternate'
        note = 'Raw/resolved provider pairs represent the same records. Resolved IDs are not SOFTWARE-enriched usernames.'
    elif parser == 'RECmd' and profile == 'All profiles':
        representation, view = 'Combined batch', 'Alternate'
        note = 'Combined registry batch overlaps individual artifact reports; it is not an additional event source.'
    elif token == 'AmcacheParser':
        note = 'Application/device inventory is not proof of execution.'
    elif token == 'AppCompatCacheParser':
        note = 'Keep native Executed/FromSlack values; Shimcache presence alone does not prove execution.'
    elif token == 'SBECmd':
        note = 'Profile is the source directory label. Shellbag timestamps retain their distinct native meanings.'
    elif parser == 'SQLECmd' and 'ActivityPackages' in tail:
        note = 'Package associations link to Activity IDs; these rows are not separate application executions.'
    return {'Report': basename, 'Parser': parser, 'Tool': token, 'Artifact': tail,
            'Profile': profile or 'Not specified', 'Representation': representation,
            'View': view, 'Note': note}


def catalog_zip(path):
    records = []
    with zipfile.ZipFile(str(path)) as archive:
        names = [i.filename for i in archive.infolist() if not i.is_dir() and i.filename.lower().endswith('.csv')]
        if len(names) != len(set(names)):
            raise ValueError('ZIP contains duplicate member names; select a ZIP with unambiguous reports')
        for member in names:
            with archive.open(member) as raw, io.TextIOWrapper(raw, encoding='utf-8-sig', newline='') as text:
                reader = csv.DictReader(text)
                columns = reader.fieldnames or []
                rows = 0
                for row in reader:
                    if None in row:
                        raise ValueError('Extra CSV fields in ' + member)
                    rows += 1
            record = describe_report(member, columns)
            record.update(Member=member, Rows=rows, Columns=len(columns),
                          State='Empty' if not rows else 'Has rows')
            records.append(record)
    available = {record['Report'].casefold() for record in records}
    for record in records:
        name = record['Report']
        if record['Parser'] == 'SRUM' and record['Representation'] == 'Raw':
            paired = name.removesuffix('_Raw.csv') + '_Resolved.csv'
            if paired.casefold() not in available: record['View'] = 'Primary'
        if record['Parser'] == 'EVTXECmd' and record['Representation'] == 'Native':
            paired = name[:-4] + '_timesketch.csv'
            if paired.casefold() not in available: record['View'] = 'Primary'
        if record['Parser'] == 'RECmd' and record['Representation'] == 'Combined batch':
            prefix = name.split('_RECmd_', 1)[0] + '_RECmd_'
            if not any(r['Report'].startswith(prefix) and r['Profile'] != 'All profiles' for r in records):
                record['View'] = 'Primary'
    return records


def write_catalog(path, output):
    records = catalog_zip(path)
    fields = ['Parser', 'Tool', 'Artifact', 'Profile', 'Representation', 'View', 'State', 'Rows', 'Columns', 'Report', 'Note']
    with Path(output).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(records)
    return records


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip_file')
    parser.add_argument('--output', required=True, help='New CSV catalog path; source ZIP is never changed')
    args = parser.parse_args()
    if Path(args.output).exists(): parser.error('Output exists; choose a new filename')
    records = write_catalog(args.zip_file, args.output)
    print(f'{len(records)} CSVs; {sum(r["Rows"] for r in records)} physical rows; not a unique-event count')
