import yaml
import argparse
import subprocess
import json
import datetime
import logging
import pathlib
import sys
import time

# Exit codes
OK = 0
PARTIAL = 1
FAILURE = 2

logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description="Ops-grade SNMP Poller")
    p.add_argument("--config", "-c", required=True, help="Path to YAML configuration file")
    p.add_argument("--out", "-o", default="-", help="Output file path, or '-' for stdout")
    p.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )
    return p.parse_args()


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)

        if cfg is None:
            logger.error("Configuration file is empty: %s", path)
            sys.exit(FAILURE)

        if not isinstance(cfg, dict):
            logger.error("Config root must be a YAML mapping (dict), got %s", type(cfg).__name__)
            sys.exit(FAILURE)

        return cfg

    except FileNotFoundError:
        logger.error("Configuration file not found: %s", path)
        sys.exit(FAILURE)

    except PermissionError:
        logger.error("Permission denied reading configuration file: %s", path)
        sys.exit(FAILURE)

    except yaml.YAMLError as exc:
        logger.error("Failed to parse YAML configuration: %s", exc)
        sys.exit(FAILURE)


def validate_config(cfg):
    """
    Validate structure and types of the configuration dict.
    Logs errors for every problem found and returns False if any are found.
    Does NOT call sys.exit — callers decide what to do with the result.
    """
    valid = True

    # ── defaults section ────────────────────────────────────────────────────
    required_default_keys = {
        "snmp_version": str,
        "timeout_s": (int, float),
        "retries": int,
        "target_budget_s": (int, float),
        "oids": list,
    }

    if "defaults" not in cfg:
        logger.error("Config missing required section: 'defaults'")
        valid = False
    else:
        defaults = cfg["defaults"]
        for key, expected_type in required_default_keys.items():
            if key not in defaults:
                logger.error("defaults: missing required key '%s'", key)
                valid = False
                continue

            value = defaults[key]
            if value is None or value == "":
                logger.error("defaults.%s must not be empty", key)
                valid = False
                continue

            if not isinstance(value, expected_type):
                logger.error(
                    "defaults.%s must be %s, got %s",
                    key, expected_type, type(value).__name__,
                )
                valid = False

        # Validate snmp_version value
        if "snmp_version" in defaults and defaults.get("snmp_version") not in ("v2c", "v3"):
            logger.error("defaults.snmp_version must be 'v2c' or 'v3'")
            valid = False

        # Validate numeric constraints
        for numeric_key in ("timeout_s", "retries", "target_budget_s"):
            val = defaults.get(numeric_key)
            if isinstance(val, (int, float)) and val <= 0:
                logger.error("defaults.%s must be positive, got %s", numeric_key, val)
                valid = False

    # ── targets section ──────────────────────────────────────────────────────
    required_target_keys = {
        "name": str,
        "ip": str,
        "community": str,
        "oids": list,
    }

    if "targets" not in cfg:
        logger.error("Config missing required section: 'targets'")
        valid = False
    elif not isinstance(cfg["targets"], list) or len(cfg["targets"]) == 0:
        logger.error("'targets' must be a non-empty list")
        valid = False
    else:
        for idx, target in enumerate(cfg["targets"]):
            # Use name if available for clearer error messages
            label = target.get("name", f"targets[{idx}]")

            if not isinstance(target, dict):
                logger.error("targets[%d]: must be a mapping, got %s", idx, type(target).__name__)
                valid = False
                continue

            for key, expected_type in required_target_keys.items():
                if key not in target:
                    logger.error("target '%s': missing required key '%s'", label, key)
                    valid = False
                    continue

                value = target[key]
                if value is None or value == "":
                    logger.error("target '%s': key '%s' must not be empty", label, key)
                    valid = False
                    continue

                if not isinstance(value, expected_type):
                    logger.error(
                        "target '%s': key '%s' must be %s, got %s",
                        label, key, expected_type, type(value).__name__,
                    )
                    valid = False

    return valid


def merge_defaults(defaults, target):
    """
    Return a single target config dict with defaults applied.
    Target-level keys override defaults where both exist.
    OIDs are merged: target OIDs are used if present, otherwise defaults.
    """
    return {
        "name": target["name"],
        "ip": target["ip"],
        "community": target.get("community", defaults.get("community", "")),
        "snmp_version": target.get("snmp_version", defaults["snmp_version"]),
        "timeout_s": target.get("timeout_s", defaults["timeout_s"]),
        "retries": target.get("retries", defaults["retries"]),
        "target_budget_s": target.get("target_budget_s", defaults["target_budget_s"]),
        # Target OIDs supplement (or replace) defaults — use target's list if provided,
        # otherwise fall back to defaults.
        "oids": target.get("oids") or defaults.get("oids", []),
    }


def build_snmpget_cmd(target, oid):
    """Build snmpget command list (v2c). v3 support can be added later."""
    version = target["snmp_version"]

    if version == "v2c":
        return [
            "snmpget",
            "-v", "2c",
            "-c", target["community"],
            "-t", str(target["timeout_s"]),
            "-r", "0",   # retries handled in poll_target
            target["ip"],
            oid,
        ]

    raise NotImplementedError(f"SNMP version '{version}' is not yet supported")


def run_snmpget(cmd, timeout_s):
    """
    Execute a snmpget command.
    Returns (ok: bool, value: str, elapsed_s: float).
    - ok=True  → got a result value
    - ok=False → timeout, unreachable, or auth error; value contains the error description
    """
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        elapsed = time.monotonic() - t0

        if result.returncode == 0:
            return True, result.stdout.strip(), elapsed

        # snmpget writes errors to stderr
        error_msg = result.stderr.strip() or result.stdout.strip()
        return False, error_msg, elapsed

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - t0
        return False, "timeout", elapsed

    except FileNotFoundError:
        elapsed = time.monotonic() - t0
        return False, "snmpget binary not found", elapsed


