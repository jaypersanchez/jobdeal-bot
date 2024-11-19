import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import PyPDF2

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

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

    # Register the message handler for new chat members
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Register the message handler for documents
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
