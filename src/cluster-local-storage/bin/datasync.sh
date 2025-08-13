#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <dir> <source> <target>"
  exit 1
fi

DIR="${1%/}/"
SOURCE=$2
TARGET=$3

PARTS="${CLUSTER_LOCAL_STORAGE_IPOIB_NUM:-8}"
mnt_path="${CLUSTER_LOCAL_STORAGE_ROOT%/}"
rsync_module="clstore"
tmpdir=$(mktemp -d /tmp/datasync.XXXXXX)
FILELIST="$tmpdir/datasync_filelist"
FILEPREFIX="$tmpdir/datasync_filepart_"

# Generate the list of all files in the specified directory
find "$DIR" -type f > "$FILELIST"

# Split the file list into 8 parts
total_size=0
while IFS= read -r file; do
  size=$(stat -c %s "$file")
  total_size=$((total_size + size))
done < "$FILELIST"
target_size=$(( total_size / PARTS ))
echo "Data total size: $total_size bytes, per NIC size: $target_size bytes"

part=0
current_size=0
output="${FILEPREFIX}${part}"
> "$output"

while IFS= read -r file; do
  size=$(stat -c %s "$file")
  current_size=$(( current_size + size ))
  echo "$file" >> "$output"

  # If the cumulative size meets/exceeds the target (and we aren't on the last part),
  # start a new part.
  if [ "$current_size" -ge "$target_size" ] && [ "$part" -lt "$((PARTS - 1))" ]; then
    part=$(( part + 1 ))
    output="${FILEPREFIX}${part}"
    > "$output"
    current_size=0
  fi
done < "$FILELIST"

for i in $(seq 0 $((PARTS - 1))); do
  PART_FILE="${FILEPREFIX}${i}"
  if [ -f "$PART_FILE" ]; then
    echo "Part $i: $(tr '\n' '\0' < $PART_FILE | du -ch --files0-from=- | awk '/total/{print $1}') bytes, $(wc -l < $PART_FILE) lines"
  fi
done

# rsync files using 8 NICs
ARGS="-aOS --partial --no-o --no-g"
if [ -n "$RSYNC_VERBOSE" ]; then
  ARGS="-avPOS --no-o --no-g"
fi
if [ -n "$RSYNC_PORT" ]; then
  ARGS+=" --port=$RSYNC_PORT"
fi
for i in $(seq 0 $((PARTS - 1))); do
  SOURCE_IDX=$((36#$(echo $SOURCE | rev | cut -c1-2 | rev)))
  TARGET_IDX=$((36#$(echo $TARGET | rev | cut -c1-2 | rev)))
  SOURCE_IPOIB="172.2$i.$(( SOURCE_IDX / 251 )).$(( SOURCE_IDX % 251 + 4 ))"
  TARGET_IPOIB="172.2$i.$(( TARGET_IDX / 251 )).$(( TARGET_IDX % 251 + 4 ))"
  PART_FILE="${FILEPREFIX}${i}"
  if [ -f "$PART_FILE" ]; then
    echo -e "\nData sync $PART_FILE from $SOURCE_IPOIB to $TARGET_IPOIB\n"
    sed -i "s|$mnt_path/||g" "$PART_FILE"
    rsync $ARGS --files-from="$PART_FILE" --address=$SOURCE_IPOIB $mnt_path rsync://$TARGET_IPOIB/$rsync_module &
    sleep 1
  fi
done

# Wait for all background rsync processes to finish
wait

echo "Re-check using Ethernet and delete extraneous files"
rsync $ARGS --delete $DIR $TARGET:$DIR

echo "Data sync completed successfully!"
