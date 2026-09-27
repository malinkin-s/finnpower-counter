# -*- coding: utf-8 -*-
"""Генератор значка утилиты.

Рисует лист с деталями и галочку готовности. Значок нужен в нескольких
размерах: 16 пикселей — это список файлов в проводнике, 256 — крупные плитки.
Мелкие размеры рисуются отдельно и грубее: при уменьшении крупного рисунка
детали превращаются в кашу.

Pillow нужен только здесь. В самой утилите внешних зависимостей нет.

Запуск:  python3 tools/make_icon.py
"""

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')

SIZES = (16, 24, 32, 48, 64, 128, 256)

BACKDROP = (38, 48, 58, 255)      # графит: на светлой и тёмной панели виден одинаково
SHEET = (214, 219, 223, 255)      # лист металла
CUTOUT = (38, 48, 58, 255)        # вырубленные детали — цвет фона
CHECK = (74, 176, 89, 255)        # готовность
CHECK_EDGE = (24, 24, 24, 60)


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_large(size):
    """Крупный рисунок: лист с шестью вырубленными деталями и галочка."""
    scale = 8
    big = size * scale
    image = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    pad = big * 0.06
    rounded(draw, (pad, pad, big - pad, big - pad), big * 0.17, BACKDROP)

    # Лист.
    sx0, sy0 = big * 0.17, big * 0.20
    sx1, sy1 = big * 0.83, big * 0.66
    rounded(draw, (sx0, sy0, sx1, sy1), big * 0.03, SHEET)

    # Вырубленные детали: три колонки на два ряда.
    cols, rows = 3, 2
    gap = (sx1 - sx0) * 0.07
    cw = ((sx1 - sx0) - gap * (cols + 1)) / cols
    ch = ((sy1 - sy0) - gap * (rows + 1)) / rows
    for row in range(rows):
        for col in range(cols):
            x = sx0 + gap + col * (cw + gap)
            y = sy0 + gap + row * (ch + gap)
            rounded(draw, (x, y, x + cw, y + ch), big * 0.012, CUTOUT)

    # Галочка поверх нижнего правого угла.
    width = int(big * 0.115)
    points = [(big * 0.40, big * 0.72), (big * 0.55, big * 0.87), (big * 0.86, big * 0.40)]
    draw.line(points, fill=CHECK_EDGE, width=int(width * 1.5), joint='curve')
    draw.line(points, fill=CHECK, width=width, joint='curve')

    return image.resize((size, size), Image.LANCZOS)


def draw_small(size):
    """Мелкий рисунок: только лист в три полосы и крупная галочка."""
    scale = 16
    big = size * scale
    image = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    rounded(draw, (0, 0, big, big), big * 0.18, BACKDROP)

    sx0, sy0, sx1, sy1 = big * 0.13, big * 0.16, big * 0.87, big * 0.60
    rounded(draw, (sx0, sy0, sx1, sy1), big * 0.04, SHEET)
    bar = (sy1 - sy0) / 5.0
    for index in range(2):
        y = sy0 + bar * (1 + index * 2)
        draw.rectangle((sx0 + bar * 0.8, y, sx1 - bar * 0.8, y + bar), fill=CUTOUT)

    width = int(big * 0.16)
    points = [(big * 0.24, big * 0.70), (big * 0.44, big * 0.89), (big * 0.84, big * 0.38)]
    draw.line(points, fill=CHECK, width=width, joint='curve')

    return image.resize((size, size), Image.LANCZOS)


def main():
    if not os.path.isdir(ASSETS):
        os.makedirs(ASSETS)

    images = []
    for size in SIZES:
        images.append(draw_small(size) if size <= 32 else draw_large(size))

    ico = os.path.join(ASSETS, 'icon.ico')
    images[-1].save(ico, format='ICO',
                    sizes=[(s, s) for s in SIZES],
                    append_images=images[:-1])

    png = os.path.join(ASSETS, 'icon.png')
    images[-1].save(png, format='PNG')

    preview = Image.new('RGBA', (sum(SIZES) + 10 * len(SIZES), 256 + 20), (255, 255, 255, 255))
    x = 5
    for size, image in zip(SIZES, images):
        preview.paste(image, (x, 256 - size + 10), image)
        x += size + 10
    preview.save(os.path.join(ASSETS, 'icon-preview.png'))

    print('icon.ico   : {} байт, размеры {}'.format(
        os.path.getsize(ico), ', '.join(str(s) for s in SIZES)))
    print('icon.png   : {} байт'.format(os.path.getsize(png)))
    print('предпросмотр: assets/icon-preview.png')


if __name__ == '__main__':
    main()
