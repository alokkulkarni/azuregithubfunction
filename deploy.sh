#!/bin/bash

# Read values from local.settings.json
GITHUB_TOKEN=$(grep -o '"GITHUB_TOKEN": *"[^"]*"' local.settings.json | cut -d'"' -f4)
GITHUB_ORG=$(grep -o '"GITHUB_ORG": *"[^"]*"' local.settings.json | cut -d'"' -f4)
GITHUB_REPOS=$(grep -o '"GITHUB_REPOS": *"[^"]*"' local.settings.json | cut -d'"' -f4)

# Validate required values
if [ -z "$GITHUB_TOKEN" ] || [ -z "$GITHUB_ORG" ] || [ -z "$GITHUB_REPOS" ]; then
    echo "Error: Required values not found in local.settings.json"
    exit 1
fi

# Create deployment package
echo "Creating deployment package..."
echo $GITHUB_TOKEN
echo $GITHUB_ORG
echo $GITHUB_REPOS

func azure functionapp publish $1 --python

# Configure application settings
echo "Configuring application settings..."
az functionapp config appsettings set --name $1 --resource-group $2 --settings \
    GITHUB_TOKEN="$GITHUB_TOKEN" \
    GITHUB_ORG="$GITHUB_ORG" \
    GITHUB_REPOS="$GITHUB_REPOS"

echo "Deployment completed!" 