def _is_auth_error(error_msg):
    """Return True if the SNMP error looks like an authentication/credential failure."""
    auth_keywords = ("authentication", "authorization", "no access", "no such", "community")
    lower = error_msg.lower()
    return any(kw in lower for kw in auth_keywords)


def poll_target(target):
    """
    Poll all OIDs for a single target, applying retries and the per-target time budget.
    Returns a dict with name, ip, status, results, ok_count, fail_count, elapsed_s.
    """
    name = target["name"]
    ip = target["ip"]
    oids = target["oids"]
    timeout_s = target["timeout_s"]
    retries = target["retries"]
    budget_s = target["target_budget_s"]

    logger.info("Polling target %s (%s) — %d OID(s)", name, ip, len(oids))

    budget_start = time.monotonic()
    oid_results = []
    ok_count = 0
    fail_count = 0

    for oid in oids:
        budget_remaining = budget_s - (time.monotonic() - budget_start)
        if budget_remaining <= 0:
            logger.warning("target=%s: time budget exhausted, skipping remaining OIDs", name)
            oid_results.append({"oid": oid, "status": "skipped", "value": "budget exhausted"})
            fail_count += 1
            continue

        cmd = build_snmpget_cmd(target, oid)
        attempt_timeout = min(timeout_s, budget_remaining)

        ok = False
        value = ""
        attempt_elapsed = 0.0
        fast_fail = False

        for attempt in range(retries + 1):
            ok, value, attempt_elapsed = run_snmpget(cmd, attempt_timeout)

            if ok:
                break

            if value == "timeout":
                if attempt < retries:
                    logger.warning(
                        "target=%s oid=%s: timeout on attempt %d/%d, retrying",
                        name, oid, attempt + 1, retries + 1,
                    )
                else:
                    logger.warning(
                        "target=%s oid=%s: timeout after %d attempt(s), giving up",
                        name, oid, retries + 1,
                    )
            else:
                # Non-timeout error — check if it's an auth failure
                if _is_auth_error(value):
                    logger.error(
                        "target=%s oid=%s: authentication/permission error — skipping target: %s",
                        name, oid, value,
                    )
                    fast_fail = True
                    break
                # Other non-timeout errors → don't retry
                logger.error("target=%s oid=%s: SNMP error: %s", name, oid, value)
                break

        if fast_fail:
            # Mark remaining OIDs as failed and bail out of the target loop
            oid_results.append({"oid": oid, "status": "failed", "value": value})
            fail_count += 1
            for remaining_oid in oids[oids.index(oid) + 1:]:
                oid_results.append({
                    "oid": remaining_oid,
                    "status": "skipped",
                    "value": "skipped due to auth failure",
                })
                fail_count += 1
            break

        if ok:
            ok_count += 1
            oid_results.append({"oid": oid, "status": "ok", "value": value})
        else:
            fail_count += 1
            oid_results.append({"oid": oid, "status": "failed", "value": value})

    total_elapsed = round(time.monotonic() - budget_start, 3)

    if ok_count == len(oids):
        status = "ok"
    elif ok_count > 0:
        status = "partial"
    else:
        status = "failed"

    logger.info(
        "Finished target %s: status=%s, ok=%d, failed=%d, elapsed=%.2fs",
        name, status, ok_count, fail_count, total_elapsed,
    )

    return {
        "name": name,
        "ip": ip,
        "status": status,
        "results": oid_results,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "elapsed_s": total_elapsed,
    }


def main():
    args = parse_args()

    # ── Logging setup ────────────────────────────────────────────────────────
    numeric_level = getattr(logging, args.log_level.upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logfile = "logs.txt"

    logging.basicConfig(
        format=fmt,
        datefmt=datefmt,
        level=numeric_level,
        handlers=[
            logging.FileHandler(logfile, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )

    # ── Load & validate config ───────────────────────────────────────────────
    cfg = load_config(args.config)

    if not validate_config(cfg):
        logger.error("Configuration validation failed — aborting")
        sys.exit(FAILURE)

    defaults = cfg["defaults"]
    raw_targets = cfg["targets"]
    config_name = pathlib.Path(args.config).name
    out_dest = args.out

    logger.info(
        "Starting poll run: %d target(s), config=%s, output=%s",
        len(raw_targets), config_name, out_dest,
    )

    run_start = time.monotonic()
    run_timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    # ── Merge defaults and poll each target ──────────────────────────────────
    target_results = []
    for raw_target in raw_targets:
        target = merge_defaults(defaults, raw_target)
        result = poll_target(target)
        target_results.append(result)

    run_elapsed = round(time.monotonic() - run_start, 3)

    # ── Build JSON output ────────────────────────────────────────────────────
    output = {
        "run": {
            "timestamp": run_timestamp,
            "config_file": config_name,
            "duration_s": run_elapsed,
            "target_count": len(target_results),
        },
        "targets": target_results,
    }

    # ── Write output ─────────────────────────────────────────────────────────
    if out_dest == "-":
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        out_path = pathlib.Path(out_dest)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2)
        logger.info("JSON output written to %s", out_path)

    # ── Determine exit code ──────────────────────────────────────────────────
    statuses = [t["status"] for t in target_results]
    if all(s == "ok" for s in statuses):
        sys.exit(OK)
    elif any(s in ("ok", "partial") for s in statuses):
        sys.exit(PARTIAL)
    else:
        sys.exit(FAILURE)


if __name__ == "__main__":
    main()
