#!/usr/bin/env python3
"""Render exact, text-free color/shape teaching cards without generative ambiguity."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
VOCAB = ROOT / "images/generated/vocab"
ADJS = ROOT / "images/generated/adjs"
SIZE = 1024
BG = "#F4F0E8"
NEUTRAL = "#C8CDD2"
OUTLINE = "#374151"
COLORS = {
    "red": "#E53935", "blue": "#1E88E5", "green": "#43A047",
    "yellow": "#FDD835", "orange_color": "#FB8C00", "purple": "#8E44AD",
    "pink": "#EC6F9E", "brown": "#795548", "gray": "#80868B",
    "black": "#171717", "white": "#FFFFFF",
}


def canvas():
    return Image.new("RGB", (SIZE, SIZE), BG)


def save(im, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "JPEG", quality=94, optimize=True)


def render_color(slug, fill):
    # Color cards are pure full-bleed fields: no contrasting background,
    # outline, shape, shadow, texture, or decoration.
    save(Image.new("RGB", (SIZE, SIZE), fill), VOCAB / f"{slug}.jpg")


def circle(d, cx, cy, r, fill):
    d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=fill)


def rect(d, cx, cy, w, h, fill):
    d.rectangle((cx-w//2, cy-h//2, cx+w//2, cy+h//2), fill=fill)


def render_comparison(slug):
    im = canvas(); d = ImageDraw.Draw(im); target = "#16A6A1"
    if slug in {"big", "small"}:
        target_big = slug == "big"
        circle(d, 360, 512, 255 if target_big else 95, target)
        circle(d, 760, 512, 95 if target_big else 255, NEUTRAL)
    elif slug in {"tall", "short"}:
        target_tall = slug == "tall"
        rect(d, 350, 512, 170, 650 if target_tall else 250, target)
        rect(d, 720, 512, 170, 250 if target_tall else 650, NEUTRAL)
    elif slug == "long":
        rect(d, 490, 390, 760, 70, target)
        rect(d, 490, 650, 280, 70, NEUTRAL)
    elif slug in {"wide", "narrow"}:
        target_wide = slug == "wide"
        rect(d, 512, 350, 760 if target_wide else 220, 170, target)
        rect(d, 512, 700, 220 if target_wide else 760, 170, NEUTRAL)
    save(im, ADJS / f"{slug}.jpg")


def render_shape(slug):
    im = canvas(); d = ImageDraw.Draw(im); fill = "#16A6A1"
    if slug == "round": circle(d, 512, 512, 320, fill)
    else: d.rectangle((192, 192, 832, 832), fill=fill)
    save(im, ADJS / f"{slug}.jpg")


def main():
    for slug, fill in COLORS.items(): render_color(slug, fill)
    for slug in ("big", "small", "tall", "short", "long", "wide", "narrow"):
        render_comparison(slug)
    for slug in ("round", "square"): render_shape(slug)
    print("rendered 20 color/shape cards")

if __name__ == "__main__": main()
