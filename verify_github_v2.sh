#!/bin/bash
# 1. Load only valid lines (ignore comments and empty lines)
if [ -f .env ]; then
  export $(grep -v '^#' .env | grep '=' | xargs)
fi

echo "🔍 Verifying GitHub Connection..."
echo "---------------------------------------"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ ERROR: GITHUB_TOKEN is not set in your .env file."
    exit 1
fi

# 2. Test the token with a verbose check
RESULT=$(curl -s -w "%{http_code}" -o response.json -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user)
HTTP_CODE=$(echo "$RESULT" | tail -c 3)

if [ "$HTTP_CODE" == "200" ]; then
    USER_LOGIN=$(grep -o '"login":"[^"]*"' response.json | head -1 | cut -d'"' -f4)
    echo "✅ SUCCESS: Logged in as $USER_LOGIN"
    
    # 3. Check for Organization (Mifos/openMF) Access
    ORG_STATUS=$(curl -s -o /dev/null -I -w "%{http_code}" -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/orgs/openMF)
    if [ "$ORG_STATUS" == "200" ]; then
        echo "✅ ORG ACCESS: Confirmed (openMF is visible)"
    else
        echo "⚠️ ORG ACCESS: Restricted (Code $ORG_STATUS)"
        echo "👉 Solution: Go to GitHub Settings -> Tokens (classic) -> Configure SSO -> Authorize 'openMF'"
    fi
else
    echo "❌ FAILED: GitHub rejected the token (HTTP $HTTP_CODE)"
    echo "Check response.json for details."
fi
rm response.json
echo "---------------------------------------"
