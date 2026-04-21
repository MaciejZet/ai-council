"""Regression tests for URL analyzer link extraction."""

from src.plugins.url_analyzer import URLAnalyzerPlugin


def test_extract_links_handles_protocol_relative_and_relative_paths():
    plugin = URLAnalyzerPlugin()
    html = """
    <html><body>
      <a href="//cdn.example.com/asset">CDN link</a>
      <a href="pricing">Pricing</a>
      <a href="/contact">Contact</a>
      <a href="mailto:test@example.com">Mail</a>
      <a href="javascript:void(0)">Ignore</a>
    </body></html>
    """

    links = plugin._extract_links(html, "https://site.test/blog/post")
    urls = [item["url"] for item in links]

    assert "https://cdn.example.com/asset" in urls
    assert "https://site.test/blog/pricing" in urls
    assert "https://site.test/contact" in urls
    assert all(not url.startswith("mailto:") for url in urls)
