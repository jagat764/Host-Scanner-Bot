import os
import requests
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from colorama import Fore, Style, init

# Initialize Colorama for terminal styling
init(autoreset=True)

# Telegram Bot Token
BOT_TOKEN = "7943587607:AAF59SDpe9NZyf5VEmrTvDL7YTuGl_XKxV0"

# Directory for storing user-uploaded files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def check_host(host):
    """
    Check the response of a single host.
    :param host: URL or host to check
    :return: Dictionary with host information
    """
    try:
        response = requests.get(host.strip(), timeout=10)  # Send a GET request with a 10s timeout
        return {
            "host": host,
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds(),
            "is_working": response.status_code == 200,
            "error": None,
        }
    except requests.exceptions.RequestException as e:
        return {
            "host": host,
            "status_code": "Error",
            "response_time": None,
            "is_working": False,
            "error": str(e),
        }


def check_hosts_concurrently(hosts, max_threads=10):
    """
    Check the response of hosts concurrently.
    :param hosts: List of URLs or hosts to check
    :param max_threads: Maximum number of threads to use
    :return: List of dictionaries with host information
    """
    results = []
    with ThreadPoolExecutor(max_threads) as executor:
        future_to_host = {executor.submit(check_host, host): host for host in hosts}
        for future in tqdm(as_completed(future_to_host), total=len(hosts), desc="Checking Hosts", ncols=80, colour="green"):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({
                    "host": future_to_host[future],
                    "status_code": "Error",
                    "response_time": None,
                    "is_working": False,
                    "error": str(e),
                })
    return results


def start(update: Update, context: CallbackContext):
    """
    Start command handler.
    """
    update.message.reply_text(
        "Welcome to the Host Checker Bot! Send me a .txt file containing a list of hosts (one per line), and I'll check which ones are working."
    )


def handle_file(update: Update, context: CallbackContext):
    """
    Handle .txt file uploads from users.
    """
    file = update.message.document
    if not file.file_name.endswith(".txt"):
        update.message.reply_text("Please send a valid .txt file.")
        return

    user_id = update.message.from_user.id
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_hosts.txt")

    # Download the file
    file.get_file().download(custom_path=file_path)
    update.message.reply_text("File received! Checking hosts... This might take a while.")

    # Process the file
    with open(file_path, "r") as f:
        hosts = [line.strip() for line in f.readlines() if line.strip()]

    if not hosts:
        update.message.reply_text("The file is empty or invalid. Please upload a valid .txt file.")
        return

    # Check hosts
    results = check_hosts_concurrently(hosts, max_threads=20)

    # Filter working hosts
    working_hosts = [result["host"] for result in results if result["is_working"]]

    if working_hosts:
        # Save working hosts to a file
        working_file_path = os.path.join(UPLOAD_DIR, f"{user_id}_working_hosts.txt")
        with open(working_file_path, "w") as wf:
            wf.write("\n".join(working_hosts))

        # Send back the working hosts file
        update.message.reply_text(f"Found {len(working_hosts)} working hosts! Sending the list back to you.")
        update.message.reply_document(document=InputFile(working_file_path), filename="working_hosts.txt")
    else:
        update.message.reply_text("No working hosts were found in the provided file.")


def main():
    """
    Main function to start the bot.
    """
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("start", start))

    # File handler
    dispatcher.add_handler(MessageHandler(Filters.document.mime_type("text/plain"), handle_file))

    # Start the bot
    print(f"{Fore.GREEN}[Bot]{Style.RESET_ALL} Host Checker Bot is running...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
