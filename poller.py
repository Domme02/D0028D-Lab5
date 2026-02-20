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

def load_config(path):
    
    try:
        with open(path, "r", encoding="utf-8") as yml:
            cfg_data = yaml.safe_load(yml)
            
            # Empty file or only comments/whitespaces.
            if cfg_data is None:
                print("Config file is empty.")
                sys.exit(FAILURE)
            
            # Checks for incorrect format of data.
            if not isinstance(cfg_data, dict):
                print("Config root must be a dictionary.")
                sys.exit(FAILURE)

            return cfg_data

    # Handles errors with wrong user input
    except FileNotFoundError:
        print("Error: File not found.")
        sys.exit(FAILURE)
    
    # Handles permission errors.
    except PermissionError:
        print("Error: Permission denied.")
        sys.exit(FAILURE)