# -*- coding: utf-8 -*-
"""The parser and view helpers must stay usable without a GUI or a network.

Nestrack bundles them into a client that has its own window and its own
network layer; pulling in Tk or sockets from here would break that.
"""

import subprocess
import sys

FORBIDDEN = ('tkinter', '_tkinter', 'socket', 'ssl', 'http', 'urllib')

PROBE = '''
import sys
import finnpower_counter.core.balance
import finnpower_counter.core.fms_parser
import finnpower_counter.core.nc_parser
import finnpower_counter.core.reader
import finnpower_counter.presentation
loaded = sorted(name for name in sys.modules
                if name.split('.')[0] in {forbidden!r})
print(','.join(loaded))
'''.format(forbidden=FORBIDDEN)


def test_core_and_presentation_import_no_gui_or_network():
    # A separate process: inside pytest these modules may already have been
    # imported by something else.
    result = subprocess.run([sys.executable, '-c', PROBE],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == ''


def test_version_is_semver():
    import finnpower_counter
    assert finnpower_counter.__version__.count('.') == 2
