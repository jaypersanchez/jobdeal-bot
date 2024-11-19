import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import requests
import PyPDF2

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Define states for the conversation
NAME, DESCRIPTION = range(2)

# Detect natural language intent for creating a repository
async def detect_intent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text.lower()
    if "create a new project" in message_text or "new repo" in message_text:
        await update.message.reply_text("Please provide the name of the new repository:")
        return NAME
    else:
        await update.message.reply_text("I didn't understand. Please try again or use clear commands.")
        return ConversationHandler.END

# Get the repository name
async def get_repo_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["repo_name"] = update.message.text  # Store the repo name
    await update.message.reply_text("Now, please provide a description for the repository:")
    return DESCRIPTION

# Get the repository description and create the repo
async def get_repo_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["repo_description"] = update.message.text  # Store the repo description

    # Prepare the data to send to the server
    repo_name = context.user_data["repo_name"]
    repo_description = context.user_data["repo_description"]

    # Call the create repo endpoint
    response = requests.post(
        "http://localhost:4000/create-repo",  # Change to your server URL if needed
        json={"name": repo_name, "description": repo_description, "private": False},  # Adjust privacy as needed
    )

    if response.status_code == 201:
        await update.message.reply_text(f"Repository '{repo_name}' created successfully!")
    else:
        await update.message.reply_text(f"Failed to create repository: {response.json().get('error', 'Unknown error')}")

    # Clear user data and end the conversation
    context.user_data.clear()
    return ConversationHandler.END

# Cancel the conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

# Define a message handler for new chat members
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"Welcome to JobDeal, {member.full_name}!")

# Define a message handler for documents (resumes)
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    file_id = document.file_id

    try:
        # Get the file from Telegram
        new_file = await context.bot.get_file(file_id)

        # Download the file content
        file_path = f"./{document.file_name}"  # Save the file locally
        await new_file.download_to_drive(file_path)  # Correct download method

        # Extract text from the PDF
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            resume_content = ""
            for page in pdf_reader.pages:
                resume_content += page.extract_text()

        if not resume_content.strip():
            await update.message.reply_text(
                "Could not extract text from the uploaded resume. Please ensure the file contains readable text."
            )
            return

        # Send the extracted text to the analyze-resume endpoint
        response = requests.post(
            "http://localhost:4000/analyze-resume",  # Change to your server URL if needed
            json={"resumeContent": resume_content},  # Send the text as JSON
        )

        if response.status_code == 200:
            analysis = response.json().get("analysis", "No analysis returned.")
            await update.message.reply_text(analysis)
        else:
            await update.message.reply_text("Failed to analyze the resume.")
    except Exception as e:
        logging.error(f"Error handling document: {e}")
        await update.message.reply_text("An error occurred while processing your document.")

def main():
    # Get the token from the environment variable
    token = os.getenv("TELEGRAM_TOKEN")

    # Create the Application with the token
    application = ApplicationBuilder().token(token).build()

    # Define the conversation handler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, detect_intent)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_repo_name)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_repo_description)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Register the conversation handler
    application.add_handler(conv_handler)

    # Register the message handler for new chat members
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Register the message handler for documents
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
