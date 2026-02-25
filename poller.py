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
    datatype_validation = {"snmp_version":str, "timeout_s":(int, float), "retries":int, "target_budget_s":(int, float), "oids":list, "name":str, "ip":str, "community":str}
    
        # Checking presence of certain keys in section "defaults"
    if "defaults" in cfg:
        for key in default_validation:
            if key not in cfg["defaults"]:
                logging.warning("%s must be present in the default configuration", key)
                continue
                
            # Validating that keys do not have empty values.
            if cfg["defaults"][key] is None or cfg["defaults"][key] == "":
                logging.warning("%s must have a value in the configuration file", key)

            # Validating values data types of the keys.
            if not isinstance(cfg["defaults"][key], datatype_validation[key]):
                logging.warning("%s must be a %s in the configuration file", key, datatype_validation[key])
                

        # Checking presence of certain keys in section "targets"
    if "targets" in cfg:
        for targets_list in cfg["targets"]:
            for key in targets_validation:
                if key not in targets_list:
                    logging.warning("target=%s: %s must be present in the configuration file", targets_list["name"] ,key)
                    continue
                    
                # Validating that keys do not have empty values.
                if cfg["targets"][key] is None or cfg["targets"][key] == "":
                    logging.warning("%s must have a value in the configuration file", key)

                # Validating values data types of the keys.
                if not isinstance(targets_list[key], datatype_validation[key]):
                    logging.warning("%s must be a %s in the configuration file", key, datatype_validation[key])

        
 

def merge_defaults(defaults, targets):
    
    targets_list = []
    
    for target in targets:
        
        target_configuration = {
        "name": target["name"], 
        "snmp_version": defaults["snmp_version"], 
        "timeout_s": defaults["timeout_s"], 
        "retries": defaults["retries"],
        "target_budget_s": defaults["target_budget_s"],
        "oids": defaults["oids"],
        "ip": target["ip"],
        "community": target["community"],
        "oids": target["oids"]
        }

        targets_list.append(target_configuration)

    return targets_list
        

def build_snmpget_cmd(targets_configuration):
    
    # Empty list to append commands to when they are built.
    snmp_commands = []

    # Going through each targets configuration, and each oid for the target, and builds the snmpget command and appends it to the snmp_commands list.
    for target in targets_configuration:
        for oid in target["oids"]:
            
            # Takes care of v2c, as command is different depending on the version of snmp used.
            if target["snmp_version"] == "v2c":
                cmd = f"snmp -{target["snmp_version"]} -c {target["community"]} {target["ip"]} {oid}"
                snmp_commands.append(cmd)

            # Future support for V3
            # if target["snmp_version"] == "v3":

    return snmp_commands

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

    logging.basicConfig(format=fmt, datefmt=datefmt, filename=logfile, encoding="utf-8", level=numeric_level)

    cfg = load_config(cfg_path)
    build_snmpget_cmd(merge_defaults(cfg["defaults"], cfg["targets"]))

if __name__ == "__main__":
    main()
