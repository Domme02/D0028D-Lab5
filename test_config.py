"""
test_config.py — Unit tests for poller.py config parsing and validation.
No network calls are made.

Run with:
    python -m unittest -v test_config.py
"""

import io
import logging
import sys
import textwrap
import unittest
from unittest.mock import MagicMock, patch

# Suppress log output during tests so test output is clean.
logging.disable(logging.CRITICAL)

# ── import the module under test ──────────────────────────────────────────────
import poller


# ── helpers ───────────────────────────────────────────────────────────────────

def _minimal_valid_cfg():
    """Return a minimal config dict that should pass validation."""
    return {
        "defaults": {
            "snmp_version": "v2c",
            "timeout_s": 2.5,
            "retries": 1,
            "target_budget_s": 10,
            "oids": ["sysUpTime.0"],
        },
        "targets": [
            {
                "name": "router1",
                "ip": "10.0.0.1",
                "community": "public",
                "oids": ["sysUpTime.0"],
            }
        ],
    }


# ── validate_config tests ─────────────────────────────────────────────────────

class TestValidateConfigMissingTargets(unittest.TestCase):
    """Missing 'targets' key must cause validate_config to return False."""

    def test_missing_targets_returns_false(self):
        cfg = _minimal_valid_cfg()
        del cfg["targets"]
        result = poller.validate_config(cfg)
        self.assertFalse(result)


class TestValidateConfigMissingDefaults(unittest.TestCase):
    """Missing 'defaults' key must cause validate_config to return False."""

    def test_missing_defaults_returns_false(self):
        cfg = _minimal_valid_cfg()
        del cfg["defaults"]
        result = poller.validate_config(cfg)
        self.assertFalse(result)


class TestValidateConfigTargetMissingIp(unittest.TestCase):
    """A target without an 'ip' key must be rejected."""

    def test_target_missing_ip_returns_false(self):
        cfg = _minimal_valid_cfg()
        del cfg["targets"][0]["ip"]
        result = poller.validate_config(cfg)
        self.assertFalse(result)


class TestValidateConfigTargetMissingName(unittest.TestCase):
    """A target without a 'name' key must be rejected."""

    def test_target_missing_name_returns_false(self):
        cfg = _minimal_valid_cfg()
        del cfg["targets"][0]["name"]
        result = poller.validate_config(cfg)
        self.assertFalse(result)


class TestValidateConfigNonNumericTimeout(unittest.TestCase):
    """A non-numeric timeout_s must be rejected."""

    def test_string_timeout_returns_false(self):
        cfg = _minimal_valid_cfg()
        cfg["defaults"]["timeout_s"] = "fast"
        result = poller.validate_config(cfg)
        self.assertFalse(result)

    def test_none_timeout_returns_false(self):
        cfg = _minimal_valid_cfg()
        cfg["defaults"]["timeout_s"] = None
        result = poller.validate_config(cfg)
        self.assertFalse(result)


class TestValidateConfigNonIntRetries(unittest.TestCase):
    """retries must be an int."""

    def test_float_retries_returns_false(self):
        cfg = _minimal_valid_cfg()
        cfg["defaults"]["retries"] = 1.5
        result = poller.validate_config(cfg)
        self.assertFalse(result)

    def test_string_retries_returns_false(self):
        cfg = _minimal_valid_cfg()
        cfg["defaults"]["retries"] = "one"
        result = poller.validate_config(cfg)
        self.assertFalse(result)


class TestValidateConfigInvalidSnmpVersion(unittest.TestCase):
    """snmp_version must be 'v2c' or 'v3'."""

    def test_bad_version_returns_false(self):
        cfg = _minimal_valid_cfg()
        cfg["defaults"]["snmp_version"] = "v1"
        result = poller.validate_config(cfg)
        self.assertFalse(result)


class TestValidateConfigEmptyTargetsList(unittest.TestCase):
    """An empty targets list must be rejected."""

    def test_empty_targets_returns_false(self):
        cfg = _minimal_valid_cfg()
        cfg["targets"] = []
        result = poller.validate_config(cfg)
        self.assertFalse(result)


class TestValidateConfigValidConfig(unittest.TestCase):
    """A fully valid config must return True."""

    def test_valid_config_returns_true(self):
        cfg = _minimal_valid_cfg()
        result = poller.validate_config(cfg)
        self.assertTrue(result)


