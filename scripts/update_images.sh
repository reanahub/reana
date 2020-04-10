#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

SCRIPT_DIRECTORY=$(dirname "$0")
REANA_HELM_CHART_VALUES_YAML_DIR="$SCRIPT_DIRECTORY/../helm/reana"
VALUES_YAML_FILE_NAME='values.yaml'
REANA_HELM_CHART_VALUES_YAML_PATH="$REANA_HELM_CHART_VALUES_YAML_DIR/$VALUES_YAML_FILE_NAME"

# Parameters
if [ "$#" -ne 1 ]; then
  echo "Wrong number of parameters, use:"
  echo ""
  echo -e "\t./update-images.sh <images-txt-file>"
  echo ""
  echo "Examples:"
  echo ""
  echo "To update values.yaml with images in images.txt"
  echo ""
  echo -e "\t./scripts/update-images.sh v0.7.0.txt"
  echo ""
  exit 1
fi

images_file_path=$1

if [ -f "$images_file_path" ]; then
  for image in $(cat $images_file_path);
  do
    image_name=$(echo "$image" | cut -d":" -f1)
    image_tag=$(echo "$image" | cut -d":" -f2)
    if grep "$image_name" "$REANA_HELM_CHART_VALUES_YAML_PATH" | grep -qv "$image_tag"; then
      echo "Updating $image_name to $image_tag."
      sed -i -e "s|$image_name.*|$image_name:$image_tag|g" "$REANA_HELM_CHART_VALUES_YAML_PATH"
      if [ -f "$REANA_HELM_CHART_VALUES_YAML_DIR/values.yaml-e" ]; then
        # remove temporary files created in BSD
        rm "$REANA_HELM_CHART_VALUES_YAML_DIR"/values.yaml-e
      fi
    fi
  done
fi
