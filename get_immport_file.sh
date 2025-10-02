#! /usr/bin/env bash

# somewhat hacky, download the first step of the snakemake pipeline to get ascp

aspera_dir=resources/tools/immport-data-download-tool/aspera/cli
ascp_cmd=$aspera_dir/bin/linux/ascp
ascp_key=$aspera_dir/etc/asperaweb_id_dsa.openssh

token=$(
    curl -qSsLf \
         --header "Authorization: bearer $IMMPORT_TOKEN" \
         --header "Content-Type: application/json" \
         -X POST \
         --data "{\"paths\": [\"$1\"]}" \
         "https://www.immport.org/data/download/token" | \
        jq -r '.token'
    )

if ! [ -z $token ]; then 
    "$ascp_cmd" \
        --user databrowser \
        -O33001 \
        -P33001 \
        -i "$ascp_key" \
        -W "$token" \
        "aspera-immport.niaid.nih.gov:$1" "$2"
fi
