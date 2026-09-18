import os
import logging
from typing import Dict, List, Any
from telegram import Update
from telegram.ext import ContextTypes

from app.db.database import SessionLocal
from app.agent.agent import agent_instance, AgentMessageResult

logger = logging.getLogger(__name__)

# User chat memory session store (per Telegram chat_id)
user_sessions: Dict[int, List[Dict[str, Any]]] = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message on /start command."""
    welcome_text = (
        "👋 <b>Welcome to Sharma General Supermarket AI Ops Agent!</b>\n\n"
        "I am your autonomous Kirana operations assistant. You can manage your store using natural Hindi or English instructions:\n\n"
        "🛒 <b>Billing:</b> <i>'Make a bill: 2kg sugar and 4 Maggi'</i>\n"
        "📦 <b>Inventory:</b> <i>'50 packets of Maggi came in, cost ₹12, MRP ₹14'</i>\n"
        "📖 <b>Khata Credit:</b> <i>'Put ₹500 on Ramesh credit'</i> or <i>'Ramesh paid ₹300'</i>\n"
        "📄 <b>PDF Invoices:</b> <i>'Send me that bill as a PDF'</i>\n"
        "📊 <b>PPTX Deck:</b> <i>'Make this week's sales analysis deck'</i>\n"
        "⚙️ <b>Preferences:</b> <i>'Always assume UPI unless I say cash'</i>\n\n"
        "Type your request to begin!"
    )
    await update.message.reply_html(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help menu on /help command."""
    help_text = (
        "ℹ️ <b>Supermarket Ops Agent Commands & Capabilities</b>\n\n"
        "• <b>Receive Stock:</b> <i>50 packets of Maggi came in, cost ₹12, MRP ₹14</i>\n"
        "• <b>Add Product:</b> <i>New item: Amul Butter 100g, GST 12%, MRP ₹62</i>\n"
        "• <b>Draft Bills:</b> Multi-turn editing supported (add/remove/change qty/set payment)\n"
        "• <b>Finalize Bill:</b> Decrements stock atomically & calculates CGST/SGST\n"
        "• <b>Khata Ledger:</b> Track customer balance & repayments\n"
        "• <b>Daily Sales:</b> <i>Today's sales?</i> or <i>Close the day</i>\n"
        "• <b>Documents:</b> Generate PDF invoices and PPTX weekly analysis decks\n"
        "• <b>/reset:</b> Clear active conversation session"
    )
    await update.message.reply_html(help_text)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset active chat history session for user."""
    chat_id = update.effective_chat.id
    user_sessions[chat_id] = []
    await update.message.reply_text("🔄 Conversation session reset. Open draft bills and store database records remain intact.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming natural language user messages from Telegram."""
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    
    # Send typing status indicator
    await update.message.reply_chat_action("typing")

    db = SessionLocal()
    try:
        chat_history = user_sessions.get(chat_id, [])
        
        # Process message with ReAct agent loop
        result: AgentMessageResult = agent_instance.process_message(db, user_text, chat_history)

        # Update in-memory chat history (cap at last 10 turns)
        chat_history.append({"role": "user", "content": user_text})
        chat_history.append({"role": "assistant", "content": result.text_response})
        user_sessions[chat_id] = chat_history[-10:]

        # Reply with agent text response
        await update.message.reply_text(result.text_response)

        # Send any generated document attachments (PDF invoice or PPTX deck)
        for doc_path in result.document_paths:
            if os.path.exists(doc_path):
                await update.message.reply_chat_action("upload_document")
                with open(doc_path, "rb") as f:
                    doc_name = os.path.basename(doc_path)
                    await update.message.reply_document(
                        document=f,
                        filename=doc_name,
                        caption=f"📄 Generated Document: {doc_name}"
                    )
            else:
                logger.warning(f"Generated document path not found: {doc_path}")

    except Exception as e:
        logger.error(f"Error handling Telegram message: {e}", exc_info=True)
        await update.message.reply_text("⚠️ An error occurred while processing your request. Please try again.")
    finally:
        db.close()
