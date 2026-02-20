import yaml

def load_config(path):
    
    try:
        with open(path, "r", encoding="utf-8") as yml:
            cfg_data = yaml.safe_load(yml)
            if not isinstance(cfg_data, dict):
                raise TypeError("YAML root must be a dictionary")
            return cfg_data

    except FileNotFoundError:
        print("Error: File not found.")
    except PermissionError:
        print("Error: Permission denied.")
    except yaml.YAMLError as e:
        print(f"YAML parsing error: {e}")
    except TypeError as e:
        print("Type error: {e}")

    return 2
    
#def validate_config(cfg):
    



print(load_config("config2.yml"))



# {'defaults': {'snmp_version': 'v2c', 'timeout_s': 2.5, 'retries': 1, 'target_budget_s': 10, 'oids': ['sysUpTime.0', 'sysName.0']}, 'targets': [{'name': 'device_name', 'ip': '172.16.0.240', 'community': 'public', 'oids': ['ifOperStatus.1']}, {'name': 'router2', 'ip': '10.0.0.2', 'community': 'public', 'oids': ['sysName.0']}]}

