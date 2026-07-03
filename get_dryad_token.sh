#! /usr/bin/env bash

DRYAD_TOKEN_URL="https://datadryad.org/oauth/token"

read -p "Client ID: " clientid
read -s -p "Client Secret: " client_secret

curl -qSsLf \
     $DRYAD_TOKEN_URL \
     -X POST \
     -H "Content-Type: application/x-www-form-urlencoded;charset=UTF-8" \
     --data-urlencode "client_id=$clientid" \
     --data-urlencode "client_secret=$client_secret" \
     --data-urlencode "grant_type=client_credentials" |\
    sed 's/.*"access_token":"\([^"]\+\)".*/\1/'
