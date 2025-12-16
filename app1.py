import os
import requests
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# Initialize Slack app with bot token and signing secret
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize FastAPI app
app1 = FastAPI(title="Slack Bot API")
handler = SlackRequestHandler(slack_app)

# Your API endpoint
API_ENDPOINT = "https://slackagent.bestworks.cloud/chat/agent"


def call_agent_api(user_id, query):
    """Call your backend API endpoint"""
    try:
        payload = {
            "user_id": user_id,
            "query": query
        }
        response = requests.post(API_ENDPOINT, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {
            "response": f"❌ Error connecting to agent: {str(e)}",
            "status_code": 500
        }


@slack_app.event("app_mention")
def handle_mention(event, say):
    """Handle when bot is mentioned in a channel"""
    user_id = event["user"]
    text = event["text"]
    
    # Remove the bot mention from the text
    query = text.split(">", 1)[1].strip() if ">" in text else text.strip()
    
    if not query:
        say("👋 Hi! Please include your question after mentioning me.")
        return
    
    # Show typing indicator
    say("🤔 Processing your request...")
    
    # Call your API
    result = call_agent_api(user_id, query)
    
    # Send response
    say(result.get("response", "No response received"))


@slack_app.event("message")
def handle_direct_message(event, say):
    """Handle direct messages to the bot"""
    # Ignore bot messages and threaded messages
    if event.get("bot_id") or event.get("thread_ts"):
        return
    
    # Only handle direct messages (channel_type will be 'im')
    if event.get("channel_type") != "im":
        return
    
    user_id = event["user"]
    query = event["text"]
    
    if not query:
        return
    
    # Show typing indicator
    say("🤔 Processing your request...")
    
    # Call your API
    result = call_agent_api(user_id, query)
    
    # Send response
    say(result.get("response", "No response received"))


@slack_app.command("/agent")
def handle_agent_command(ack, command, say):
    """Handle /agent slash command"""
    ack()  # Acknowledge the command immediately
    
    user_id = command["user_id"]
    query = command["text"]
    
    if not query:
        say("❓ Please provide a query. Usage: `/agent your question here`")
        return
    
    # Call your API
    result = call_agent_api(user_id, query)
    
    # Send response
    say(result.get("response", "No response received"))


# FastAPI routes for Slack events
@app1.post("/slack/events")
async def slack_events(req: Request):
    """Handle Slack events"""
    return await handler.handle(req)


@app1.post("/slack/commands")
async def slack_commands(req: Request):
    """Handle Slack slash commands"""
    return await handler.handle(req)


@app1.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Slack bot is running"}


@app1.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Slack Bot API", 
        "endpoints": {
            "events": "/slack/events",
            "commands": "/slack/commands",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    print("⚡️ Slack bot is running on port 8000!")
    uvicorn.run(app1, host="0.0.0.0", port=8068)