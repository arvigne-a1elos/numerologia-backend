"""PDF styling constants and configurations."""

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle


class Typography:
    """Typography constants."""

    FONT_FAMILY = "Helvetica"
    FONT_FAMILY_BOLD = "Helvetica-Bold"
    
    # Font sizes
    SIZE_TITLE = 20
    SIZE_SUBTITLE = 16
    SIZE_BODY = 13
    SIZE_SMALL = 11
    
    # Line spacing
    SPACING_BODY = SIZE_BODY * 1.5
    SPACING_TITLE = SIZE_TITLE * 2.0


class ColorPalette:
    """Color definitions for the application."""

    GOLD = colors.HexColor("#B8860B")
    LIGHT_GRAY = colors.HexColor("#f0f0f0")
    DARK = colors.HexColor("#222")
    GRAY = colors.HexColor("#888")


class ParagraphStyles:
    """Pre-defined paragraph styles for ReportLab."""

    TITLE = ParagraphStyle(
        name="Title",
        fontName=Typography.FONT_FAMILY_BOLD,
        fontSize=Typography.SIZE_TITLE,
        textColor=ColorPalette.DARK,
        alignment=TA_CENTER,
        spaceAfter=Typography.SPACING_TITLE,
    )

    SUBTITLE = ParagraphStyle(
        name="Subtitle",
        fontName=Typography.FONT_FAMILY_BOLD,
        fontSize=Typography.SIZE_SUBTITLE,
        textColor=ColorPalette.GOLD,
        alignment=TA_LEFT,
        spaceAfter=Typography.SPACING_BODY,
    )

    BODY = ParagraphStyle(
        name="Body",
        fontName=Typography.FONT_FAMILY,
        fontSize=Typography.SIZE_BODY,
        textColor=ColorPalette.DARK,
        alignment=TA_JUSTIFY,
        spaceAfter=Typography.SPACING_BODY,
    )

    SMALL = ParagraphStyle(
        name="Small",
        fontName=Typography.FONT_FAMILY,
        fontSize=Typography.SIZE_SMALL,
        textColor=ColorPalette.GRAY,
        alignment=TA_LEFT,
    )


# Legacy constants for backward compatibility
GOLD = ColorPalette.GOLD
LGRAY = ColorPalette.LIGHT_GRAY
DARK = ColorPalette.DARK
GRAY = ColorPalette.GRAY
FONTE = Typography.FONT_FAMILY
FONTE_B = Typography.FONT_FAMILY_BOLD
TAM_T = Typography.SIZE_TITLE
TAM_S = Typography.SIZE_SUBTITLE
TAM_C = Typography.SIZE_BODY
TAM_P = Typography.SIZE_SMALL
ES = Typography.SPACING_BODY
ET = Typography.SPACING_TITLE
