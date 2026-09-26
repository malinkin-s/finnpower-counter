# -*- coding: utf-8 -*-
"""Точка входа для сборки исполняемого файла.

    pyinstaller --onefile --noconsole app.py
"""

import sys

from finnpower_counter.gui import main

if __name__ == '__main__':
    sys.exit(main())
