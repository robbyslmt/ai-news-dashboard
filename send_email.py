import tempfile, os, subprocess, sys, datetime

today = datetime.date.today().isoformat()

html = '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="margin:0;padding:0;background:#f4f4f7;font-family:Arial,Helvetica,sans-serif;"><table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;"><tr><td align="center" style="padding:20px;"><table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;"><tr><td style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:30px 24px;text-align:center;"><h1 style="color:#ffffff;margin:0;font-size:28px;">&#128240; AI News Dashboard</h1><p style="color:#a0aec0;margin:8px 0 0;font-size:14px;">' + today + ' &mdash; Top AI Stories</p></td></tr><tr><td style="padding:20px 24px;"><table width="100%" cellpadding="0" cellspacing="0"><tr><td style="background:#1a1a2e;color:#fff;padding:12px;border-radius:6px;text-align:center;width:33%;"><div style="font-size:24px;font-weight:bold;">10</div><div style="font-size:11px;color:#a0aec0;">Stories</div></td><td style="width:4%;"></td><td style="background:#1a1a2e;color:#fff;padding:12px;border-radius:6px;text-align:center;width:33%;"><div style="font-size:24px;font-weight:bold;">50+</div><div style="font-size:11px;color:#a0aec0;">Scanned</div></td><td style="width:4%;"></td><td style="background:#1a1a2e;color:#fff;padding:12px;border-radius:6px;text-align:center;width:33%;"><div style="font-size:24px;font-weight:bold;">7</div><div style="font-size:11px;color:#a0aec0;">Subreddits</div></td></tr></table></td></tr>'

html += '<tr><td style="padding:8px 24px;"><h2 style="color:#1a1a2e;font-size:18px;border-bottom:2px solid #1a1a2e;padding-bottom:8px;">&#128293; Top 3 Stories</h2></td></tr>'

top3 = [
    ("#1", "503", "Hacker News", "Claude Code sends 33k tokens before reading the prompt; OpenCode sends 7k", "https://systima.ai/blog/claude-code-vs-opencode-token-overhead", "Analysis reveals Claude Code sends over 33,000 system prompt tokens before reading user input, compared to OpenCode's 7,000."),
    ("#2", "424", "Hacker News", "What xAI's Grok build CLI sends to xAI: A wire-level analysis", "https://gist.github.com/cereblab/dc9a40bc26120f4540e4e09b75ffb547", "A wire-level analysis of xAI's Grok coding CLI reveals exactly what data it transmits back to xAI servers, sparking privacy concerns."),
    ("#3", "422", "Hacker News", "Old and new apps, via modern coding agents", "https://terrytao.wordpress.com/2026/07/11/old-and-new-apps-via-modern-coding-agents/", "Mathematician Terence Tao shares his experience using modern AI coding agents to build applications."),
]

html += '<tr><td style="padding:0 24px 16px;">'
for rank, votes, src, title, url, summary in top3:
    html += '<div style="background:#f8f9fb;border-left:4px solid #2563eb;padding:14px;border-radius:0 6px 6px 0;margin-bottom:12px;">'
    html += '<div style="font-size:13px;color:#2563eb;font-weight:bold;">&#127942; ' + rank + ' &middot; ' + votes + ' upvotes &middot; ' + src + '</div>'
    html += '<div style="font-size:15px;color:#1a1a2e;font-weight:bold;margin:4px 0;"><a href="' + url + '" style="color:#1a1a2e;text-decoration:none;">' + title + '</a></div>'
    html += '<div style="font-size:13px;color:#4a5568;">' + summary + '</div></div>'
html += '</td></tr>'

all_stories = [
    ("1", "Claude Code sends 33k tokens", "https://systima.ai/blog/claude-code-vs-opencode-token-overhead", "HN", "503"),
    ("2", "What xAI's Grok CLI sends to xAI", "https://gist.github.com/cereblab/dc9a40bc26120f4540e4e09b75ffb547", "HN", "424"),
    ("3", "Old and new apps, via modern coding agents", "https://terrytao.wordpress.com/2026/07/11/old-and-new-apps-via-modern-coding-agents/", "HN", "422"),
    ("4", "I love LLMs, I hate hype", "https://geohot.github.io//blog/jekyll/update/2026/07/12/i-love-llms.html", "HN", "366"),
    ("5", "Ask HN: Add flag for AI-generated articles", "https://news.ycombinator.com/item?id=48886741", "HN", "214"),
    ("6", "Migrating production AI agent to GPT-5.6", "https://ploy.ai/blog/migrating-a-production-ai-agent-to-gpt-5-6", "HN", "160"),
    ("7", "I Learned to Read Again", "https://substack.magazinenongrata.com/p/how-i-learned-to-read-again", "HN", "117"),
    ("8", "Mechanistic interpretability & causality for LLMs", "https://cacm.acm.org/news/can-we-understand-how-large-language-models-reason/", "HN", "92"),
    ("9", "Flash-MSA: Million-Token Sparse Attention", "https://nanduruganesh.github.io/flash-msa/", "HN", "31"),
    ("10", "Z.ai GLM-5.2 vs Anthropic & OpenAI", "https://www.japantimes.co.jp/business/2026/07/03/tech/china-ai-catch-up/", "Web", "—"),
]

html += '<tr><td style="padding:8px 24px;"><h2 style="color:#1a1a2e;font-size:18px;border-bottom:2px solid #1a1a2e;padding-bottom:8px;">&#128196; All Stories</h2></td></tr>'
html += '<tr><td style="padding:0 24px 20px;"><table width="100%" cellpadding="8" cellspacing="0" style="font-size:13px;border-collapse:collapse;">'
html += '<tr style="background:#1a1a2e;color:#fff;"><td style="padding:10px 8px;border-radius:6px 0 0 0;font-weight:bold;">#</td><td style="padding:10px 8px;font-weight:bold;">Story</td><td style="padding:10px 8px;font-weight:bold;">Source</td><td style="padding:10px 8px;border-radius:0 6px 0 0;font-weight:bold;text-align:center;">&#9650;</td></tr>'
for i, (num, title, url, src, votes) in enumerate(all_stories):
    bg = ' style="background:#f8f9fb;"' if i % 2 == 0 else ''
    html += '<tr' + bg + '><td style="padding:8px;color:#6b7280;">' + num + '</td><td style="padding:8px;"><a href="' + url + '" style="color:#2563eb;text-decoration:none;">' + title + '</a></td><td style="padding:8px;color:#6b7280;">' + src + '</td><td style="padding:8px;text-align:center;font-weight:bold;">' + votes + '</td></tr>'
html += '</table></td></tr>'

html += '<tr><td style="background:#1a1a2e;padding:20px 24px;text-align:center;"><p style="color:#a0aec0;margin:0;font-size:12px;">Generated by Hermes Agent &#129302; &middot; <a href="https://robbyslmt.github.io/ai-news-dashboard/" style="color:#60a5fa;text-decoration:none;">Live Dashboard</a></p></td></tr></table></td></tr></table></body></html>'

tmp = os.path.join(tempfile.gettempdir(), '836dcdb6b75f_report.html')
with open(tmp, 'w', encoding='utf-8') as f:
    f.write(html)

gws = os.path.expanduser('~/AppData/Local/hermes/skills/productivity/google-workspace/scripts/google_api.py')
result = subprocess.run([
    sys.executable, gws, 'gmail', 'send',
    '--to', 'snowflake.and.you@gmail.com',
    '--subject', '\U0001f9f0 AI News Dashboard \u2014 ' + today,
    '--html-file', tmp,
    '--html'
], capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print('STDERR:', result.stderr)
os.unlink(tmp)
