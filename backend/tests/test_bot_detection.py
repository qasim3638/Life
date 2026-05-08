"""Tests for the new bot-detection layer in routes.analytics."""
from __future__ import annotations

from routes.analytics import _looks_like_bot, _is_valid_tilestation_url


# ── Bot UA detection ──────────────────────────────────────────────────

def test_python_requests_is_bot():
    assert _looks_like_bot("python-requests/2.31.0") is True


def test_curl_is_bot():
    assert _looks_like_bot("curl/7.88.1") is True


def test_wget_is_bot():
    assert _looks_like_bot("Wget/1.21.3") is True


def test_gptbot_is_bot():
    assert _looks_like_bot("Mozilla/5.0 GPTBot/1.0 (+https://openai.com/gptbot)") is True


def test_claude_bot_is_bot():
    assert _looks_like_bot("ClaudeBot/1.0 (+claudebot@anthropic.com)") is True


def test_perplexity_bot_is_bot():
    assert _looks_like_bot("Mozilla/5.0 PerplexityBot") is True


def test_bytespider_is_bot():
    assert _looks_like_bot("Mozilla/5.0 Bytespider; spider-feedback@bytedance.com") is True


def test_meta_external_agent_is_bot():
    assert _looks_like_bot("meta-externalagent/1.1") is True


def test_headless_chrome_is_bot():
    assert _looks_like_bot("Mozilla/5.0 HeadlessChrome/120.0.0.0") is True


def test_empty_ua_is_bot():
    assert _looks_like_bot("") is True
    assert _looks_like_bot(None) is True


def test_short_ua_is_bot():
    assert _looks_like_bot("ab") is True


def test_real_chrome_ua_is_not_bot():
    chrome = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    assert _looks_like_bot(chrome) is False


def test_real_safari_ua_is_not_bot():
    safari = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
    assert _looks_like_bot(safari) is False


def test_real_firefox_ua_is_not_bot():
    firefox = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
    assert _looks_like_bot(firefox) is False


def test_real_edge_ua_is_not_bot():
    edge = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    assert _looks_like_bot(edge) is False


# ── URL validation ────────────────────────────────────────────────────

def test_relative_url_is_valid():
    assert _is_valid_tilestation_url("/shop/product/abc") is True
    assert _is_valid_tilestation_url("/") is True


def test_absolute_url_to_own_domain_is_valid():
    assert _is_valid_tilestation_url("https://tilestation.co.uk/shop") is True
    assert _is_valid_tilestation_url("https://www.tilestation.co.uk/blog") is True


def test_absolute_url_to_railway_prod_is_valid():
    assert _is_valid_tilestation_url("https://tile-station-production.up.railway.app/health") is True


def test_emergent_preview_url_is_valid():
    assert _is_valid_tilestation_url("https://abc.preview.emergentagent.com/shop") is True


def test_off_site_example_com_is_invalid():
    """Bot pings often use https://example.com — must reject."""
    assert _is_valid_tilestation_url("https://example.com/shop/tiles") is False


def test_unrelated_domain_is_invalid():
    assert _is_valid_tilestation_url("https://random-spam.xyz/checkout") is False


def test_empty_url_is_invalid():
    assert _is_valid_tilestation_url("") is False
    assert _is_valid_tilestation_url(None) is False
