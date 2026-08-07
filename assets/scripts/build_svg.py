#!/usr/bin/env python3
"""Genera los SVG de marca del perfil (banner + separador).

El texto se convierte a trazados: un SVG servido por GitHub se carga como
`<img>`, un contexto restringido donde no hay carga de fuentes externas y el
soporte de `@font-face` con data-URI no es homogeneo entre navegadores. Con
outlines el render es identico en cualquier cliente.

Las fuentes son las mismas que sirve kn990x.dev (@fontsource-variable, en el
repo KN990x-B). Los tokens de color y el motivo isometrico salen de
KN990x-B/src/styles/base/variables.css y components/landing.css.

Uso:
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python build_svg.py [--fonts <dir de KN990x-B/node_modules/.pnpm>]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / "assets"

DEFAULT_FONT_ROOT = REPO.parent / "KN990x-B" / "node_modules" / ".pnpm"
SPACE_GROTESK = (
    "@fontsource-variable+space-grotesk@5.2.10/node_modules/@fontsource-variable/"
    "space-grotesk/files/space-grotesk-latin-wght-normal.woff2"
)
JETBRAINS_MONO = (
    "@fontsource-variable+jetbrains-mono@5.2.8/node_modules/@fontsource-variable/"
    "jetbrains-mono/files/jetbrains-mono-latin-wght-normal.woff2"
)

WORDMARK = "KN990x"
KICKER = "SOFTWARE · AUTOMATION · INTERNAL TOOLS"

# Lienzo del banner. GitHub lo sirve dentro de una columna de ~900px, asi que el
# SVG se escala a ~0.7: el lockup se dimensiona contando con esa reduccion.
W, H = 1280, 340
# Reticula mas gruesa y espaciada que .hero-iso (72px / 1px @ opacidad 0.045):
# a 0.7 de escala un hairline con esa opacidad desaparece por completo.
GRID_STEP, GRID_LINE = 80, 1.2

# El banner va sin fondo: sobre el lienzo de GitHub (#0d1117 u #ffffff) un rect
# opaco se lee como un panel pegado. Con fondo transparente la reticula pasa a
# ser el elemento grafico y la pieza se integra en la pagina.
THEMES = {
    "dark": {
        "grid": ("#ffffff", 0.13),
        "grad": ("#ededea", "#8fa3ac"),
        "kicker": "#999999",
        "rule": "#3a3a3a",
        "diamond": "#525252",
    },
    "light": {
        "grid": ("#000000", 0.09),
        "grad": ("#16181a", "#55707b"),
        "kicker": "#6f6f6f",
        "rule": "#d5d5d0",
        "diamond": "#b0b0ab",
    },
}


class Typesetter:
    """Compone una linea de texto como trazados, en unidades de fuente."""

    def __init__(self, path: Path, weight: float):
        font = TTFont(path)
        self.font = instancer.instantiateVariableFont(font, {"wght": weight})
        self.upm = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.glyphs = self.font.getGlyphSet()
        self.hmtx = self.font["hmtx"]

    def layout(self, text: str, tracking_em: float):
        """Devuelve (trazados, ancho, y_min, y_max) en unidades de fuente."""
        tracking = tracking_em * self.upm
        paths: list[tuple[str, float]] = []
        pen_x = 0.0
        y_min, y_max = None, None

        for char in text:
            name = self.cmap[ord(char)]
            glyph = self.glyphs[name]

            pen = SVGPathPen(self.glyphs)
            glyph.draw(pen)
            commands = pen.getCommands()
            if commands:
                paths.append((commands, pen_x))
                bounds = BoundsPen(self.glyphs)
                glyph.draw(bounds)
                if bounds.bounds:
                    _, g_min, _, g_max = bounds.bounds
                    y_min = g_min if y_min is None else min(y_min, g_min)
                    y_max = g_max if y_max is None else max(y_max, g_max)

            pen_x += self.hmtx[name][0] + tracking

        width = pen_x - tracking  # el tracking del ultimo glifo no cuenta
        return paths, width, (y_min or 0), (y_max or 0)


def render_line(setter, text, tracking_em, size, center_x, center_y, fill, indent="  "):
    """Emite un <g> con la linea centrada en (center_x, center_y) por su caja de tinta."""
    paths, width, y_min, y_max = setter.layout(text, tracking_em)
    scale = size / setter.upm

    origin_x = center_x - (width * scale) / 2
    # El eje y del SVG crece hacia abajo y el de la fuente hacia arriba: scale(s, -s)
    # invierte el glifo, asi que la linea base se calcula desde el centro de tinta.
    origin_y = center_y + ((y_max + y_min) / 2) * scale

    out = [f'{indent}<g transform="translate({origin_x:.2f} {origin_y:.2f}) '
           f'scale({scale:.6f} -{scale:.6f})" fill="{fill}">']
    for commands, pen_x in paths:
        out.append(f'{indent}  <path transform="translate({pen_x:.0f} 0)" d="{commands}"/>')
    out.append(f"{indent}</g>")
    return "\n".join(out)


def build_banner(theme_name: str, sans: Typesetter, mono: Typesetter) -> str:
    t = THEMES[theme_name]
    grid_color, grid_opacity = t["grid"]
    grad_from, grad_to = t["grad"]

    # Mascara radial en la linea de .hero-iso: elipse centrada, opaca en el nucleo
    # y desvanecida en los bordes para que la reticula no llegue a cortarse en seco.
    cx, cy = W / 2, H * 0.48
    rx, ry = W * 0.62, H * 0.85
    squash = ry / rx

    wordmark = render_line(sans, WORDMARK, -0.04, 240, W / 2, 148, "url(#wordmark)")
    kicker = render_line(mono, KICKER, 0.22, 20, W / 2, 258, t["kicker"])

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="KN990x — software, automation, internal tools">
  <defs>
    <linearGradient id="wordmark" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0.3" stop-color="{grad_from}"/>
      <stop offset="1" stop-color="{grad_to}"/>
    </linearGradient>
    <radialGradient id="falloff" gradientUnits="userSpaceOnUse" cx="{cx:.0f}" cy="{cy:.0f}" r="{rx:.0f}"
      gradientTransform="matrix(1 0 0 {squash:.6f} 0 {cy - cy * squash:.4f})">
      <stop offset="0.15" stop-color="#ffffff"/>
      <stop offset="0.82" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <mask id="fade">
      <rect width="{W}" height="{H}" fill="url(#falloff)"/>
    </mask>
    <pattern id="iso-a" width="{GRID_STEP}" height="{GRID_STEP}" patternUnits="userSpaceOnUse" patternTransform="rotate(60)">
      <line x1="0" y1="0" x2="0" y2="{GRID_STEP}" stroke="{grid_color}" stroke-opacity="{grid_opacity}" stroke-width="{GRID_LINE}"/>
    </pattern>
    <pattern id="iso-b" width="{GRID_STEP}" height="{GRID_STEP}" patternUnits="userSpaceOnUse" patternTransform="rotate(-60)">
      <line x1="0" y1="0" x2="0" y2="{GRID_STEP}" stroke="{grid_color}" stroke-opacity="{grid_opacity}" stroke-width="{GRID_LINE}"/>
    </pattern>
  </defs>

  <g mask="url(#fade)">
    <rect width="{W}" height="{H}" fill="url(#iso-a)"/>
    <rect width="{W}" height="{H}" fill="url(#iso-b)"/>
  </g>

{wordmark}
{kicker}
</svg>
"""


