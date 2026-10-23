"""Regression tests for native llama.cpp canonical/legacy model discovery.

Run with: python -m unittest backend/tests/test_llamacpp_model_aliases.py
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE = (
    Path(__file__).resolve().parents[1]
    / "open_webui"
    / "utils"
    / "llamacpp_model_aliases.py"
)
spec = importlib.util.spec_from_file_location("llamacpp_model_aliases", MODULE)
assert spec is not None and spec.loader is not None
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
expand = helpers.expand_llamacpp_model_aliases


class LlamaCppAliasDiscoveryTests(unittest.TestCase):
    def test_preserves_canonical_and_legacy_identity(self):
        models = [
            {
                "id": "gemma3:CORE",
                "aliases": ["gemma3:270m-core"],
                "status": {"value": "loaded"},
            },
            {
                "id": "imranzunzani/gemma3-1b-owui-fix:LATEST",
                "aliases": ["imranzunzani/gemma3-1b-owui-fix:latest"],
            },
            {
                "id": "qwen2.5-coder:Q4_K_M",
                "aliases": ["qwen2.5-coder:1.5b-instruct-q4_K_M"],
            },
        ]
        output = expand(models)
        ids = [entry["id"] for entry in output]
        self.assertEqual(ids[:3], [entry["id"] for entry in models])
        self.assertEqual(
            ids[3:],
            [
                "gemma3:270m-core",
                "imranzunzani/gemma3-1b-owui-fix:latest",
                "qwen2.5-coder:1.5b-instruct-q4_K_M",
            ],
        )
        self.assertEqual(output[3]["status"], {"value": "loaded"})
        self.assertEqual(output[3]["alias_of"], "gemma3:CORE")
        self.assertEqual(len(models), 3)

    def test_canonical_id_wins_collision_even_if_seen_later(self):
        models = [
            {"id": "gemma3:CORE", "aliases": ["gemma3:270m-core"]},
            {"id": "gemma3:270m-core", "aliases": []},
        ]
        self.assertEqual(expand(models), models)

    def test_deduplicates_aliases(self):
        models = [
            {"id": "a", "aliases": ["legacy", "legacy"]},
            {"id": "b", "aliases": ["legacy", "other"]},
        ]
        self.assertEqual([m["id"] for m in expand(models)], ["a", "b", "legacy", "other"])

    def test_ignores_invalid_alias_types(self):
        models = [
            {"id": "a", "aliases": [None, 19, "", "ok"]},
            {"id": "b", "aliases": "not-a-list"},
            {"id": "", "aliases": ["bad"]},
        ]
        self.assertEqual([m["id"] for m in expand(models)], ["a", "b", "", "ok"])

    def test_does_not_mutate_source_objects(self):
        models = [{"id": "a", "aliases": ["old"], "meta": {"ready": True}}]
        result = expand(models)
        result[1]["id"] = "changed"
        self.assertEqual(models, [{"id": "a", "aliases": ["old"], "meta": {"ready": True}}])

    def test_empty(self):
        self.assertEqual(expand([]), [])


if __name__ == "__main__":
    unittest.main()
