import os
import os
try:
    import redis
except ImportError:
    redis = None
from datetime import datetime, timedelta
import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI




from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
PASSWORD = os.getenv("PASSWORD")

# Redis Cloud connection for memory storage
if redis:
    redis_client = redis.Redis(
        host=HOST,
        port=PORT,
        decode_responses=True,
        username="default",
        password=PASSWORD,
    )
else:
    redis_client = None

# Test Redis connection
if redis_client:
    try:
        redis_client.ping()
        print("✅ Redis Cloud connected successfully")
    except redis.ConnectionError as e:
        print(f"❌ Redis Cloud connection failed: {e}")
        print("⚠️  Falling back to memory-only mode")
else:
    print("⚠️  Redis not installed. Falling back to memory-only mode")

# Redis memory management functions
def store_conversation_memory(user_id: str, messages: list, metadata: dict = None):
    """Store conversation in Redis with 12-hour TTL"""
    try:
        memory_data = {
            "messages": messages,
            "metadata": metadata or {},
            "last_updated": datetime.utcnow().isoformat(),
            "user_id": user_id
        }

        # Store with 12-hour expiration (43200 seconds)
        if redis_client:
            redis_client.setex(
                f"conversation:{user_id}",
                43200,  # 12 hours in seconds
                json.dumps(memory_data)
            )
            print(f"💾 Stored conversation for user {user_id} with 12-hour TTL")
        else:
            print(f"⚠️ Redis unavailable, skipping persistence for {user_id}")
    except Exception as e:
        print(f"❌ Error storing conversation: {e}")


def get_conversation_memory(user_id: str) -> dict:
    """Retrieve conversation from Redis"""
    try:
        if redis_client:
            data = redis_client.get(f"conversation:{user_id}")
            if data:
                return json.loads(data)
        return {"messages": [], "metadata": {}}
    except Exception as e:
        print(f"❌ Error retrieving conversation: {e}")
        return {"messages": [], "metadata": {}}


def clear_conversation_memory(user_id: str):
    """Clear conversation memory for a specific user"""
    try:
        if redis_client:
            redis_client.delete(f"conversation:{user_id}")
            print(f"🧹 Cleared conversation memory for user: {user_id}")
    except Exception as e:
        print(f"❌ Error clearing conversation: {e}")


def get_conversation_summary(user_id: str) -> str:
    """Get a summary of the conversation for continuity"""
    return f"Conversation thread: {user_id} - CapAmerica product catalog inquiry"


async def setup_agent():
    """Setup MCP client and AI agent (without LangGraph memory checkpointer)"""
    client = MultiServerMCPClient(
        {
            "Forget_Password": {
                "command": "python",
                "args": ["password_reset.py"],
                "transport": "stdio",
            }
        }
    )

    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

    tools = await client.get_tools()
    model = ChatOpenAI(model="gpt-4o-mini")

    # Create agent without LangGraph memory (we'll use Redis instead)
    agent = create_agent(model, tools)

    return agent


async def process_question(agent, user_question, user_id="default_user"):
    """Send any user question to the agent with Redis memory"""
    print(f"\n🔍 Question: {user_question}")
    print("🔄 Processing...")

    # Get existing conversation from Redis
    memory_data = get_conversation_memory(user_id)

    # Build message history with new question
    messages = memory_data.get("messages", [])
    messages.append({"role": "user", "content": user_question})

    # Add conversation context to messages for the agent
    if len(messages) > 1:
        context_messages = messages[-6:]  # Keep last 6 messages for context
        full_messages = context_messages + [{"role": "system", "content":
            f"Conversation history for context: {json.dumps([msg['content'] for msg in context_messages[-3:]])}"}]
    else:
        full_messages = [{"role": "user", "content": user_question}]

    # Get response from agent
    response = await agent.ainvoke({"messages": full_messages})

    # Extract and store response
    response_content = response['messages'][-1].content
    messages.append({"role": "assistant", "content": response_content})

    # Save updated conversation to Redis with 12-hour TTL
    store_conversation_memory(user_id, messages)

    return response_content


# Alternative: Direct question function
async def ask_question(question, style_preference=None, user_id="default_user"):
    """Function to directly ask a question with optional style preference and user memory (for programmatic use)"""
    agent = await setup_agent()

    # Get recent conversation context
    # recent_context = await get_recent_context(user_id) # context not needed for simple reset flow yet
    
    contextual_question = f"""
    You are **Anvita**, a secure IT Password Reset Assistant.
    Your **ONLY** goal is to help employees reset their passwords securely.

    **YOUR PROTOCOL:**
    1.  **Identity Verification**:
        - When a user asks to reset their password (or says "reset password", "/anvita reset password"), ask for their **Employee ID**.
        - Use the tool `verify_employee_id` to check if it exists.
        - If invalid, ask them to try again.

    2.  **Security Question**:
        - Once the Employee ID is verified, use the tool `fetch_security_question` to get their specific security question.
        - Ask the user this question. Present options if the tool provides them (or if they are standard), otherwise just ask the question.

    3.  **Authentication & Reset**:
        - When the user provides the answer, use the tool `verify_security_answer_and_reset` to verify it.
        - **Pass the exact Employee ID and User Answer to the tool.**
        - If the tool returns "verified": True:
            - Inform the user their password has been reset.
            - Tell them to check their email for the temporary password.
            - Show a confirmation message like:
              "✅ Identity Verified!
               📋 Ticket Created: TKT-001" (You can generate a random ticket ID or use the one from the tool if available)
        - If the tool returns "verified": False:
            - Inform them it was incorrect and ask if they want to try again.

    **TONE AND STYLE:**
    - Professional, secure, and helpful.
    - Use emojis like 🔐, ✅, 📋, ⏱️ to make it look like a modern bot.
    - Be concise.

    **User's Input:** {question}
    """

    return await process_question(agent, contextual_question, user_id)


def clear_conversation(user_id: str):
    """Clear conversation memory for a specific user"""
    clear_conversation_memory(user_id)
