import configparser
import os

def load_nmr_config():
    config = configparser.ConfigParser()
    # Path relative to project root
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini not found at {config_path}")
    
    config.read(config_path, encoding='utf-8')
    if 'NMR' not in config:
        raise ValueError("[NMR] section missing in config.ini")
    
    return dict(config['NMR'])
