#!/usr/bin/python3
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from requests.exceptions import HTTPError, ConnectionError, Timeout
import requests
import urllib3
import importlib.util

# Paths and Constants
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../conf/config.py'))

# Dynamically load the config module
try:
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
except (FileNotFoundError, ImportError) as e:
    raise SystemExit(f"Error: Could not import config. Please ensure the config file is present at {config_path}. Error: {e}")

log_messages = []

DEBUG = 0  # Global debug flag

def debug(msg):
    """Store a debug message in the global log buffer."""
    if DEBUG == 1:
        log_messages.append(f"[DEBUG]: {msg}")

def warn(msg):
    """Store a warning message in the global log buffer."""
    log_messages.append(f"[WARN]: {msg}")

def error(msg):
    """Print an error message to stderr, flush logs, and exit the script."""
    sys.stderr.write(f"[ERROR]: {msg}\n")
    print_logs()
    raise SystemExit(1)

def print_logs():
    """Flush all buffered log messages to stderr."""
    for message in log_messages:
        sys.stderr.write(f"{message}\n")

if config.SSL_VERIFY == False:
    """Suppress SSL warnings if SSL verification is disabled."""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration defaults
DEFAULT_NUM_THREADS = 16
DEFAULT_CACHE_REFRESH = 28800  # 8 hours
DEFAULT_MAX_PER_PAGE = '1000'
DEFAULT_RETRY_COUNT = 3

RETRY_COUNT = getattr(config, 'RETRY_COUNT', DEFAULT_RETRY_COUNT)

def validate_config():
    """Validate required configuration settings and set defaults where needed."""
    required_settings = ['SAT_SVR', 'USERNAME', 'PASSWORD', 'CACHE_FILE']
    for setting in required_settings:
        if not hasattr(config, setting) or not getattr(config, setting):
            error(f"Missing required configuration value for {setting}. Please check your config file at {config_path}.")

    def set_with_default(attr_name, default_value, env_var=None):
        """Set configuration value with optional default and environment variable override."""
        if env_var:
            value = os.getenv(env_var, None)
            if value is not None:
                debug(f"{attr_name} set via environment variable {env_var}: {value}")
                return type(default_value)(value)

        if not hasattr(config, attr_name) or getattr(config, attr_name) in (None, '', 'None'):
            warn(f"{attr_name} not found in config. Using default: {default_value}")
            return default_value
        return getattr(config, attr_name)

    config.NUM_THREADS = set_with_default('NUM_THREADS', DEFAULT_NUM_THREADS, 'NUM_THREADS')
    config.CACHE_REFRESH = set_with_default('CACHE_REFRESH', DEFAULT_CACHE_REFRESH)
    config.MAX_PER_PAGE = set_with_default('MAX_PER_PAGE', DEFAULT_MAX_PER_PAGE)

    debug(f"Using {config.NUM_THREADS} threads for fetching host data")

def get_json(url, retry_count=RETRY_COUNT, delay=2):
    """Fetch JSON data from the given URL, with retries for transient errors."""
    for attempt in range(1, retry_count + 1):
        try:
            r = requests.get(url, auth=(config.USERNAME, config.PASSWORD), verify=config.SSL_VERIFY)
            r.raise_for_status()
            debug(f"Received response: {r.text[:200]}...")
            return r.json()
        except (HTTPError, ConnectionError, Timeout) as http_err:
            warn(f"Attempt {attempt}/{retry_count} failed: {http_err} for URL: {url}. Retrying in {delay} seconds...")
            if attempt < retry_count:
                time.sleep(delay)
        except Exception as err:
            error(f"An error occurred: {err}")
            break
    return None

def get_results(url):
    """Fetch and validate results from the specified API endpoint."""
    debug(f"Attempting to fetch URL: {url}")
    jsn = get_json(url)
    if jsn is None:
        error(f"No response or invalid JSON returned from {url}")
        return None
    if isinstance(jsn, dict):
        debug(f"Fetched JSON: {json.dumps(jsn)[:200]}...")
        if 'error' in jsn and jsn['error'] is not None:
            error(f"Error: {jsn['error'].get('message', 'Unknown error')}")
            return None
        return jsn.get('results', jsn)
    else:
        error(f"Received an unexpected JSON structure from {url}")
    return None

def write_cache(json_data):
    """Write the provided JSON data to the cache file."""
    try:
        with open(config.CACHE_FILE, 'w') as outfile:
            json.dump(json_data, outfile)
    except IOError as e:
        error(f"Error writing to cache file {config.CACHE_FILE}: {e}")

def read_cache():
    """Read and return cached JSON data if it exists and is not expired."""
    try:
        stat = os.stat(config.CACHE_FILE)
        if time.time() - stat.st_mtime < config.CACHE_REFRESH:
            with open(config.CACHE_FILE, 'r') as infile:
                return json.load(infile)
    except (OSError, ValueError):
        return None

def get_hc():
    """Fetch and return the list of current host collections."""
    hc_list = {}
    hc_results = get_results(config.SAT_SVR + f'katello/api/organizations/1/host_collections?page=1&per_page={config.MAX_PER_PAGE}')
    if not hc_results:
        error("Failed to fetch host collections.")
    for record in hc_results:
        hc_list[record['name']] = record['id']
    return hc_list

def get_hcdata(hc_list):
    """Fetch data for the given list of host collections."""
    all_data_dict = {}
    with ThreadPoolExecutor(max_workers=config.NUM_THREADS) as executor:
        futures = {
            executor.submit(get_results, config.SAT_SVR + f'api/organizations/1/hosts/?search=host_collection_id={hc_list[hc]}&page=1&per_page={config.MAX_PER_PAGE}'): hc for hc in hc_list
        }

        for future in futures:
            hc = futures[future]
            try:
                json_result = future.result()
                if json_result:
                    all_data_dict[hc] = json_result
                else:
                    all_data_dict[hc] = []
            except Exception as e:
                error(f"Error getting details for HC {hc}: {e}")
                all_data_dict[hc] = []
    return all_data_dict

def get_data():
    """Main function to fetch host collections, update cache, and return full data."""
    hc_list = get_hc()
    cached_data = read_cache() or {}

    # Fetch all cached HC names
    cached_hc_names = set(cached_data.keys())

    # Identify new HCs that need to be fetched from Satellite
    new_hcs = {name: hc_list[name] for name in hc_list if name not in cached_hc_names}

    # Identify removed HCs that need to be pruned from the cache
    removed_hcs = cached_hc_names - set(hc_list.keys())

    if new_hcs:
        debug(f"Found new host collections: {new_hcs.keys()}")
        new_data = get_hcdata(new_hcs)
        cached_data.update(new_data)

    if removed_hcs:
        debug(f"Removing deleted host collections from cache: {removed_hcs}")
        for hc in removed_hcs:
            del cached_data[hc]

    # Finally, write the updated cache with new and removed HCs handled
    write_cache(cached_data)
    
    return cached_data

def parse_json_hc(json_result):
    """Parse and print the JSON results in Ansible inventory format."""
    ansible_inventory = {'_meta': {'hostvars': {}}}
    for host_collection, hosts in json_result.items():
        ansible_inventory[host_collection] = [host['certname'] for host in hosts]

    print(json.dumps(ansible_inventory, indent=2))

def main():
    """Main function to validate config, fetch data, and print inventory."""
    validate_config()
    json_result = get_data()
    parse_json_hc(json_result)
    print_logs()

if __name__ == "__main__":
    main()

