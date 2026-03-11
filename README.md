# SNMP Poller

An ops-grade Python tool that polls SNMP OIDs from multiple targets defined in a YAML config file and emits structured JSON output with timeouts, retries, time budgets, structured logging, and clean exit codes.

---

## Setup

```bash
sudo apt-get update
sudo apt-get install -y snmp python3 python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml
```

---

## How to run

```bash
# Output to a file
python3 poller.py --config config.yml --out out.json

# Output to stdout, with INFO logging
python3 poller.py --config config.yml --out - --log-level INFO

# Only show warnings and errors
python3 poller.py --config config.yml --out - --log-level WARNING
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | All targets polled successfully (no failed OIDs) |
| `1`  | Partial success — at least one target returned data, but some OIDs failed |
| `2`  | Total failure — no data from any target, or config is invalid |

---

## Example log output (INFO level)

```
2025-07-14 12:00:01 INFO - Starting poll run: 2 target(s), config=config.yml, output=-
2025-07-14 12:00:01 INFO - Polling target router1 (10.0.0.1) — 3 OID(s)
2025-07-14 12:00:02 WARNING - target=router1 oid=sysName.0: timeout on attempt 1/2, retrying
2025-07-14 12:00:04 INFO - Finished target router1: status=partial, ok=2, failed=1, elapsed=3.10s
2025-07-14 12:00:04 INFO - Polling target router2 (10.0.0.2) — 4 OID(s)
2025-07-14 12:00:06 INFO - Finished target router2: status=ok, ok=4, failed=0, elapsed=1.82s
2025-07-14 12:00:06 INFO - JSON output written to out.json
```

---

## Example JSON output

```json
{
  "run": {
    "timestamp": "2025-07-14T12:00:01.123456Z",
    "config_file": "config.yml",
    "duration_s": 5.12,
    "target_count": 2
  },
  "targets": [
    {
      "name": "router1",
      "ip": "10.0.0.1",
      "status": "partial",
      "results": [
        { "oid": "sysUpTime.0",    "status": "ok",     "value": "SNMPv2-MIB::sysUpTime.0 = Timeticks: (123456) 0:20:34.56" },
        { "oid": "sysName.0",      "status": "failed",  "value": "timeout" },
        { "oid": "ifOperStatus.1", "status": "ok",     "value": "IF-MIB::ifOperStatus.1 = INTEGER: up(1)" }
      ],
      "ok_count": 2,
      "fail_count": 1,
      "elapsed_s": 3.1
    },
    {
      "name": "router2",
      "ip": "10.0.0.2",
      "status": "ok",
      "results": [
        { "oid": "sysUpTime.0",  "status": "ok", "value": "SNMPv2-MIB::sysUpTime.0 = Timeticks: (654321) 1:49:03.21" },
        { "oid": "sysDescr.0",   "status": "ok", "value": "SNMPv2-MIB::sysDescr.0 = STRING: Linux router2" },
        { "oid": "sysContact.0", "status": "ok", "value": "SNMPv2-MIB::sysContact.0 = STRING: admin@example.com" },
        { "oid": "ifOperStatus.1","status": "ok", "value": "IF-MIB::ifOperStatus.1 = INTEGER: up(1)" }
      ],
      "ok_count": 4,
      "fail_count": 0,
      "elapsed_s": 1.82
    }
  ]
}
```

---

## Running unit tests

```bash
python -m unittest -v test_config.py
```

Expected output (all tests passing):

```
test_bad_version_returns_false (test_config.TestValidateConfigInvalidSnmpVersion) ... ok
test_empty_targets_returns_false (test_config.TestValidateConfigEmptyTargetsList) ... ok
test_float_retries_returns_false (test_config.TestValidateConfigNonIntRetries) ... ok
test_missing_defaults_returns_false (test_config.TestValidateConfigMissingDefaults) ... ok
test_missing_file_exits_with_failure (test_config.TestLoadConfig) ... ok
test_missing_targets_returns_false (test_config.TestValidateConfigMissingTargets) ... ok
test_target_missing_ip_returns_false (test_config.TestValidateConfigTargetMissingIp) ... ok
test_valid_config_returns_true (test_config.TestValidateConfigValidConfig) ... ok
...
----------------------------------------------------------------------
Ran 20 tests in 0.003s

OK
```
