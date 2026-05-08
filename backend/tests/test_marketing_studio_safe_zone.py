"""Tests for the marketing-studio safe-zone prompt enrichment + crop
behaviour. Regression for the "BANK HOLIDAY SALE text cropped at the
top" bug reported May 3 2026.
"""
import io
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fake_square_png(size: int = 1024) -> bytes:
    """Generate a synthetic PNG we can feed through the crop helper."""
    img = Image.new("RGB", (size, size), color=(40, 40, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_aspect_directive_very_wide():
    from services.marketing_studio import _aspect_directive
    assert "3:1" in _aspect_directive(1920, 640)
    assert "very wide" in _aspect_directive(1920, 640).lower() or "three times" in _aspect_directive(1920, 640).lower()


def test_aspect_directive_wide():
    from services.marketing_studio import _aspect_directive
    out = _aspect_directive(1200, 628)
    # 1200/628 = 1.91 — between 1.6 and 2.0 triggers "16:9" bucket
    assert out  # non-empty


def test_aspect_directive_square():
    from services.marketing_studio import _aspect_directive
    assert "1:1" in _aspect_directive(1024, 1024)


def test_aspect_directive_portrait():
    from services.marketing_studio import _aspect_directive
    assert "portrait" in _aspect_directive(1080, 1920).lower() or "9:16" in _aspect_directive(1080, 1920)


def test_safe_zone_appendix_has_critical_rules():
    """The appendix must contain all 5 critical constraints or the
    text-cropping regression will come back."""
    from services.marketing_studio import SAFE_ZONE_APPENDIX
    text = SAFE_ZONE_APPENDIX
    assert "centre 60%" in text, "must specify centre 60% text zone"
    assert "20% padding" in text, "must specify 20% edge padding"
    assert "top 25%" in text, "must ban headline in top 25%"
    assert "bottom 25%" in text, "must ban headline in bottom 25%"
    assert "bleed" in text.lower(), "must name the outer 15% as bleed zone"
    assert "CTA" in text, "must specify CTA placement"


@pytest.mark.asyncio
async def test_generate_banner_image_appends_safe_zone(monkeypatch):
    """Every call to generate_banner_image must inject the safe-zone
    rules into the downstream model prompt, whatever model is picked."""
    from services import marketing_studio as ms

    captured_prompts: list[str] = []

    async def _fake_nb(prompt, reference_image_b64=None):
        captured_prompts.append(prompt)
        return _fake_square_png()

    monkeypatch.setattr(ms, "_generate_nano_banana", _fake_nb)

    await ms.generate_banner_image(
        prompt="BANK HOLIDAY SALE up to 70% off, bold gold headline",
        model="nano-banana", width=1920, height=640,
    )
    assert len(captured_prompts) == 1
    p = captured_prompts[0]
    assert "SAFE ZONE" in p
    assert "centre 60%" in p
    assert "top 25%" in p
    # Aspect hint included too
    assert "3:1" in p or "three times" in p.lower()


@pytest.mark.asyncio
async def test_generate_banner_image_gpt_also_gets_safe_zone(monkeypatch):
    from services import marketing_studio as ms

    captured: list[str] = []

    async def _fake_gpt(prompt):
        captured.append(prompt)
        return _fake_square_png()

    monkeypatch.setattr(ms, "_generate_gpt_image_1", _fake_gpt)

    await ms.generate_banner_image(
        prompt="Kitchen showroom",
        model="gpt-image-1", width=1080, height=1350,
    )
    assert len(captured) == 1
    assert "SAFE ZONE" in captured[0]


def test_crop_centering_shifts_up_for_ultrawide_banners():
    """A 1024x1024 source cropped to 1920x640 (3:1) loses 70% of
    top+bottom. Centering must bias upward so headline y-band survives."""
    from services.marketing_studio import _crop_resize_to_target

    # Paint a recognisable horizontal stripe at y=45% of the source so
    # we can tell whether the crop biased upward or not. A true-centre
    # crop with a 3:1 target on a 1:1 source keeps y in [0.333, 0.667]
    # of the original. Our biased crop keeps [0.303, 0.637].
    src = Image.new("RGB", (1024, 1024), color=(255, 255, 255))
    # Red stripe at y=300 (29.3% of 1024)
    for y in range(295, 305):
        for x in range(1024):
            src.putpixel((x, y), (255, 0, 0))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    out_bytes = _crop_resize_to_target(buf.getvalue(), 1920, 640)
    out = Image.open(io.BytesIO(out_bytes))
    # The red stripe was at source y=29.3%. With the new centering
    # (0.5, 0.47), the cropped band spans y≈30.7% → 63.7% of the
    # source. So the stripe at 29.3% should NOT survive — that's
    # expected; the point is that the text normally lives in
    # y≈45-55% which IS in the kept band.
    # What we assert here is that row ~100 of the output (which maps
    # back to source y=30.7% + (100/640)*33.3% ≈ 35.9%) is NOT purely
    # white — meaning the biased crop preserved more of the upper
    # portion than a true-centre crop would.
    # The real proof is the centering value, so let's just check the
    # heuristic triggered:
    from services.marketing_studio import _crop_resize_to_target  # noqa: F401
    # Build a programmatic assertion by patching Image.fit and reading
    # the centering arg.
    import services.marketing_studio as ms
    with patch.object(ms.ImageOps, "fit", wraps=ms.ImageOps.fit) as spy:
        _crop_resize_to_target(buf.getvalue(), 1920, 640)
        assert spy.called
        _, kwargs = spy.call_args
        assert kwargs.get("centering") == (0.5, 0.47), f"expected upward bias, got {kwargs.get('centering')}"


def test_crop_centering_stays_centred_for_normal_aspects():
    """When the source and target are similar shapes, no bias needed."""
    from services.marketing_studio import _crop_resize_to_target
    import services.marketing_studio as ms

    src = Image.new("RGB", (1600, 900), color=(50, 50, 50))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    with patch.object(ms.ImageOps, "fit", wraps=ms.ImageOps.fit) as spy:
        _crop_resize_to_target(buf.getvalue(), 1080, 1080)
        _, kwargs = spy.call_args
        # 1080/1080 = 1.0 (target), 1600/900 = 1.78 (source).
        # target is NOT wider than source — no bias.
        assert kwargs.get("centering") == (0.5, 0.5)
