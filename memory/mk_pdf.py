"""Convert the session handoff markdown to a printable HTML then to PDF via headless Chrome."""
import markdown
from pathlib import Path

src = Path("/app/memory/SESSION_HANDOFF_2026-02-22.md")
html_out = Path("/app/memory/SESSION_HANDOFF_2026-02-22.html")

body = markdown.markdown(
    src.read_text(),
    extensions=["fenced_code", "tables", "toc"],
)

css = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  color: #111;
  line-height: 1.5;
  font-size: 11pt;
  max-width: 780px;
  margin: 0 auto;
  padding: 8px 4px 24px;
}
h1 { font-size: 22pt; letter-spacing: -0.02em; margin: 12px 0 6px; }
h2 { font-size: 15pt; margin: 26px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #ddd; }
h3 { font-size: 12pt; margin: 18px 0 6px; color: #222; }
p { margin: 6px 0; }
ul, ol { margin: 6px 0 6px 20px; padding: 0; }
li { margin: 3px 0; }
code {
  font-family: "SF Mono", "Menlo", "Consolas", monospace;
  font-size: 9.5pt;
  background: #f4f4f6;
  padding: 1px 4px;
  border-radius: 3px;
  color: #b02a37;
}
pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px 14px;
  border-radius: 6px;
  overflow-x: auto;
  page-break-inside: avoid;
  font-size: 8.5pt;
  line-height: 1.35;
}
pre code { background: transparent; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 10pt; }
th, td { border: 1px solid #d0d0d5; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f2f2f4; font-weight: 600; }
hr { border: 0; border-top: 1px solid #ddd; margin: 22px 0; }
strong { color: #000; }
blockquote { border-left: 3px solid #999; padding-left: 12px; color: #555; margin: 8px 0; }
"""

html = f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>App N SaaS Builder — Session Handoff 2026-02-22</title>
<style>{css}</style>
</head><body>
{body}
</body></html>"""

html_out.write_text(html)
print(f"wrote {html_out}")
