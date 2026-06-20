#!/bin/bash
# Replace environment variables in Hadoop XML config files

set -e

SOURCE_CONFIG_DIR="/opt/hadoop/etc/hadoop-template"
TARGET_CONFIG_DIR="/opt/hadoop/etc/hadoop"

echo "Replacing environment variables in Hadoop configs..."
echo "HOST_NAME=${HOST_NAME}"

# Copy template configs to actual config directory
cp -r "$SOURCE_CONFIG_DIR"/* "$TARGET_CONFIG_DIR/"

# Replace ${HOST_NAME} with actual value in all XML files
for file in "$TARGET_CONFIG_DIR"/*.xml; do
    if [ -f "$file" ]; then
        echo "Processing $file"
        sed -i "s/\${HOST_NAME}/${HOST_NAME}/g" "$file"
    fi
done

echo "Environment variables replaced successfully"
