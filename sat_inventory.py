#!/usr/bin/python
import json
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor

git_dir = '/GitProjects/'
p = os.path.expanduser('~') + git_dir + 'ansible/sat_dynamic_inventory/conf'
sys.path.append(p)

# Now we import config
import config

DEBUG = 0  # Set to 1 for verbose output for debugging

try:
    import requests
except ImportError:
    print("Please install the python-requests module.")
    sys.exit(-1)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Debugging function
def debug(msg):
    if DEBUG == 1:
        print("DEBUG:" + msg)

# Get NUM_THREADS from environment, default to config.NUM_THREADS if not set
NUM_THREADS = int(os.getenv('NUM_THREADS', config.NUM_THREADS))
debug(f"Using {NUM_THREADS} threads for fetching host data")

# Performs a GET using the passed URL location
def get_json(url):
    r = requests.get(url, auth=(config.USERNAME, config.PASSWORD), verify=config.SSL_VERIFY)
    return r.json()

# Fetch results from the API
def get_results(url):
    debug("Attempting to fetch URL: " + url)
    jsn = get_json(url)
    if jsn.get('error'):
        print("Error: " + jsn['error']['message'])
    else:
        return jsn.get('results', jsn)
    return None

# Write data to cache
def write_cache(json_data):
    with open(config.CACHE_FILE, 'w') as outfile:
        json.dump(json_data, outfile)

# Read cache if not expired
def read_cache():
    try:
        stat = os.stat(config.CACHE_FILE)
        if time.time() - stat.st_mtime < config.CACHE_REFRESH:
            with open(config.CACHE_FILE, 'r') as infile:
                return json.load(infile)
    except (OSError, ValueError):
        return None

# Fetch Host Collections and Hosts concurrently with dynamic threads
def get_data():
    json_result = read_cache()
    if json_result:
        debug("Using cached data")
        return json_result

    # Fetch host collections
    hc_list = {}
    hc_results = get_results(config.SAT_SVR + 'katello/api/organizations/1/host_collections?page=1&per_page=' + config.MAX_PER_PAGE)
    for record in hc_results:
        hc_list[record['name']] = record['id']

    # Fetch hosts for each host collection concurrently
    all_data_dict = {}
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = {
            executor.submit(get_results, config.SAT_SVR + 'api/organizations/1/hosts/?search=host_collection_id=' + str(hc_list[hc]) + '&page=1&per_page=' + config.MAX_PER_PAGE): hc for hc in hc_list
        }

        for future in futures:
            hc = futures[future]
            try:
                json_result = future.result()
                if json_result:
                    all_data_dict[hc] = json_result
            except Exception as e:
                debug(f"Error getting details for HC {hc}: {e}")

    write_cache(all_data_dict)
    return all_data_dict

# Parse the JSON results from host collections to build the Ansible inventory
def parse_json_hc(json_result):
    ansible_inventory = {'_meta': {'hostvars': {}}}

    for host_collection, hosts in json_result.items():
        ansible_inventory[host_collection] = [host['certname'] for host in hosts]

    print(json.dumps(ansible_inventory, indent=2))

# Main function
def main():
    json_result = get_data()
    parse_json_hc(json_result)

if __name__ == "__main__":
    main()

