# Ansible Satellite Dynamic and Static Inventory

This project integrates **dynamic and static inventories** for use with Ansible, enabling seamless interaction with Red Hat Satellite and additional hosts.

## Features

- Query dynamic host collections directly from Satellite.
- Manage static hosts not present in Satellite.
- Combine dynamic and static inventories for unified host management.

---

## File Structure

- **`stat_and_dyn/sat_inventory.py`**: Python script to query the Satellite server.
- **`stat_and_dyn/stat_hosts`**: Static inventory file for non-Satellite hosts. Ensure changes are committed and pushed.
- **`conf/config.py`**: Configuration file for the dynamic inventory. If missing, create it by copying the default template:
  ```bash
  cp conf/config.py.default conf/config.py
  ```

---

## Requirements

- **Credentials**: Create a `ansible_inventory` user in the Satellite server with read-only access.
- **Python Version**: Ensure compatibility with Python 3.x.
- **Dependencies**: Verify required libraries are installed (e.g., `requests`).
- **Ansible Compatibility**: Tested with Ansible 2.10+.

---

## Configuration

1. Copy the default configuration template:
   ```bash
   cp conf/config.py.default conf/config.py
   ```
2. Update `conf/config.py` with your Satellite server credentials and other required settings.
3. Ensure `ansible.cfg` is properly set up to point to the correct inventory and roles directories.

---

## Usage

### List Available Host Collections

Use the `sat_inventory.py` script to query and list available host collections:
```bash
./stat_and_dyn/sat_inventory.py | grep '\['
```

### Query Hosts with Intersections

Query hosts by intersecting specific collections (e.g., RHEL 6 servers in production):
```bash
ansible -i stat_and_dyn/ 'RHEL_6_Servers:&PROD' --list-hosts
```

---

## Example Outputs

### Listing Host Collections

```bash
$ ./stat_and_dyn/sat_inventory.py | grep '\['
[RHEL_8_Servers]
[RHEL_9_Servers]
[PROD]
[NON_PROD]
[...] 
```

### Query Intersection of Collections

```bash
$ ansible -i stat_and_dyn/ 'RHEL_6_Servers:&PROD' --list-hosts
  rhel6-prod1.example.com
  rhel6-prod2.example.com
```

---

## Notes

- Ensure the `stat_and_dyn/stat_hosts` file is up to date for accurate static inventory management.
- Always validate configuration changes before using in production.
- For convenience, symlink the utilities for easier usage:
  ```bash
  mkdir -p ~/bin
  ln -s $(pwd)/utils/* ~/bin/
  ```
- For troubleshooting, refer to the Ansible and Satellite logs.

---

Happy automating! 🚀


