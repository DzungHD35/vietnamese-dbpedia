"""Bảng màu, theme Gradio và CSS của giao diện."""

import os

import gradio as gr

INK = "#17221f"
MUTED = "#56645f"
LINE = "#d9e1de"
JADE = "#0f6b5a"
JADE_DARK = "#0b5547"
JADE_SOFT = "#e1f0eb"
SOFT = "#f5f7f6"

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
FAVICON = os.path.join(STATIC_DIR, "favicon.svg")

_PALETTE = {
    "ink": INK,
    "muted": MUTED,
    "line": LINE,
    "jade": JADE,
    "jade-dark": JADE_DARK,
    "jade-soft": JADE_SOFT,
    "soft": SOFT,
}
with open(os.path.join(STATIC_DIR, "style.css"), encoding="utf-8") as _f:
    CSS = ":root {" + " ".join(f"--{k}: {v};" for k, v in _PALETTE.items()) + "}\n" + _f.read()

THEME = gr.themes.Base(
    primary_hue="teal",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Be Vietnam Pro"), "Segoe UI", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "Consolas", "monospace"],
    radius_size=gr.themes.sizes.radius_sm,
).set(
    body_background_fill="#ffffff",
    body_text_color=INK,
    body_text_color_subdued=MUTED,
    background_fill_primary="#ffffff",
    background_fill_secondary=SOFT,
    block_background_fill="#ffffff",
    block_border_color=LINE,
    block_border_width="1px",
    block_shadow="none",
    block_label_background_fill="#ffffff",
    block_label_text_color=MUTED,
    block_title_text_weight="600",
    panel_background_fill="#ffffff",
    input_background_fill="#ffffff",
    input_border_color=LINE,
    input_border_color_focus=JADE,
    input_shadow="none",
    input_shadow_focus=f"0 0 0 2px {JADE}22",
    border_color_primary=LINE,
    button_primary_background_fill=JADE,
    button_primary_background_fill_hover=JADE_DARK,
    button_primary_text_color="#ffffff",
    button_primary_border_color=JADE,
    button_secondary_background_fill="#ffffff",
    button_secondary_background_fill_hover=SOFT,
    button_secondary_border_color=LINE,
    button_secondary_text_color=INK,
    button_primary_shadow="none",
    button_secondary_shadow="none",
    button_primary_shadow_hover="none",
    button_secondary_shadow_hover="none",
    checkbox_background_color_selected=JADE,
    checkbox_border_color_selected=JADE,
    color_accent_soft=JADE_SOFT,
    link_text_color=JADE,
)

# Gradio bật dark mode bằng class "dark" trên <body> khi hệ điều hành ở chế độ tối; gỡ class đó để luôn sáng
FORCE_LIGHT_JS = """
() => {
    const body = document.body;
    const keepLight = () => { if (body.classList.contains("dark")) body.classList.remove("dark"); };
    keepLight();
    new MutationObserver(keepLight).observe(body, { attributes: true, attributeFilter: ["class"] });
}
"""