def build_rule(theme_name: str) -> str:
    t = THEMES[theme_name]
    width, height = 1280, 24
    mid_y = height / 2
    center = width / 2
    gap = 44  # hueco a cada lado del rombo
    d = 6     # semidiagonal del rombo

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="presentation" aria-hidden="true">
  <defs>
    <linearGradient id="left" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{t['rule']}" stop-opacity="0"/>
      <stop offset="1" stop-color="{t['rule']}" stop-opacity="1"/>
    </linearGradient>
    <linearGradient id="right" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{t['rule']}" stop-opacity="1"/>
      <stop offset="1" stop-color="{t['rule']}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <line x1="0" y1="{mid_y}" x2="{center - gap}" y2="{mid_y}" stroke="url(#left)" stroke-width="1"/>
  <line x1="{center + gap}" y1="{mid_y}" x2="{width}" y2="{mid_y}" stroke="url(#right)" stroke-width="1"/>
  <path d="M{center} {mid_y - d} L{center + d} {mid_y} L{center} {mid_y + d} L{center - d} {mid_y} Z"
        fill="none" stroke="{t['diamond']}" stroke-width="1"/>
</svg>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", type=Path, default=DEFAULT_FONT_ROOT,
                        help="raiz de node_modules/.pnpm en el repo KN990x-B")
    args = parser.parse_args()

    sans_path = args.fonts / SPACE_GROTESK
    mono_path = args.fonts / JETBRAINS_MONO
    for path in (sans_path, mono_path):
        if not path.exists():
            raise SystemExit(f"No encuentro la fuente: {path}\nPasa --fonts con la ruta correcta.")

    sans = Typesetter(sans_path, 700)   # display del wordmark
    mono = Typesetter(mono_path, 500)   # kicker en mono, como los metadatos del sitio

    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (ASSETS / f"banner-{theme}.svg").write_text(build_banner(theme, sans, mono), encoding="utf-8")
        (ASSETS / f"rule-{theme}.svg").write_text(build_rule(theme), encoding="utf-8")
        print(f"escrito assets/banner-{theme}.svg  assets/rule-{theme}.svg")


if __name__ == "__main__":
    main()
