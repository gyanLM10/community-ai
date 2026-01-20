#!/bin/bash
if [ -f .env ]; then export $(grep -v '^#' .env | xargs); fi
echo "🔍 Checking Slack Tokens..."
echo "---------------------------------------"
# Bot Token Test
curl -s -X POST -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
     -H "Content-type: application/json" \
     https://slack.com/api/auth.test | grep -q '"ok":true' && echo "✅ Bot Token: VALID" || echo "❌ Bot Token: FAILED"
# App Token Test
curl -s -X POST -H "Authorization: Bearer $SLACK_APP_TOKEN" \
     -H "Content-type: application/json" \
     https://slack.com/api/apps.connections.open | grep -q '"ok":true' && echo "✅ App Token: VALID" || echo "❌ App Token: FAILED"
echo "---------------------------------------"
