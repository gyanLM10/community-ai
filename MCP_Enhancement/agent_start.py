import os
import logging
import requests
import re
from typing import Optional, List, Dict

# Environment & Server
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_sdk.errors import SlackApiError

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Slack Bolt App (The Listener)
slack_app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)
app_handler = AsyncSlackRequestHandler(slack_app)

# Initialize FastAPI (The Web Server)
api = FastAPI()


# --- HELPER FUNCTIONS (From Phase 1) ---

def get_jira_auth():
    """Returns the tuple for Basic Auth (Email, Token)."""
    return (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))


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


def _create_block_kit_summary(title: str, content: str) -> List[Dict]:
    """Helper to build a professional Slack UI message."""
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📄 {title}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": content}
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "*Source: Mifos Enhancement Agent | Phase 2 Listener*"}]
        }
    ]


# --- CORE LOGIC (The Tools) ---

async def get_jira_ticket_details(ticket_key: str):
    """Fetches Jira ticket summary, description, AND comments with duplicate filter."""
    jira_url = os.getenv("JIRA_URL")
    if not jira_url: return "❌ Error: JIRA_URL not set."

    try:
        url = f"{jira_url}/rest/api/3/issue/{ticket_key}"
        resp = requests.get(url, auth=get_jira_auth())

        if resp.status_code != 200:
            return f"❌ Error fetching ticket {ticket_key}: {resp.status_code}"

        data = resp.json()
        fields = data.get("fields", {})
        summary = fields.get("summary", "No Summary")
        description = parse_adf_text(fields.get("description")) or "No Description"

        # Comments with Duplicate Filter
        comments_data = fields.get("comment", {}).get("comments", [])
        comments_text = []
        seen_comments = set()

        for c in comments_data:
            author = c.get("author", {}).get("displayName", "Unknown")
            body = parse_adf_text(c.get("body")).strip()

            if body and body not in seen_comments:
                comments_text.append(f"- *{author}*: {body}")
                seen_comments.add(body)

        discussion = "\n".join(
            comments_text[-5:]) if comments_text else "No comments found."  # Limit to last 5 for brevity

        return (
            f"*Summary:* {summary}\n"
            f"*Description:* {description[:200]}...\n\n"
            f"*Recent Discussion:*\n{discussion}"
        )

    except Exception as e:
        return f"❌ Exception reading Jira: {str(e)}"


async def check_jira_for_ui_assets(ticket_key: str):
    """Checks for UI screenshots in Jira."""
    jira_url = os.getenv("JIRA_URL")
    url = f"{jira_url}/rest/api/3/issue/{ticket_key}?fields=attachment"

    try:
        resp = requests.get(url, auth=get_jira_auth())
        data = resp.json()
        attachments = data.get("fields", {}).get("attachment", [])

        image_list = []
        for a in attachments:
            if a['mimeType'].startswith('image/'):
                image_list.append(f"• <{a['content']}|{a['filename']}>")

        if not image_list:
            return "No UI screenshots found."
        return "\n".join(image_list)
    except Exception:
        return "Error checking assets."


# --- SLACK EVENT LISTENERS (The "Brain" of Phase 2) ---

@slack_app.event("app_mention")
async def handle_mentions(body, say):
    """
    Trigger: When user types '@Mifos-Enhancement-Agent check WEB-95'
    Action: Runs the Librarian tools and replies in the thread.
    """
    text = body["event"]["text"]
    user = body["event"]["user"]

    # Simple Greeting
    if "hello" in text.lower():
        await say(
            f"👋 Hello <@{user}>! I am the Mifos Enhancement Agent. Mention me with a Ticket ID (like WEB-95) to get a summary.")
        return

    # Extract Ticket ID (Look for pattern like WEB-123 or MIFOSX-123)
    match = re.search(r"([A-Z]+-\d+)", text)
    if match:
        ticket_key = match.group(1)
        await say(f"🔍 Acknowledgement: Checking Jira for *{ticket_key}*...")

        # Run Tools
        details = await get_jira_ticket_details(ticket_key)
        assets = await check_jira_for_ui_assets(ticket_key)

        # Format and Send
        final_text = f"{details}\n\n*UI Assets:*\n{assets}"
        blocks = _create_block_kit_summary(f"Librarian Report: {ticket_key}", final_text)

        await say(blocks=blocks, text=f"Report for {ticket_key}")
    else:
        await say("❓ I didn't see a valid Ticket ID (e.g., WEB-95) in your message.")


@slack_app.event("message")
async def handle_message_events(body, logger):
    """Log messages for debugging (but don't reply unless mentioned)."""
    logger.info(body)


# --- FASTAPI SERVER ---

@api.post("/slack/events")
async def endpoint(req: Request):
    """The endpoint that Slack hits (via ngrok)."""
    return await app_handler.handle(req)


if __name__ == "__main__":
    import uvicorn

    # Run the web server on port 3000
    print("⚡️ Mifos Agent is listening on port 3000...")
    uvicorn.run(api, host="0.0.0.0", port=3000)