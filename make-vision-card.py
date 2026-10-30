#!/usr/bin/env python3
"""Generate a dependency-free BMP card for repeatable vision checks."""

import argparse
import struct
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("output", nargs="?", default="vision-test-card.bmp")
args = parser.parse_args()

width, height = 512, 320
pixels = bytearray([245, 245, 245]) * (width * height)


def rectangle(x0, y0, x1, y1, color):
    for y in range(y0, y1):
        offset = (y * width + x0) * 3
        pixels[offset : offset + (x1 - x0) * 3] = bytes(color) * (x1 - x0)


rectangle(45, 60, 205, 220, (220, 35, 35))
rectangle(285, 85, 475, 245, (30, 80, 220))
rectangle(0, 285, width, height, (245, 195, 30))

row_size = (width * 3 + 3) & ~3
pixel_size = row_size * height
header_size = 54
output_path = Path(args.output)
with output_path.open("wb") as output:
    output.write(b"BM")
    output.write(struct.pack("<IHHI", header_size + pixel_size, 0, 0, header_size))
    output.write(struct.pack("<IIIHHIIIIII", 40, width, height, 1, 24, 0, pixel_size, 2835, 2835, 0, 0))
    padding = b"\0" * (row_size - width * 3)
    for y in range(height - 1, -1, -1):
        row = pixels[y * width * 3 : (y + 1) * width * 3]
        bgr = bytearray(len(row))
        bgr[0::3], bgr[1::3], bgr[2::3] = row[2::3], row[1::3], row[0::3]
        output.write(bgr)
        output.write(padding)

print(output_path.resolve())
