import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


@pytest.fixture
def localization(monkeypatch):
    frappe = types.ModuleType("frappe")
    frappe.local = types.SimpleNamespace(
        request=types.SimpleNamespace(cookies={}), lang=None
    )
    frappe.session = types.SimpleNamespace(user="Guest")
    frappe.flags = types.SimpleNamespace()
    frappe.whitelist = lambda *a, **k: lambda fn: fn
    frappe.throw = lambda message, *a, **k: (_ for _ in ()).throw(ValueError(message))
    frappe.clear_cache = lambda **kwargs: None

    class DB:
        language = None
        writes = []

        @classmethod
        def get_value(cls, doctype, name, field, **kwargs):
            if doctype == "User" and field == "language":
                return cls.language
            return None

        @classmethod
        def set_value(cls, *args, **kwargs):
            cls.writes.append((args, kwargs))

    frappe.db = DB
    limiter = types.ModuleType("frappe.rate_limiter")
    limiter.rate_limit = lambda *a, **k: lambda fn: fn
    access = types.ModuleType("nightjar_learning.access")
    access.instructor = lambda *a, **k: True
    access.is_admin = lambda *a, **k: False
    access.is_staff = lambda *a, **k: True
    access.user = lambda: "teacher@example.invalid"
    access.deny = lambda message="denied": (_ for _ in ()).throw(PermissionError(message))
    monkeypatch.setitem(sys.modules, "frappe", frappe)
    monkeypatch.setitem(sys.modules, "frappe.rate_limiter", limiter)
    monkeypatch.setitem(sys.modules, "nightjar_learning.access", access)
    spec = importlib.util.spec_from_file_location(
        "nightjar_learning.localization", ROOT / "nightjar_learning/localization.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module, frappe


@pytest.mark.parametrize(
    ("value", "expected"),
    [("ar", "ar"), ("ar-LY", "ar"), ("en_US", "en"), ("fr", None), (None, None)],
)
def test_normalize_language(localization, value, expected):
    module, _ = localization
    assert module.normalize_language(value) == expected


def test_language_precedence_and_arabic_default(localization):
    module, frappe = localization
    assert module.current_language() == "ar"
    frappe.session.user = "member@example.invalid"
    frappe.db.language = "en"
    assert module.current_language() == "en"
    frappe.local.request.cookies["nightjar_language"] = "ar"
    assert module.current_language() == "ar"
    assert module.current_language("en") == "en"


def test_content_fallback(localization):
    module, _ = localization
    row = {
        "title": "Original",
        "nj_title_ar": "العنوان",
        "nj_title_en": "English title",
    }
    assert module.translated(row, "title", "ar") == "العنوان"
    assert module.translated(row, "title", "en") == "English title"
    row["nj_title_ar"] = ""
    assert module.translated(row, "title", "ar") == "English title"
    row["nj_title_en"] = ""
    assert module.translated(row, "title", "ar") == "Original"


def test_language_update_is_account_scoped(localization):
    module, frappe = localization
    frappe.session.user = "member@example.invalid"
    assert module.set_language("en") == {"language": "en", "direction": "ltr"}
    assert frappe.db.writes[-1][0][:4] == (
        "User",
        "member@example.invalid",
        "language",
        "en",
    )
    with pytest.raises(ValueError):
        module.set_language("fr")


def test_request_language_applies_to_frappe(localization):
    module, frappe = localization
    frappe.local.request.cookies["nightjar_language"] = "ar"
    module.apply_request_language()
    assert frappe.local.lang == "ar"
