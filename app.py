"""
Simple local web form for the Nebula support-agent assistant.

Run:
    pip install flask anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python app.py

Then open http://localhost:5000 in your browser.

This is a thin UI wrapper around assistant.py's generate_response() —
all the actual AI logic lives there; this file only handles the form and
rendering. Kept as a single file with inline HTML/CSS for simplicity,
matching the MVP scope of this task (see README.md).
"""

from flask import Flask, request, render_template_string

from assistant import generate_response

app = Flask(__name__)

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Nebula Support Assistant</title>
<style>
  :root {
    --bg: #f7f7f8;
    --card: #ffffff;
    --border: #e2e2e6;
    --text: #1a1a1e;
    --muted: #6b6b74;
    --accent: #d97757;
    --warn-bg: #fff4e5;
    --warn-border: #f0b872;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    padding: 40px 20px;
  }
  .container { max-width: 760px; margin: 0 auto; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .subtitle { color: var(--muted); margin-bottom: 28px; font-size: 14px; }
  form {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 28px;
  }
  textarea {
    width: 100%;
    min-height: 120px;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-family: inherit;
    font-size: 14px;
    resize: vertical;
  }
  button {
    margin-top: 12px;
    background: var(--accent);
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  button:hover { opacity: 0.9; }
  .summary-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 16px;
  }
  .summary-card h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin: 0 0 8px 0; }
  .kb-chip {
    display: inline-block;
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 999px;
    margin-top: 8px;
  }
  .kb-used { background: #e6f4ea; color: #1e7e34; }
  .kb-missing { background: #f1f1f3; color: var(--muted); }
  .flag-banner {
    background: var(--warn-bg);
    border: 1px solid var(--warn-border);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 16px;
    font-size: 14px;
  }
  .flag-banner strong { display: block; margin-bottom: 4px; }
  .variants { display: grid; gap: 14px; }
  .variant-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
  }
  .variant-tone {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--accent);
    margin-bottom: 8px;
  }
  .variant-text { font-size: 14px; line-height: 1.55; white-space: pre-wrap; }
  .error-card {
    background: #fdecea;
    border: 1px solid #f5b3ac;
    border-radius: 12px;
    padding: 16px 20px;
    font-size: 14px;
  }
  .meta { color: var(--muted); font-size: 12px; margin-top: 24px; }
</style>
</head>
<body>
<div class="container">
  <h1>🎧 Nebula Support Assistant</h1>
  <p class="subtitle">Paste a ticket below to get a summary, a knowledge-base reference, and 3 draft replies in different tones.</p>

  <form method="POST" action="/submit">
    <textarea name="ticket_text" placeholder="Paste the ticket text here...">{{ ticket_text or '' }}</textarea>
    <br>
    <button type="submit">Generate draft replies</button>
  </form>

  {% if result %}
    {% if result.error %}
      <div class="error-card">
        <strong>Something went wrong.</strong> {{ result.flag_reason }}
        <br><br>Please write a manual reply for this ticket.
      </div>
    {% else %}
      {% if result.flag_for_review %}
      <div class="flag-banner">
        <strong>⚠️ Needs your judgment before sending</strong>
        {{ result.flag_reason }}
      </div>
      {% endif %}

      <div class="summary-card">
        <h2>Summary</h2>
        <div>{{ result.summary }}</div>
        {% if result.kb_used %}
          <span class="kb-chip kb-used">📚 Grounded in: {{ result.kb_article_title }}</span>
        {% else %}
          <span class="kb-chip kb-missing">No KB article matched — verify details before sending</span>
        {% endif %}
      </div>

      <div class="variants">
        {% for v in result.variants %}
        <div class="variant-card">
          <div class="variant-tone">{{ v.tone }}</div>
          <div class="variant-text">{{ v.text }}</div>
        </div>
        {% endfor %}
      </div>

      <div class="meta">
        Model: {{ result.model_used }} · Confidence: {{ result.confidence }}
        {% if result.latency_ms %} · {{ result.latency_ms }}ms{% endif %}
      </div>
    {% endif %}
  {% endif %}
</div>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE_TEMPLATE, result=None, ticket_text=None)


@app.route("/submit", methods=["POST"])
def submit():
    ticket_text = request.form.get("ticket_text", "").strip()
    if not ticket_text:
        return render_template_string(PAGE_TEMPLATE, result=None, ticket_text=None)

    result = generate_response(ticket_text)
    return render_template_string(
        PAGE_TEMPLATE, result=result.to_dict(), ticket_text=ticket_text
    )


if __name__ == "__main__":
    print("Starting Nebula Support Assistant on http://localhost:5000")
    app.run(debug=True, port=5000)
