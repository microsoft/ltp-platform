#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

log() {
  local level=$1
  shift
  local message="$*"

  local color='\033[1;33m'
  local reset='\033[0m'

  local timestamp="${color}$(date '+%Y-%m-%d %H:%M:%S')${reset}"
  case "$level" in
    info)
      color='\033[1;32m'
      ;;
    warn | warning)
      color='\033[1;35m'
      ;;
    error)
      color='\033[1;31m'
      ;;
    debug)
      color='\033[1;33m'
      ;;
    *)
      color='\033[1;36m'
      ;;
  esac
  echo -e "${timestamp} ${color}[${level^^}]${reset} $message"
}

# Initialize variables
verbose=0
step=""
path=""
source="$(hostname)"
hostfile=""

# Process options
while getopts "vs:p:h:" opt; do
  case "$opt" in
    v)
      verbose=1
      ;;
    s)
      step="$OPTARG"
      ;;
    p)
      path="$OPTARG"
      ;;
    h)
      hostfile="$OPTARG"
      ;;
    *)
      log error "Usage: $0 -v -s <step> -p <path> -h <hostfile>"
      exit 1
      ;;
  esac
done

# Remove options from the positional parameters list
shift $((OPTIND - 1))

if [ -z "$path" ] || [ -z "$hostfile" ]; then
  log error "Usage: $0 -v -s <step> -p <path> -h <hostfile>"
  exit 1
fi
sed -i "/^$source$/d" $hostfile

# Settings
num_parts=$(wc -l < $hostfile)
mnt_path="/mntext"
tmpdir=$(mktemp -d /tmp/datacopy.XXXXXX)
file_list="$tmpdir/bcast_list"
file_prefix="$tmpdir/bcast_part_"
file_selflist="$tmpdir/bcast_selflist"
script_list="$tmpdir/bcast_sh"

rsync_args="-aO --partial --no-o --no-g"
if [ "$verbose" -eq "1" ]; then
  rsync_args="-avPO --no-o --no-g"
fi
if [ -n "$RSYNC_PORT" ]; then
  rsync_args+=" --port=$RSYNC_PORT"
fi

calc_ipoib_addr() {
  local hca_idx=$1
  local host_idx=$2
  echo "172.2$(( hca_idx % 8 )).$(( host_idx / 251 )).$(( host_idx % 251 + 4 ))"
  # echo "172.16.$(( hca_idx % 8 )).$(( host_idx + 4 ))"
}

# Step 1
# ======
if [ -z "$step" ] || [ "$step" -eq "1" ]; then
  log info "--- Step 1 Started ---"
  timer=$SECONDS

  # Calculate total size and expected part size
  total_size=0
  find "$path" -type f > $file_list
  while IFS= read -r line; do
    size=$(stat -c %s "$line")
    total_size=$((total_size + size))
  done < $file_list
  part_size=$(( total_size / num_parts ))
  log info "Data total size: $total_size bytes, average part size: $part_size bytes"

  # Split file list into n parts according to sizes
  part=0
  current_size=0
  file_part="${file_prefix}$(printf "%03d" $part)"
  >| $file_part
  while IFS= read -r line; do
    size=$(stat -c %s "$line")
    current_size=$(( current_size + size ))
    echo "$line" >> $file_part
    if [ "$current_size" -ge "$((part_size * 389 / 400))" ] && [ "$part" -lt "$((num_parts - 1))" ]; then
      part=$(( part + 1 ))
      current_size=0
      file_part="${file_prefix}$(printf "%03d" $part)"
      >| $file_part
    fi
  done < $file_list
  for part in $(seq 0 $((num_parts - 1))); do
    file_part="${file_prefix}$(printf "%03d" $part)"
    if [ -f "$file_part" ]; then
      log info "Part $part: $( (du -ch $(cat $file_part) || echo '?? total') | grep total | awk '{print $1}') bytes, $(wc -l < $file_part) files"
    fi
  done

  # Push to each node with rsync
  sudo apt-get update -y && sudo apt-get install -y parallel pssh
  parallel-ssh -i -t 30 -p $num_parts -h $hostfile "sudo mkdir -p $path && sudo chown \$USER:\$USER $path"
  rsync_push() {
    local part=$1

    target=$(sed -n "$((part + 1))p" $hostfile)
    file_part="${file_prefix}$(printf "%03d" $part)"

    # Get IPoIB from hostname
    target_idx=$((36#$(echo $target | rev | cut -c1-2 | rev)))
    target_ipoib="$(calc_ipoib_addr $part $target_idx)"
    source_idx=$((36#$(hostname | rev | cut -c1-2 | rev)))
    source_ipoib="$(calc_ipoib_addr $part $source_idx)"

    echo "Rsync push $file_part from $source_ipoib to $target_ipoib ..."
    if [ -f "$file_part" ]; then
      # Hardcode path
      sed -i "s|$mnt_path/||g" $file_part
      rsync $rsync_args --files-from=$file_part --address=$source_ipoib ${mnt_path} rsync://$target_ipoib/paidata
    fi
  }
  export rsync_args mnt_path file_prefix hostfile
  export -f calc_ipoib_addr rsync_push
  parallel -j $num_parts rsync_push ::: $(seq 0 $((num_parts - 1)))

  log timer "Finished in $((SECONDS - timer)) seconds"
  log info "--- Step 1 Completed Successfully ---"
fi

# Step 2
# ======
if [ -z "$step" ] || [ "$step" -eq "2" ]; then
  log info "--- Step 2 Started ---"
  timer=$SECONDS

  # Prepare a bash file with rsync commands
  >| $script_list
  mapfile -t hosts < $hostfile
  for (( i=0; i<${#hosts[@]}; i++ )); do
    source_idx=$((36#$(echo ${hosts[i]} | rev | cut -c1-2 | rev)))
    for (( j=0; j<${#hosts[@]}; j++ )); do
      target_idx=$((36#$(echo ${hosts[j]} | rev | cut -c1-2 | rev)))
      if [ "$i" -ne "$j" ]; then
        no=$((i + j))
        # Get IPoIB from hostname
        source_ipoib="$(calc_ipoib_addr $no $source_idx)"
        target_ipoib="$(calc_ipoib_addr $no $target_idx)"

        # Hardcode path
        echo "${hosts[i]},${hosts[j]},rsync $rsync_args --files-from=$file_selflist --address=$source_ipoib ${mnt_path} rsync://$target_ipoib/paidata" >> $script_list
      fi
    done
  done
  log info "Generated $script_list file."

  parallel-ssh -i -t 30 -p $num_parts -h $hostfile "mkdir -p $tmpdir && find $path -type f | sed \"s|$mnt_path/||g\" > $file_selflist"
  log info "Prepared $file_selflist file."
  parallel-ssh -i -t 30 -p $num_parts -h $hostfile "sudo apt-get install -y parallel"
  parallel-scp -t 120 -p $num_parts -h $hostfile $script_list $script_list
  log info "Distributed $script_list file."

  # Execute via parallel
  log info "Rsync push in parallel ..."
  parallel-ssh -i -t 0 -p 150 -h $hostfile "cat $script_list | grep -i ^\$(hostname) | cut -d, -f3 | parallel -j $num_parts"

  # Re-check by re-run
  log info "Rsync again to re-check ..."
  parallel-ssh -i -t 0 -p 32 -h $hostfile "cat $script_list | grep -i ^\$(hostname) | cut -d, -f3 | parallel -j $num_parts"

  log timer "Finished in $((SECONDS - timer)) seconds"
  log info "--- Step 2 Completed Successfully ---"
fi
