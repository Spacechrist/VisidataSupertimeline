"""Autorunsc CSV review views for VisiData, loaded by the DFIR Category menu."""
from visidata import Sheet, ColumnItem, vd

CATEGORIES = ('Services', 'Drivers', 'Tasks', 'KnownDLLs', 'Logon', 'Explorer')
REQUIRED = {'Entry', 'Category', 'Enabled', 'Signer', 'Image Path'}


def category(value):
    return 'KnownDLLs' if value.strip().casefold().replace(' ', '') == 'knowndlls' else value.strip()


def signature(row):
    signer = row.get('Signer', '').strip()
    if signer.casefold().startswith('(verified)'):
        return 'Verified'
    if signer.casefold().startswith('(unsigned)'):
        return 'Unsigned'
    return 'Unverified' if signer else 'Unknown'


def enabled(row):
    return row.get('Enabled', '').strip().casefold() == 'enabled'


def missing(row):
    # Match the collector's explicit diagnostic; never probe the analyst's filesystem.
    return row.get('Image Path', '').strip().casefold().startswith('file not found:')


def matches(row, selected_category=None, only_enabled=False, only_unverified=False,
            only_missing=False):
    return (bool(row.get('Entry', '').strip())
            and (selected_category is None or category(row.get('Category', '')) == selected_category)
            and (not only_enabled or enabled(row))
            and (not only_unverified or signature(row) != 'Verified')
            and (not only_missing or missing(row)))


def snapshot(sheet):
    columns = {col.name: col for col in sheet.columns}
    absent = REQUIRED - columns.keys()
    if absent:
        vd.fail('Open an Autorunsc CSV first; missing columns: ' + ', '.join(sorted(absent)))
    return tuple({name: str(col.getValue(row) or '') for name, col in columns.items()}
                 for row in sheet.rows if str(columns['Entry'].getValue(row) or '').strip())


class AutorunscReview(Sheet):
    """Independent review snapshot; filters always operate on the complete snapshot."""
    def __init__(self, records, selected_category=None):
        super().__init__('Autorunsc - All - All')
        self.records = records
        self.selected_category = selected_category
        self.only_enabled = self.only_unverified = self.only_missing = False
        preferred = ['Entry', 'Enabled', 'Signature State', 'Signer', 'Image Path',
                     'Launch String', 'Entry Location', 'Category', 'Profile',
                     'Description', 'Company', 'Time', 'SHA-256']
        names = list(dict.fromkeys(preferred + [k for row in records for k in row]))
        widths = {'Entry': 30, 'Enabled': 10, 'Signature State': 16, 'Signer': 36,
                  'Image Path': 60, 'Launch String': 60, 'Entry Location': 50}
        for name in names:
            self.addColumn(ColumnItem(name, name, width=widths.get(name, 24)))
        self.refresh_view()

    def refresh_view(self):
        self.rows = [dict(row, **{'Signature State': signature(row)}) for row in self.records
                     if matches(row, self.selected_category, self.only_enabled,
                                self.only_unverified, self.only_missing)]
        filters = [label for flag, label in ((self.only_enabled, 'Enabled'),
                   (self.only_unverified, 'Unverified'), (self.only_missing, 'Missing Image')) if flag]
        self.name = 'Autorunsc - {} - {}'.format(self.selected_category or 'All', ' + '.join(filters) or 'All')
        self.cursorRowIndex = self.topRowIndex = 0

    def toggle_filter(self, field):
        setattr(self, field, not getattr(self, field))
        self.refresh_view()
        vd.status(f'{self.name}: {len(self.rows)} entries')

    def reset_filters(self):
        self.only_enabled = self.only_unverified = self.only_missing = False
        self.refresh_view()

    def choose_category(self, index):
        self.selected_category = CATEGORIES[index] if index is not None else None
        self.refresh_view()

    def show_menu(self):
        vd.push(AutorunscMenu(self.records))


class AutorunscMenu(Sheet):
    def __init__(self, records):
        super().__init__('Autorunsc - Categories')
        self.records = records
        for name, width in [('Key', 5), ('Category', 16), ('All', 9), ('Enabled', 9),
                            ('Unverified', 12), ('Enabled + Unverified', 23), ('Missing Image', 16)]:
            self.addColumn(ColumnItem(name, name, width=width, type=int if name not in ('Category', 'Key') else str))
        self.rows = []
        for index, cat in enumerate(CATEGORIES):
            entries = [r for r in records if matches(r, cat)]
            self.rows.append({'Key': str(index + 1), 'Category': cat, 'All': len(entries),
                              'Enabled': sum(enabled(r) for r in entries),
                              'Unverified': sum(signature(r) != 'Verified' for r in entries),
                              'Enabled + Unverified': sum(enabled(r) and signature(r) != 'Verified' for r in entries),
                              'Missing Image': sum(missing(r) for r in entries)})

    def open_category(self, index=None):
        cat = CATEGORIES[index] if index is not None else self.cursorRow['Category']
        vd.push(AutorunscReview(self.records, cat))

    def open_all(self):
        vd.push(AutorunscReview(self.records))


@Sheet.api
def autorunsc_menu(sheet):
    if isinstance(sheet, (AutorunscReview, AutorunscMenu)):
        records = sheet.records
    else:
        records = snapshot(sheet)
    vd.push(AutorunscMenu(records))


Sheet.addCommand('', 'autorunsc-menu', 'sheet.autorunsc_menu()', 'Autorunsc: open category counts and review views')
AutorunscMenu.addCommand('Enter', 'autorunsc-open-category', 'sheet.open_category()', 'Open selected Autorunsc category')
AutorunscMenu.addCommand('0', 'autorunsc-all', 'sheet.open_all()', 'Review all Autorunsc categories')
AutorunscReview.addCommand('0', 'autorunsc-all', 'sheet.choose_category(None)', 'Review all categories, preserving filters')
for index, cat in enumerate(CATEGORIES):
    slug = cat.lower()
    AutorunscMenu.addCommand(str(index + 1), 'autorunsc-' + slug,
                            f'sheet.open_category({index})', 'Open Autorunsc ' + cat)
    AutorunscReview.addCommand(str(index + 1), 'autorunsc-' + slug,
                              f'sheet.choose_category({index})', 'Show Autorunsc ' + cat + ', preserving filters')
for key, field, slug, helptext in [
        ('F5', 'only_enabled', 'enabled', 'Toggle enabled entries only'),
        ('F6', 'only_unverified', 'unverified', 'Toggle entries without a verified signer (includes unknown)'),
        ('F7', 'only_missing', 'missing-image', 'Toggle entries explicitly reported as File not found')]:
    AutorunscReview.addCommand(key, 'autorunsc-toggle-' + slug,
                              f'sheet.toggle_filter({field!r})', helptext)
AutorunscReview.addCommand('F8', 'autorunsc-reset-filters', 'sheet.reset_filters()', 'Clear filters in current category')
