#!/bin/bash

#Trying to find the optimal thread max for concurrent requests to satellite.

for i in $(seq 5 5 60); do
  echo "testing with $i threads"
  rm ~/inventory_cache.json
  time NUM_THREADS=${i} python -m cProfile -s time sat_inventory_opt.py > profile_output_t_${i}.txt
  echo "----"
  sleep 60
done
