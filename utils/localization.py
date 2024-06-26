import yaml


def load_localization():
    """
    Load localization data from a YAML file.

    Returns:
        dict: The loaded localization data.
    """
    with open('localization.yml', 'r', encoding="utf-8") as localization_file:
        localization = yaml.safe_load(localization_file)
    
    return localization