"""Enumerations for the labels domain.

Values are stored as lowercase strings and are part of the public API contract.
Do not rename existing values; add new ones (architecture doc section 6).
"""

from enum import StrEnum


class LabelColor(StrEnum):
    """The palette a label is painted from.

    Named colors rather than hex codes: the frontend maps each name onto a design
    token with a light and a dark variant, so every label stays readable in both
    themes and no workspace can pick a color that disappears on its background.
    The order is the order a color picker offers them in.
    """

    GRAY = "gray"
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    TEAL = "teal"
    BLUE = "blue"
    INDIGO = "indigo"
    PURPLE = "purple"
    PINK = "pink"
