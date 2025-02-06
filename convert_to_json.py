import argparse
import json
from bs4 import BeautifulSoup


def parse_media_item(anchor):
    """
    Extract extra details from a media attachment.
    For file attachments, this looks for elements like:
      - a file title (from a 'div' with class "title" or "title bold")
      - file-size or status (from a 'div' with class "status" or "status details")
      - a thumbnail image (from any <img> found in the anchor)
    """
    media_item = {"url": anchor.get("href", "")}

    # Try to extract a file title from different possible class names.
    title_div = anchor.find("div", class_="title")
    if title_div:
        media_item["title"] = title_div.get_text(strip=True)

    # Extract file size or status details if available.
    status_div = anchor.find("div", class_="status")
    if status_div:
        media_item["size"] = status_div.get_text(strip=True)

    # For photo attachments, capture the thumbnail image if present.
    img = anchor.find("img")
    if img:
        media_item["thumbnail"] = img.get("src", "")

    return media_item


def parse_message(message_div):
    """
    Extracts details from a single message container.

    The output schema includes:
      - id: the message element id attribute.
      - classes: a list of CSS classes (which helps determine the type).
      - type: "service" or "default" (derived from the classes).
      - timestamp: the full date/time information (from a title attribute or message body).
      - time: a simplified time string where available.
      - content: the pure text content (with HTML tags removed).
      - links: any hyperlinks embedded in the content.
      - media: a list of dictionaries with media attachment information.
    """
    msg = {}
    msg["id"] = message_div.get("id", "")
    msg["classes"] = message_div.get("class", [])

    # Determine a message type based on its classes.
    if "service" in msg["classes"]:
        msg["type"] = "service"
    elif "default" in msg["classes"]:
        msg["type"] = "default"
    else:
        msg["type"] = "unknown"

    # Extract time information.
    date_div = message_div.find("div", class_="pull_right date details")
    if date_div:
        msg["time"] = date_div.get_text(strip=True)
        timestamp = date_div.get("title", "")
        if timestamp:
            msg["timestamp"] = timestamp
    else:
        bd_div = message_div.find("div", class_="body details")
        if bd_div:
            date_text = bd_div.get_text(strip=True)
            msg["timestamp"] = date_text
            msg["time"] = ""

    # Extract text content from the message.
    text_div = message_div.find("div", class_="text")
    if text_div:
        msg["content"] = " ".join(text_div.stripped_strings)
        links = []
        for a in text_div.find_all("a"):
            href = a.get("href")
            if href:
                links.append(href)
        if links:
            msg["links"] = links
    else:
        msg["content"] = ""

    # Extraction for media attachments.
    media_items = []
    for a in message_div.find_all("a", class_=["media_file", "photo_wrap"]):
        media_item = parse_media_item(a)
        media_items.append(media_item)
    if media_items:
        msg["media"] = media_items

    return msg


def parse_html_export(html_content):
    """
    Processes the entire HTML export.
    Finds all message containers (div elements with a "message" class) and extracts details.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    messages_divs = soup.find_all("div", class_="message")
    messages = []
    for msg_div in messages_divs:
        parsed_msg = parse_message(msg_div)
        messages.append(parsed_msg)
    return messages


def main():
    parser = argparse.ArgumentParser(
        description="Extract Telegram channel messages from an HTML export and save as JSON."
    )
    parser.add_argument(
        "--input_file",
        type=str,
        default="export/messages.html",
        help="Path to the HTML export file from Telegram.",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default="telegram_messages.json",
        help="Path to save the extracted JSON file.",
    )
    args = parser.parse_args()

    with open(args.input_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    messages = parse_html_export(html_content)

    with open(args.output_file, "w", encoding="utf-8") as outf:
        json.dump(messages, outf, indent=2, ensure_ascii=False)

    print(f"Extracted {len(messages)} messages to {args.output_file}")


if __name__ == "__main__":
    main()
