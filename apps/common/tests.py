"""Tests for shared utility helpers."""
from __future__ import annotations

import pytest

from apps.common.utils.text import (
    is_probable_person_name,
    name_tokens,
    normalize_name,
)


def test_normalize_name_lowercases_and_strips_punctuation():
    assert normalize_name("Sam Altman") == "sam altman"
    assert normalize_name(" Sam  Altman ") == "sam altman"
    assert normalize_name("Sam-Altman") == "sam-altman"


def test_normalize_name_drops_honorifics_and_roles():
    assert normalize_name("Mr. Sam Altman") == "sam altman"
    # Possessive org prefix + role title both collapse away.
    assert normalize_name("OpenAI's CEO Sam Altman") == "sam altman"


def test_normalize_name_handles_accents():
    assert normalize_name("Émile Zola") == "emile zola"


def test_name_tokens():
    assert name_tokens("Sam Altman") == ["sam", "altman"]
    assert name_tokens("") == []


@pytest.mark.parametrize(
    "name",
    [
        "Sam Altman",
        "Elon Musk",
        "Satya Nadella",
        "Jean-Luc Picard",
        "Mary Jane Watson",
    ],
)
def test_is_probable_person_name_accepts_real_names(name):
    assert is_probable_person_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "",
        "Altman",  # single token
        "Full Name",  # prompt placeholder leak
        "On Thursday",  # date/stopword
        "The Wall Street",  # leading stopword
        "After Musk",  # leading stopword
        "Amazon Web Services",  # org tokens
        "Apollo Global Management",  # org tokens
        "App Store",  # org token
        "Amazon\nIs",  # embedded newline
        "OpenAI Inc",  # org tokens
    ],
)
def test_is_probable_person_name_rejects_noise(name):
    assert is_probable_person_name(name) is False
