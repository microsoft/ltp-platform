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

PARTS=8
tmpdir=$(mktemp -d /tmp/datasync.XXXXXX)
FILELIST="$tmpdir/datasync_filelist"
FILEPREFIX="$tmpdir/datasync_filepart_"

# Generate the list of all files in the specified directory
find "$DIR" -type f > "$FILELIST"

# Split the file list into 8 parts
#split -n l/8 -d "$FILELIST" "$FILEPREFIX"
#total_size=$(du -cb $(cat $FILELIST) | grep total | awk '{print $1}')
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

for i in {0..7}; do
    PART_FILE="${FILEPREFIX}${i}"
    echo "Part $i: $( (du -ch $(cat $PART_FILE) || echo '?? total') | grep total | awk '{print $1}') bytes, $(wc -l < $PART_FILE) lines"
done

# rsync files using 8 NICs
ARGS="-aO --partial --no-o --no-g"
if [ "$RSYNC_VERBOSE" -eq "1" ]; then
  ARGS="-avPO --no-o --no-g"
fi
if [ -n "$RSYNC_PORT" ]; then
  ARGS+=" --port=$RSYNC_PORT"
fi
ssh $TARGET "sudo mkdir -p -m 777 $DIR"
for i in {0..7}; do
    SOURCE_IDX=$((36#$(echo $SOURCE | rev | cut -c1-2 | rev)))
    TARGET_IDX=$((36#$(echo $TARGET | rev | cut -c1-2 | rev)))
    SOURCE_IPOIB="172.2$i.$(( SOURCE_IDX / 251 )).$(( SOURCE_IDX % 251 + 4 ))"
    TARGET_IPOIB="172.2$i.$(( TARGET_IDX / 251 )).$(( TARGET_IDX % 251 + 4 ))"
    PART_FILE="${FILEPREFIX}${i}"
    echo -e "\nData sync $PART_FILE from $SOURCE_IPOIB to $TARGET_IPOIB\n"
    sed -i 's/\/mntext\///g' "$PART_FILE"
    rsync $ARGS --files-from="$PART_FILE" --address=$SOURCE_IPOIB /mntext rsync://$TARGET_IPOIB/paidata &
    sleep 1
done

# Wait for all background rsync processes to finish
wait

echo "Re-check using Ethernet"
rsync $ARGS $DIR $TARGET:$DIR

echo "Data sync completed successfully!"
