import os
import json
import logging
import requests
from typing import Optional, List, Dict

# FastMCP for the Server
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Slack SDK for Professional Formatting (Block Kit)
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    SLACK_SDK_AVAILABLE = True
except ImportError:
    SLACK_SDK_AVAILABLE = False

# Load environment variables
load_dotenv()

# Initialize the AI Agent
mcp = FastMCP("Mifos-Enhancement-Agent")

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- HELPER FUNCTIONS ---

def safe_preview(token_name):
    """Helper to safely preview a token's existence."""
    val = os.getenv(token_name)
    if not val: return "❌ Missing"
    return f"✅ Ready (...{val[-4:]})"


def get_jira_auth():
    """Returns the tuple for Basic Auth (Email, Token)."""
    return (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))


def get_slack_client():
    """Safely returns the Slack WebClient."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token or not SLACK_SDK_AVAILABLE:
        return None
    return WebClient(token=token)


def _create_block_kit_summary(title: str, content: str, is_draft: bool) -> List[Dict]:
    """Helper to build a professional Slack UI message."""
    header_text = f"🧪 [DRAFT] {title}" if is_draft else f"📄 {title}"
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": content}
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "*Source: Mifos Enhancement Agent | Combined Context*"}]
        }
    ]


# --- TOOLS ---

@mcp.tool()
def check_full_system_status():
    """Checks the connection status of ALL integrations."""
    slack_status = f"✅ SDK Ready (...{os.getenv('SLACK_BOT_TOKEN')[-4:]})" if SLACK_SDK_AVAILABLE and os.getenv(
        'SLACK_BOT_TOKEN') else "❌ SDK/Token Missing"

    status_report = [
        f"🐙 GitHub: {safe_preview('GITHUB_TOKEN')}",
        f"💬 Slack:  {slack_status}",
        f"📋 Jira:   {os.getenv('JIRA_URL') or '❌'} | {safe_preview('JIRA_API_TOKEN')}"
    ]
    return "\n".join(status_report)


import os
import requests
from mcp.server.fastmcp import FastMCP


# Assuming your auth and initialization are already defined above
# ...

@mcp.tool()
def get_jira_ticket_details(ticket_key: str):
    """
    [READ-ONLY] Fetches a Jira ticket's summary, description, AND comments.
    Includes a duplicate filter for comments to ensure a clean consensus summary.
    """
    jira_url = os.getenv("JIRA_URL")
    if not jira_url:
        return "❌ Error: JIRA_URL not set."

    def parse_adf_text(adf_node):
        """Helper to recursively extract all plain text from Jira's ADF format."""
        if not adf_node:
            return ""
        texts = []
        if isinstance(adf_node, dict):
            if adf_node.get("type") == "text":
                texts.append(adf_node.get("text", ""))
            for value in adf_node.values():
                if isinstance(value, (dict, list)):
                    texts.append(parse_adf_text(value))
        elif isinstance(adf_node, list):
            for item in adf_node:
                texts.append(parse_adf_text(item))
        return " ".join(filter(None, texts))

    try:
        url = f"{jira_url}/rest/api/3/issue/{ticket_key}"
        resp = requests.get(url, auth=get_jira_auth())

        if resp.status_code != 200:
            return f"❌ Error fetching ticket {ticket_key}: {resp.status_code}"

        data = resp.json()
        fields = data.get("fields", {})
        summary = fields.get("summary", "No Summary")

        # Extract Description
        description = parse_adf_text(fields.get("description")) or "No Description"

        # 2. Get Comments & Apply Duplicate Filter
        comments_data = fields.get("comment", {}).get("comments", [])
        comments_text = []
        seen_comments = set()  # Memory to track unique comments

        for c in comments_data:
            author = c.get("author", {}).get("displayName", "Unknown")
            # Extract text from the complex ADF body
            body = parse_adf_text(c.get("body")).strip()

            # UNIQUE FILTER: Only add if we haven't seen this exact text before
            if body and body not in seen_comments:
                comments_text.append(f"- {author}: {body}")
                seen_comments.add(body)

        # Assemble the final report
        discussion = "\n".join(comments_text) if comments_text else "No comments found."

        full_context = (
            f"**Ticket:** {ticket_key}\n"
            f"**Summary:** {summary}\n"
            f"**Description:** {description}\n\n"
            f"**Discussion/Comments:**\n{discussion}"
        )
        return full_context

    except Exception as e:
        return f"❌ Exception reading Jira: {str(e)}"

