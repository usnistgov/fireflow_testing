#! /usr/bin/env bash

# step 1: get list of all studies that mention "flow cytometry" (or similar)

study_ids=$(
    curl -qSsLf \
         --header "Authorization: bearer $IMMPORT_TOKEN" \
         --header "Content-Type: application/json" \
         -G \
         --data-urlencode "assayMethod=CyTOF" \
         --data-urlencode "assayMethod=Flow Cytometry" \
         --data-urlencode "assayMethod=Spectral Flow Cytometry" \
         --data-urlencode "assayMethod=Intracellular Cytokine Stain Flow Cytometric Assay" \
         --data-urlencode "pageSize=2000" \
         "https://www.immport.org/data/query/api/search/study" | \
        jq -r '.hits.hits.[]._id' | \
        sed 's/SDY//' | \
        sort -k1,1n | \
        sed 's/^/SDY/' | \
        tr '\n' ' '
    )

# step 2: dump all file paths relating to these studies

for s in $study_ids; do
    curl -qSsLf \
         --header "Authorization: bearer $IMMPORT_TOKEN" \
         --header "Content-Type: application/json" \
         "https://www.immport.org/data/query/api/study/filePath/$s" | \
        jq -r '.[].path'
done
