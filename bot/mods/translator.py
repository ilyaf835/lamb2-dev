from __future__ import annotations
from typing import Optional


class Translator:

    def __init__(self, labels: Optional[dict[str, str]] = None,
                 table: Optional[dict[str, str]] = None, language: Optional[str] = None):
        self.labels = {}
        self.table = {}
        self.language = language
        if labels:
            self.update_labels(labels)
        if table:
            self.update_table(table)

    def __call__(self, s: str, language: Optional[str] = None):
        return self.translate(s, language=language)

    def update_labels(self, labels: dict[str, str]):
        self.labels.update(labels)

    def update_table(self, table: dict[str, str]):
        self.table.update(table)

    def set_language(self, language: str):
        self.language = language

    def translate(self, s: str, language: Optional[str] = None):
        language = language or self.language
        if language in self.table:
            if s in self.labels:
                return self.table[language].get(self.labels[s], s)
        return s