@mcp.tool()
def search_slack_history(query: str):
    """
    [READ-ONLY] Searches Slack history for keywords (e.g., 'payment bug', 'release 1.2').
    """
    client = get_slack_client()
    if not client: return "❌ Slack SDK or Token missing."

    try:
        # Requires 'search:read' scope
        result = client.search_messages(query=query, count=5)
        matches = result.get("messages", {}).get("matches", [])
        if not matches: return f"No discussions found for '{query}'."

        formatted = [f"- {m['username']} (in {m['channel']['name']}): {m['text']}" for m in matches]
        return "\n".join(formatted)
    except SlackApiError as e:
        return f"❌ Slack Search Error: {e.response['error']}"


@mcp.tool()
def post_mifos_summary(title: str, summary_content: str, channel_id: str = None, is_draft: bool = True):
    """
    Posts a summary to a private DM by default for Shadow Testing.
    """
    client = get_slack_client()
    if not client: return "❌ Slack SDK/Token missing."

    # Use your Member ID from .env
    user_id = channel_id or os.getenv("MY_SLACK_ID")
    if not user_id: return "❌ No Member ID found in .env"

    try:
        # Step A: Open a private DM 'pipe' with the user
        dm_channel = client.conversations_open(users=user_id)
        target_dm_id = dm_channel["channel"]["id"]

        # Step B: Build and Send the message
        blocks = _create_block_kit_summary(title, summary_content, is_draft)
        resp = client.chat_postMessage(channel=target_dm_id, blocks=blocks, text=title)

        return f"✅ Private DM sent successfully to you."
    except SlackApiError as e:
        return f"❌ Slack Error: {e.response['error']}"


@mcp.tool()
def create_jira_task(summary: str, description: str, project_key: str = "MM", issue_type: str = "Task"):
    """
    [WRITE] Creates a Jira ticket. Default type is 'Task' (better for Docs/Cleanup than 'Bug').
    """
    jira_url = os.getenv("JIRA_URL")
    if not jira_url: return "❌ Error: JIRA_URL is not set."

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
            },
            "issuetype": {"name": issue_type}
        }
    }

    try:
        resp = requests.post(f"{jira_url}/rest/api/3/issue", json=payload, auth=get_jira_auth())
        if resp.status_code == 201:
            key = resp.json().get("key")
            return f"✅ Ticket Created ({issue_type}): {key}\n🔗 {jira_url}/browse/{key}"
        return f"❌ Failed: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


@mcp.tool()
def check_jira_for_ui_assets(ticket_key: str):
    """
    Checks a Jira ticket for image attachments (screenshots of UI changes).
    This addresses the mentor's point that UI changes are stored in Jira.
    """
    jira_url = os.getenv("JIRA_URL")
    url = f"{jira_url}/rest/api/3/issue/{ticket_key}?fields=attachment,summary"

    try:
        resp = requests.get(url, auth=get_jira_auth())
        data = resp.json()
        attachments = data.get("fields", {}).get("attachment", [])

        image_list = []
        for a in attachments:
            if a['mimeType'].startswith('image/'):
                image_list.append(f"📸 Image Found: {a['filename']} (Link: {a['content']})")

        if not image_list:
            return f"No UI screenshots found in {ticket_key}."

        return f"UI Assets for {ticket_key}:\n" + "\n".join(image_list)
    except Exception as e:
        return f"Error checking Jira attachments: {str(e)}"

if __name__ == "__main__":
    mcp.run()