"""Gradio theme + custom CSS lifted from the original notebook.

Dark serif aesthetic — Playfair Display headings, Source Serif 4 body,
colour-coded panels (blue=plaintiff, red=defense, amber=expert, slate=judge,
green=strategist).
"""
import gradio as gr

THEME = gr.themes.Default(
    primary_hue="slate",
    secondary_hue="blue",
    neutral_hue="gray",
)

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Source+Serif+4:ital,wght@0,300;0,400;1,300&display=swap');

body, .gradio-container {
    background: #0e0e0e;
    color: #e8e2d9;
    font-family: 'Source Serif 4', Georgia, serif;
}
h1, h2, h3 { font-family: 'Playfair Display', Georgia, serif !important; }
.gradio-container { max-width: 1500px !important; }

#sidebar {
    background: #141414;
    border-right: 1px solid #2a2a2a;
    padding: 16px;
    border-radius: 8px;
}
#sidebar h3 { font-size: 1rem !important; opacity: 0.85; }
#sidebar .gr-button { font-size: 0.85rem !important; padding: 6px 10px !important; }

#plaintiff-panel {
    background: linear-gradient(160deg, #0a1628 0%, #0d1f3c 100%);
    border-left: 4px solid #3b82f6;
    border-radius: 4px 12px 12px 4px;
    padding: 20px; color: #bfdbfe;
    box-shadow: inset 0 0 60px rgba(59,130,246,0.05), 0 8px 32px rgba(0,0,0,0.4);
    min-height: 200px;
}
#defense-panel {
    background: linear-gradient(160deg, #1a0a0a 0%, #2d0f0f 100%);
    border-left: 4px solid #ef4444;
    border-radius: 4px 12px 12px 4px;
    padding: 20px; color: #fecaca;
    box-shadow: inset 0 0 60px rgba(239,68,68,0.05), 0 8px 32px rgba(0,0,0,0.4);
    min-height: 200px;
}
#expert-panel {
    background: linear-gradient(160deg, #1a1400 0%, #2d2200 100%);
    border-left: 4px solid #f59e0b;
    border-radius: 4px 12px 12px 4px;
    padding: 20px; color: #fde68a;
    box-shadow: inset 0 0 60px rgba(245,158,11,0.05), 0 8px 32px rgba(0,0,0,0.4);
    min-height: 200px;
}
#judge-panel {
    background: linear-gradient(160deg, #111111 0%, #1a1a1a 100%);
    border-left: 4px solid #9ca3af;
    border-radius: 4px 12px 12px 4px;
    padding: 20px; color: #e5e7eb;
    box-shadow: inset 0 0 60px rgba(156,163,175,0.05), 0 8px 32px rgba(0,0,0,0.4);
    min-height: 200px;
}
#strategy-panel {
    background: linear-gradient(160deg, #001a0d 0%, #002d15 100%);
    border-left: 4px solid #10b981;
    border-radius: 4px 12px 12px 4px;
    padding: 20px; color: #a7f3d0;
    box-shadow: inset 0 0 60px rgba(16,185,129,0.05), 0 8px 32px rgba(0,0,0,0.4);
    min-height: 200px;
}
.gr-button-primary {
    background: linear-gradient(135deg, #1e3a5f, #1d4ed8) !important;
    border: 1px solid #3b82f6 !important;
    font-family: 'Playfair Display', serif !important;
    letter-spacing: 0.05em !important;
    font-size: 1rem !important;
    padding: 12px 32px !important;
}
.gr-button-primary:hover {
    background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
    box-shadow: 0 0 20px rgba(59,130,246,0.3) !important;
}
footer { display: none !important; }
"""
