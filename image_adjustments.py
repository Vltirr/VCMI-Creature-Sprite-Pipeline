from __future__ import annotations

import math

from PIL import Image, ImageChops, ImageEnhance, ImageOps


def clamp_u8(v: float) -> int:
    return max(0, min(255, int(round(v))))


def value_to_factor(value: int) -> float:
    return max(0.0, float(value) / 100.0)


def gamma_lut(gamma: float) -> list[int]:
    gamma = max(0.01, gamma)
    inv = 1.0 / gamma
    return [clamp_u8(255.0 * pow(i / 255.0, inv)) for i in range(256)]


def apply_gamma(img: Image.Image, gamma: float) -> Image.Image:
    if math.isclose(gamma, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        return img
    img = img.convert("RGBA")
    rgb = img.convert("RGB").point(gamma_lut(gamma) * 3)
    alpha = img.getchannel("A")
    rgb.putalpha(alpha)
    return rgb


def _scaled_mask(mask: Image.Image, strength: float) -> Image.Image:
    strength = max(0.0, min(1.0, strength))
    if strength <= 0.0:
        return Image.new("L", mask.size, 0)
    return mask.point(lambda i: clamp_u8(i * strength))


def adjust_highlights_shadows(img: Image.Image, highlights: int, shadows: int) -> Image.Image:
    if highlights == 0 and shadows == 0:
        return img

    img = img.convert("RGBA")
    rgb = img.convert("RGB")
    alpha = img.getchannel("A")
    lum = ImageOps.grayscale(rgb)
    white = Image.new("RGB", rgb.size, (255, 255, 255))
    black = Image.new("RGB", rgb.size, (0, 0, 0))
    out = rgb

    if shadows != 0:
        shadow_mask = ImageOps.invert(lum)
        shadow_mask = _scaled_mask(shadow_mask, abs(shadows) / 100.0)
        target = white if shadows > 0 else black
        out = Image.composite(target, out, shadow_mask)

    if highlights != 0:
        highlight_mask = _scaled_mask(lum, abs(highlights) / 100.0)
        target = white if highlights > 0 else black
        out = Image.composite(target, out, highlight_mask)

    out.putalpha(alpha)
    return out


def apply_adjustments(
    img: Image.Image,
    brightness: int,
    contrast: int,
    saturation: int,
    sharpness: int,
    gamma: int,
    highlights: int,
    shadows: int,
) -> Image.Image:
    out = img.convert("RGBA")

    if brightness != 100:
        out = ImageEnhance.Brightness(out).enhance(value_to_factor(brightness))
    if contrast != 100:
        out = ImageEnhance.Contrast(out).enhance(value_to_factor(contrast))
    if saturation != 100:
        out = ImageEnhance.Color(out).enhance(value_to_factor(saturation))
    if sharpness != 100:
        out = ImageEnhance.Sharpness(out).enhance(value_to_factor(sharpness))

    out = apply_gamma(out, max(1, gamma) / 100.0)
    out = adjust_highlights_shadows(out, highlights=highlights, shadows=shadows)
    return out
