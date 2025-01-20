#!/bin/bash

#examle:
INVENTORY="../git/ansible/sat_dynamic_inventory/stat_and_dyn/${USER}_CONTAINERS"

cat << EOF
{
  "_meta": {}
}
EOF

if [ -n "$container" ] && [ "$container" == "podman" ]; then
  # "Running inside a Podman container" do not update inventory
  exit 0
else
  echo '[CONTAINERS]' > $INVENTORY
  podman ps | tail -n +2 | awk '{print $NF" ansible_connection=podman ansible_python_interpreter=auto"}' >> $INVENTORY

  # Special case for RHEL 6 servers
  echo "[RHEL_6_Servers]" >> $INVENTORY
  podman ps | tail -n +2 | grep "r6_" | awk '{print $NF" ansible_connection=ssh ansible_python_interpreter=/usr/bin/python"}' >> $INVENTORY

  #for version in 7 8 9; do
  #  echo "[RHEL_${version}_Servers]" >> $INVENTORY
  #  podman ps | tail -n +2 | grep "r${version}_" | awk '{print $NF" ansible_connection=podman ansible_python_interpreter=auto"}' >> $INVENTORY
  #done
fi

