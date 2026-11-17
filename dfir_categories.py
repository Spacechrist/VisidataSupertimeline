"""Permanent VisiData Category menu with isolated, extensible parser modules."""
from visidata import Sheet, ColumnItem, vd
import autorunsc

PARSERS = {}


class ParserInfo(Sheet):
    def __init__(self, name, source_sheet):
        super().__init__(name + ' - Setup')
        self._dfir_source_sheet = source_sheet
        self.addColumn(ColumnItem('Setting', 'Setting', width=22))
        self.addColumn(ColumnItem('Details', 'Details', width=100))
        self.rows = [
            {'Setting': 'Parser', 'Details': name},
            {'Setting': 'Status', 'Details': 'Menu entry reserved; review rules have not been implemented yet.'},
            {'Setting': 'Next step', 'Details': 'Define the desired views and filters using a sample output from this parser.'},
            {'Setting': 'Source', 'Details': 'No filtering or modification has been applied to the source sheet.'},
        ]


class ParserCategories(Sheet):
    def __init__(self, source_sheet):
        super().__init__('Category - DFIR Parsers')
        self._dfir_source_sheet = source_sheet
        for name, width in [('Parser', 32), ('Status', 22), ('Purpose', 80)]:
            self.addColumn(ColumnItem(name, name, width=width))
        self.rows = [{'Parser': name, 'Status': 'Ready' if p['handler'] else 'Rules pending',
                      'Purpose': p['description']} for name, p in PARSERS.items()]

    def open_parser(self):
        if self.cursorRow:
            self._dfir_source_sheet.dfir_open_parser(self.cursorRow['Parser'])


@Sheet.api
def dfir_categories(sheet):
    while isinstance(sheet, (ParserCategories, ParserInfo)):
        sheet = sheet._dfir_source_sheet
    vd.push(ParserCategories(sheet))


@Sheet.api
def dfir_open_parser(sheet, name):
    while isinstance(sheet, (ParserCategories, ParserInfo)):
        sheet = sheet._dfir_source_sheet
    parser = PARSERS[name]
    if parser['handler']:
        parser['handler'](sheet)
    else:
        vd.push(ParserInfo(name, sheet))


def register_parser(name, slug, description, handler=None):
    """Register one module without allocating a global parser-specific shortcut."""
    if name in PARSERS:
        raise ValueError('Parser already registered: ' + name)
    command = 'dfir-parser-' + slug
    if Sheet('').getCommand(command):
        raise ValueError('VisiData command already registered: ' + command)
    PARSERS[name] = {'handler': handler, 'description': description}
    Sheet.addCommand('', command, f'sheet.dfir_open_parser({name!r})', 'Open DFIR parser: ' + name)
    vd.addMenuItem('Category', name, command)


ParserCategories.addCommand('Enter', 'dfir-open-parser', 'sheet.open_parser()', 'Open the selected parser')

# The native menu and command longname work even if F2 belongs to another plugin.
Sheet.addCommand('', 'dfir-categories', 'sheet.dfir_categories()', 'Open DFIR parser category menu')
vd.addMenuItem('Category', 'All parsers', 'dfir-categories')
register_parser('Autorunsc', 'autorunsc', 'Autostart configuration: Services, Drivers, Tasks, KnownDLLs, Logon, Explorer',
                lambda sheet: sheet.autorunsc_menu())
register_parser('Supertimeline', 'supertimeline', 'Cross-artifact timeline review; logic to be defined')
register_parser('EVTXECmd', 'evtxecmd', 'Windows event logs')
register_parser('MFTECmd', 'mftecmd', 'MFT and USN journal')
register_parser('RECmd', 'recmd', 'Registry artifacts')
register_parser('EZTools - Execution', 'ezexecution', 'Prefetch, Amcache, AppCompatCache, and LNK outputs')
register_parser('EZTools - File and Folder', 'ezfilefolder', 'Jump Lists, ShellBags, and Recycle Bin outputs')
register_parser('SQLECmd', 'sqlecmd', 'Mapped SQLite artifacts')
register_parser('SRUM', 'srum', 'Application and network usage')
register_parser('Hayabusa', 'hayabusa', 'Event log detection timeline')
register_parser('Chainsaw', 'chainsaw', 'Event log hunting results')
register_parser('PyrsistenceSniper', 'pyrsistencesniper', 'Persistence findings')
register_parser('YARA-X', 'yarax', 'YARA scan results')
register_parser('Filesystem Timeline', 'filesystem-timeline', 'Filesystem MACB timeline')

existing = Sheet('').getCommand('F2')
if existing is None or existing.longname in ('autorunsc-menu', 'dfir-categories'):
    Sheet.bindkey('F2', 'dfir-categories')
else:
    vd.warning('DFIR: F2 already bound to ' + existing.longname + '; use Category > All parsers')
