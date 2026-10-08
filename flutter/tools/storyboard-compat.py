#!/usr/bin/env python3
"""Copy storyboards, adjusting the stock Flutter template to the Linux ibtool subset.

  storyboard-compat.py <Base.lproj dir> <output dir>

Two adjustments, both visually neutral, applied to build-time copies only:
  * a calibratedWhite white background becomes the same white in sRGB;
  * a view or imageView with no design-time frame gets one (the layout is
    driven by constraints / autoresizing at run time, so the frame is unused).
"""
import os
import re
import sys

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

def white_to_srgb(m):
    w, a = m.group(1), m.group(2)
    return f'<color key="{m.group(0).split(chr(34))[1]}" red="{w}" green="{w}" blue="{w}" alpha="{a}" colorSpace="custom" customColorSpace="sRGB"/>'

for name in sorted(os.listdir(src)):
    if not name.endswith(".storyboard"):
        continue
    s = open(os.path.join(src, name)).read()
    s = re.sub(
        r'<color key="[^"]+" white="([^"]+)" alpha="([^"]+)" colorSpace="custom" customColorSpace="calibratedWhite"/>',
        white_to_srgb, s)
    images = {m.group(1): (float(m.group(2)), float(m.group(3)))
              for m in re.finditer(r'<image name="([^"]+)" width="([^"]+)" height="([^"]+)"/>', s)}
    lines, result = s.split("\n"), []
    for i, line in enumerate(lines):
        result.append(line)
        m = re.match(r"(\s*)<(view|imageView)\b[^>]*>\s*$", line)
        if not m or line.rstrip().endswith("/>"):
            continue
        if i + 1 < len(lines) and 'key="frame"' in lines[i + 1]:
            continue
        indent = m.group(1) + "    "
        if m.group(2) == "view":
            rect = (0.0, 0.0, 600.0, 600.0)
        else:
            img = re.search(r'image="([^"]+)"', line)
            w, h = images.get(img.group(1), (100.0, 100.0)) if img else (100.0, 100.0)
            rect = ((600 - w) / 2, (600 - h) / 2, w, h)
        result.append(f'{indent}<rect key="frame" x="{rect[0]:g}" y="{rect[1]:g}" width="{rect[2]:g}" height="{rect[3]:g}"/>')
    open(os.path.join(out, name), "w").write("\n".join(result))
