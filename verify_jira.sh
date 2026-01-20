#!/bin/bash
# 1. Path to your .env
ENV_PATH="./MCP_Enhancement/.env"

if [ -f "$ENV_PATH" ]; then
  # Load Jira variables specifically
  export JIRA_URL=$(grep '^JIRA_URL=' "$ENV_PATH" | cut -d'=' -f2-)
  export JIRA_EMAIL=$(grep '^JIRA_EMAIL=' "$ENV_PATH" | cut -d'=' -f2-)
  export JIRA_API_TOKEN=$(grep '^JIRA_API_TOKEN=' "$ENV_PATH" | cut -d'=' -f2-)
else
  echo "❌ ERROR: .env file not found at $ENV_PATH"
  exit 1
fi

echo "🔍 Verifying Jira Connection..."
echo "---------------------------------------"

# 2. Check if variables are empty
if [[ -z "$JIRA_URL" || -z "$JIRA_EMAIL" || -z "$JIRA_API_TOKEN" ]]; then
    echo "❌ ERROR: Jira variables are missing in your .env file."
    exit 1
fi

# 3. Test the connection
# Jira Cloud requires Basic Auth with "email:token"
RESPONSE=$(curl -s -w "%{http_code}" -u "$JIRA_EMAIL:$JIRA_API_TOKEN" -X GET "$JIRA_URL/rest/api/3/myself")
HTTP_CODE=$(echo "$RESPONSE" | tail -c 3)

if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ SUCCESS: Jira authenticated as $JIRA_EMAIL"
    echo "📊 Status: Connected to $JIRA_URL"
else
    echo "❌ FAILED: Jira rejected the connection (HTTP $HTTP_CODE)"
    if [ "$HTTP_CODE" == "401" ]; then
        echo "💡 Tip: Double-check your Email and API Token. (Note: Use your real email, not your Slack username)."
    elif [ "$HTTP_CODE" == "404" ]; then
        echo "💡 Tip: Check your JIRA_URL. It should look like https://your-domain.atlassian.net"
    fi
fi
echo "---------------------------------------"
