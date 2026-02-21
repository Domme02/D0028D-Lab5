import yaml
import argparse
import subprocess
import json
import datetime
import logging
import pathlib
import sys

# Added exit codes as const variables.
OK = 0
PARTIAL = 1
FAILURE = 2

def parse_args():
    
    p = argparse.ArgumentParser(description="Poller")
    p.add_argument("--config", "-c", required=True, help="Path to configuration file")
    p.add_argument("--log-level","-l", default="INFO", choices=["INFO", "WARNING", "ERROR"], help="Log level")

    return p.parse_args()

def load_config(path):
    
    try:
        with open(path, "r", encoding="utf-8") as yml:
            cfg = yaml.safe_load(yml)
            
            # Empty file or only comments/whitespaces.
            if cfg is None:
                logging.warning("Configuration file is empty")
                sys.exit(FAILURE)
            
            # Checks for incorrect format of data.
            if not isinstance(cfg, dict):
                logging.warning("Config root must be a dictionary")
                sys.exit(FAILURE)

            return cfg

    # Handles errors with wrong user input
    except FileNotFoundError:
        logging.warning("Configuration file not found")
        sys.exit(FAILURE)
    
    # Handles permission errors.
    except PermissionError:
        logging.warning("Permission to access configuration file denied")
        sys.exit(FAILURE)


def validate_config(cfg):
    
    default_validation = ["snmp_version", "timeout_s", "retries", "target_budget_s", "oids"]
    targets_validation = ["name", "ip", "community", "oids"]
    
    # For loop, looping through each section of the configuration file.
    for section in cfg:
    
        # Checking presence of certain keys in section "defaults"
        if section == "defaults":
            for key in default_validation:
                if key not in cfg[section]:
                    logging.warning("%s must be present in the default configuration", key)

        # Checking presence of certain keys in section "targets"
        if section == "targets":
            for targets_list in cfg[section]:
                for key in targets_validation:
                    if key not in targets_list:
                        logging.warning("target=%s: %s must be present in the configuration file", targets_list["name"] ,key)

        
 

def merge_defaults(defaults, target):
    pass

def build_snmpget_cmd(target, oid):
    pass

def run_snmpget(cmd, timeout_s):
    pass

def poll_target(target):
    pass

def main():
    
    args = parse_args()
    
    cfg_path = args.config
    log_level_name = args.log_level

    # Global logging and logging configuration.
    numeric_level = getattr(logging, log_level_name.upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logfile = "logs.txt"

    logger = logging.getLogger("poller")
    logging.basicConfig(format=fmt, datefmt=datefmt, filename=logfile, encoding="utf-8", level=numeric_level)

    cfg = load_config(cfg_path)
    validate_config(cfg)

if __name__ == "__main__":
    main()
