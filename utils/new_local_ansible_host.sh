#!/bin/bash

# Function to display usage information
usage() {
    echo "Usage: $0 <host> <inventory>"
    echo "  <host>      - The hostname to resolve"
    echo "  <inventory> - The Ansible inventory file to update"
    exit 1
}

# Check if the correct number of arguments is provided
if [ "$#" -ne 2 ]; then
    echo "Error: Incorrect number of arguments"
    usage
fi

# Assign arguments to variables
host=$1
inventory=$2

# Validate that the inventory file exists and is writable
if [ ! -w "$inventory" ]; then
    echo "Error: Inventory file '$inventory' does not exist or is not writable"
    usage
fi

# Resolve the IP address of the host using getent first, then fallback to dig
ip=$(getent hosts "$host" | awk '{ print $1 }')
if [ -z "$ip" ]; then
  ip=$(dig +short "$host")
fi

# Check if the host was successfully resolved
if [ -z "$ip" ]; then
    echo "Error: Failed to resolve host '$host'"
    exit 1
fi

# Append the host and IP to the inventory file
echo "$host ansible_host=${ip}" >> "$inventory"
echo "Successfully added '$host ansible_host=${ip}' to '$inventory'"

