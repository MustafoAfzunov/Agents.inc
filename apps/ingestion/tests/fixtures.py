"""HTML fixtures and helpers shared by ingestion tests."""
from __future__ import annotations

LISTING_HTML = """
<!doctype html><html><body>
<a href="/2025/01/15/openai-launches-new-feature/">OpenAI launches new feature</a>
<a href="https://techcrunch.com/2025/01/16/altman-talks-future/">Altman talks future</a>
<a href="/category/openai/">category link (ignored)</a>
<a href="https://techcrunch.com/events/">events (ignored)</a>
<a href="/2025/01/15/openai-launches-new-feature/">duplicate link</a>
</body></html>
"""

ARTICLE_HTML = """
<!doctype html><html><head>
<title>Sam Altman criticizes Elon Musk over xAI strategy</title>
<meta name="author" content="Jane Reporter" />
<meta property="article:published_time" content="2025-01-15T09:30:00Z" />
</head><body>
<article>
<p>OpenAI chief executive Sam Altman criticizes Elon Musk after Musk launched a new
xAI initiative this week.</p>
<p>Sam Altman partners with Satya Nadella to expand Azure investments.</p>
<p>Altman declined to comment further. Musk responded on X.</p>
</article>
</body></html>
"""