# ── merge_defaults tests ──────────────────────────────────────────────────────

class TestMergeDefaults(unittest.TestCase):

    def setUp(self):
        self.defaults = {
            "snmp_version": "v2c",
            "timeout_s": 2.5,
            "retries": 1,
            "target_budget_s": 10,
            "oids": ["sysUpTime.0", "sysName.0"],
        }

    def test_target_oids_override_defaults(self):
        target = {
            "name": "r1", "ip": "1.2.3.4",
            "community": "public", "oids": ["ifOperStatus.1"],
        }
        merged = poller.merge_defaults(self.defaults, target)
        self.assertEqual(merged["oids"], ["ifOperStatus.1"])

    def test_defaults_used_when_target_has_no_oids(self):
        target = {"name": "r1", "ip": "1.2.3.4", "community": "public", "oids": []}
        merged = poller.merge_defaults(self.defaults, target)
        self.assertEqual(merged["oids"], self.defaults["oids"])

    def test_target_timeout_overrides_default(self):
        target = {
            "name": "r1", "ip": "1.2.3.4",
            "community": "public", "oids": [],
            "timeout_s": 5.0,
        }
        merged = poller.merge_defaults(self.defaults, target)
        self.assertEqual(merged["timeout_s"], 5.0)

    def test_default_timeout_used_when_not_in_target(self):
        target = {"name": "r1", "ip": "1.2.3.4", "community": "public", "oids": []}
        merged = poller.merge_defaults(self.defaults, target)
        self.assertEqual(merged["timeout_s"], 2.5)

    def test_required_keys_present_in_merged(self):
        target = {"name": "r1", "ip": "1.2.3.4", "community": "public", "oids": []}
        merged = poller.merge_defaults(self.defaults, target)
        for key in ("name", "ip", "community", "snmp_version",
                    "timeout_s", "retries", "target_budget_s", "oids"):
            self.assertIn(key, merged, msg=f"Key '{key}' missing from merged config")


# ── build_snmpget_cmd tests ───────────────────────────────────────────────────

class TestBuildSnmpgetCmd(unittest.TestCase):

    def _target(self, **overrides):
        base = {
            "name": "r1", "ip": "10.0.0.1",
            "community": "public", "snmp_version": "v2c",
            "timeout_s": 2.5, "retries": 1, "target_budget_s": 10,
            "oids": [],
        }
        base.update(overrides)
        return base

    def test_returns_list(self):
        cmd = poller.build_snmpget_cmd(self._target(), "sysUpTime.0")
        self.assertIsInstance(cmd, list)

    def test_starts_with_snmpget(self):
        cmd = poller.build_snmpget_cmd(self._target(), "sysUpTime.0")
        self.assertEqual(cmd[0], "snmpget")

    def test_contains_community(self):
        cmd = poller.build_snmpget_cmd(self._target(community="secret"), "sysUpTime.0")
        self.assertIn("secret", cmd)

    def test_contains_ip(self):
        cmd = poller.build_snmpget_cmd(self._target(ip="192.168.1.1"), "sysUpTime.0")
        self.assertIn("192.168.1.1", cmd)

    def test_contains_oid(self):
        cmd = poller.build_snmpget_cmd(self._target(), "ifOperStatus.1")
        self.assertIn("ifOperStatus.1", cmd)

    def test_v3_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            poller.build_snmpget_cmd(self._target(snmp_version="v3"), "sysUpTime.0")


# ── load_config tests (using tmp files / mocks) ───────────────────────────────

class TestLoadConfig(unittest.TestCase):

    def test_missing_file_exits_with_failure(self):
        with self.assertRaises(SystemExit) as cm:
            poller.load_config("/nonexistent/path/config.yml")
        self.assertEqual(cm.exception.code, poller.FAILURE)

    def test_valid_yaml_returns_dict(self):
        yaml_text = textwrap.dedent("""\
            defaults:
              snmp_version: "v2c"
              timeout_s: 2.5
              retries: 1
              target_budget_s: 10
              oids:
                - sysUpTime.0
            targets:
              - name: r1
                ip: 10.0.0.1
                community: public
                oids:
                  - sysUpTime.0
        """)
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(yaml_text)
            tmp_path = f.name
        try:
            cfg = poller.load_config(tmp_path)
            self.assertIsInstance(cfg, dict)
            self.assertIn("defaults", cfg)
            self.assertIn("targets", cfg)
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
