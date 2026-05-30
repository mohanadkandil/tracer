"""Data model + entity span helper for Bosch GDPR synthetic dataset."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EntityLabel = Literal[
    "PERSON",
    "EMPLOYEE_ID",
    "EMAIL",
    "PHONE",
    "ADDRESS",
    "TAX_ID",
    "IBAN",
    "DEPARTMENT",
    "COMPANY",
    "DATE",
    "ID_NUMBER",
    "SIGNATURE",
    "USERNAME",
]

DocType = Literal[
    "expense",
    "it_access",
    "incident",
    "supplier",
    "training",
    "policy",
    "meeting",
    "blank_template",
]

Lang = Literal["de", "en"]


class Entity(BaseModel):
    start: int
    end: int
    label: EntityLabel
    value: str


class Example(BaseModel):
    id: str
    doc_type: DocType
    lang: Lang
    is_template: bool = False
    is_filled: bool = True
    source: Literal["faker", "paraphrase", "hard_negative"] = "faker"
    text: str
    entities: list[Entity] = Field(default_factory=list)

    def validate_spans(self) -> bool:
        """Verify each entity's offsets actually match value in text."""
        for e in self.entities:
            if self.text[e.start : e.end] != e.value:
                return False
        return True


class TextBuilder:
    """Append text + entity spans together. Offsets always correct by construction."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self.entities: list[Entity] = []
        self._cursor = 0

    @property
    def text(self) -> str:
        return "".join(self._parts)

    def add(self, s: str) -> None:
        self._parts.append(s)
        self._cursor += len(s)

    def add_entity(self, value: str, label: EntityLabel) -> None:
        start = self._cursor
        self.add(value)
        self.entities.append(
            Entity(start=start, end=self._cursor, label=label, value=value)
        )

    def nl(self, n: int = 1) -> None:
        self.add("\n" * n)
