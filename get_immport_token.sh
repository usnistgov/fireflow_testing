#! /usr/bin/env bash

IMMPORT_TOKEN_URL="https://www.immport.org/auth/token"

read -p "Username: " username
read -s -p "Password: " password

curl -qSsLf \
     $IMMPORT_TOKEN_URL \
     -X POST \
     --header 'Accept: application/json;charset=UTF-8' \
     --data-urlencode "username=$username" \
     --data-urlencode "password=$password" | \
    tr -d '[:space:]' | \
    sed 's/.*"access_token":"\([^"]\+\)".*/\1/'
