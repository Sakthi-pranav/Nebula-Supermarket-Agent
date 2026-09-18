import sys
import argparse
from pathlib import Path

# Ensure stdout uses UTF-8 encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure application package is on python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import init_db, SessionLocal
from scripts.seed_db import seed
from app.agent.agent import agent_instance

def run_cli_interactive():
    """Run an interactive local terminal session with the Supermarket Ops Agent."""
    print("\n" + "=" * 60)
    print("🛒 Supermarket Ops Agent - Local CLI Demo Mode")
    print("=" * 60)
    print("Type your natural language request (e.g. 'Make a bill: 2kg sugar and 4 Maggi').")
    print("Type 'exit' or 'quit' to end session.\n")

    db = SessionLocal()
    chat_history = []
    
    try:
        while True:
            try:
                user_input = input("\n👤 Owner > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting CLI mode.")
                break
                
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            result = agent_instance.process_message(db, user_input, chat_history)

            # Update chat history
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": result.text_response})
            chat_history = chat_history[-10:]

            print(f"\n🤖 Agent > {result.text_response}")

            for doc_path in result.document_paths:
                print(f"   📄 [Generated Document]: {doc_path}")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Supermarket Ops Agent Application Launcher")
    parser.add_argument("--seed", action="store_true", help="Initialize and seed database with sample data")
    parser.add_argument("--bot", action="store_true", help="Run Telegram bot")
    parser.add_argument("--cli", "--demo", action="store_true", help="Run interactive terminal CLI mode")
    
    args = parser.parse_args()

    # Always ensure database tables are initialized
    init_db()

    if args.seed:
        print("🌱 Running database seeding...")
        seed()
    elif args.bot:
        from app.telegram.bot import run_bot
        run_bot()
    elif args.cli:
        run_cli_interactive()
    else:
        print("🛒 Supermarket Ops Agent System Initialized.")
        print("\nAvailable Options:")
        print("  python app/main.py --seed    (Seed sample products & preferences)")
        print("  python app/main.py --cli     (Run interactive terminal demo mode)")
        print("  python app/main.py --bot     (Start Telegram Bot server)")

if __name__ == "__main__":
    main()
