import yaml


def load_config():
    """
    Load configuration data from a YAML file.

    Returns:
        dict: The loaded configuration data.
    """
    with open('config.yml', 'r', encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    
    return config