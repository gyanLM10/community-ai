#!/bin/bash
if [ -f .env ]; then export $(grep -v '^#' .env | xargs); fi
echo "🔍 Checking GitHub Token..."
echo "---------------------------------------"
# Test Authentication
RESPONSE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user)
USER_LOGIN=$(echo $RESPONSE | grep -o '"login":"[^"]*"' | cut -d'"' -f4)

if [ -z "$USER_LOGIN" ]; then
    echo "❌ Status: FAILED (Bad Credentials)"
    echo "💡 Tip: Check for extra spaces in your .env or re-copy the token."
else
    echo "✅ Status: VALID (Logged in as $USER_LOGIN)"
    # Check Scopes
    SCOPES=$(curl -sI -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | grep -i "x-oauth-scopes")
    echo "📊 Scopes: $SCOPES"
    
    # Check Org Access
    ORG_CHECK=$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/orgs/openMF | grep -o '"login":"openMF"')
    if [ "$ORG_CHECK" == '"login":"openMF"' ]; then
        echo "✅ Org Access: VALID (Can see openMF)"
    else
        echo "⚠️ Org Access: RESTRICTED"
        echo "💡 Tip: Go to GitHub Settings -> Tokens (classic) -> Configure SSO and Authorize 'openMF'."
    fi
fi
echo "---------------------------------------"
