import json
import os
import argparse
import concurrent.futures
from dotenv import load_dotenv
import openai
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL")
)


def load_exported_messages(export_file_path):
    """
    Loads the exported messages from the JSON file produced by our conversion script.
    Expected schema per message:
      - id, classes, type, timestamp, time, content, links (optional), media (optional)
    Returns only messages that contain non-empty 'content'.
    """
    try:
        with open(export_file_path, "r", encoding="utf8") as file:
            data = json.load(file)
    except Exception as e:
        print(f"Error loading exported file '{export_file_path}': {e}")
        return []

    if isinstance(data, list):
        messages = data
    elif isinstance(data, dict) and "messages" in data:
        messages = data["messages"]
    else:
        print("Unexpected JSON format in exported file.")
        messages = []

    # Filter out messages without any content.
    messages = [msg for msg in messages if msg.get("content", "").strip()]
    return messages


def build_prompt(messages, sample_size):
    """
    Construct the prompt for the OpenAI API using the new JSON schema.
    """
    sample_messages = messages[:sample_size]
    prompt = (
        "Create a JSON object that organizes the following messages into topics. "
        "Each topic should be a key in the JSON object, and its value should be an array of objects. "
        "Each object in the array must have exactly these three keys: 'summary', 'timestamp', and 'link'. "
        "The input messages follow this schema:\n\n"
        "{\n"
        '  "id": string,\n'
        '  "classes": list,\n'
        '  "type": string,\n'
        '  "timestamp": string,\n'
        '  "time": string,\n'
        '  "content": string,\n'
        '  "links": [string],\n'
        '  "media": [ { ... } ]\n'
        "}\n\n"
        "Here are the messages to organize:\n\n"
    )
    prompt += json.dumps(sample_messages, indent=2)
    return prompt


def log_ai_call(prompt, response, model, error=None):
    """
    Log AI call details to a file with timestamp
    """
    from datetime import datetime

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "prompt": prompt,
        "response": response,
        "error": str(error) if error else None,
    }

    try:
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)

        # Log to a daily file
        log_file = f"logs/ai_calls_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")


def call_openai(prompt, model="gpt-4o-mini", max_tokens=1500, temperature=0.3, top_p=1):
    """
    Call OpenAI API using the JSON mode to ensure JSON output.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a JSON-only output assistant. Always respond with valid, complete JSON. Ensure all strings are properly escaped and terminated.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=0,
            presence_penalty=0,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content.strip()

        # Always log the response before validation
        log_ai_call(prompt, text, model)

        # Validate JSON
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            print("OpenAI returned invalid JSON. Retrying with lower temperature...")
            # Log the retry attempt
            log_ai_call(
                prompt,
                None,
                model,
                error="Invalid JSON received, retrying with lower temperature",
            )
            # Retry once with lower temperature
            return call_openai(prompt, model, max_tokens, temperature=0.1, top_p=0.9)

    except Exception as e:
        log_ai_call(prompt, None, model, error=str(e))
        print(f"Error calling OpenAI API: {e}")
        return "{}"


def process_batch(messages):
    """
    Processes one batch of messages.
    Returns the partial table of contents as a dictionary.
    """
    prompt = build_prompt(messages, sample_size=len(messages))
    toc_text = call_openai(prompt)

    try:
        # Clean the response text
        toc_text = toc_text.strip()
        if not toc_text.startswith("{"):
            print(
                f"Invalid JSON format, response doesn't start with '{{': {toc_text[:100]}..."
            )
            return {}

        # Parse JSON with additional error handling
        try:
            partial_toc = json.loads(toc_text)
        except json.JSONDecodeError as e:
            # Try to clean up common JSON issues
            toc_text = toc_text.replace("\n", " ").replace("\r", "")
            toc_text = " ".join(toc_text.split())  # Normalize whitespace
            try:
                partial_toc = json.loads(toc_text)
            except:
                print(f"JSON parsing error even after cleanup: {e}")
                return {}

        if not isinstance(partial_toc, dict):
            print(f"Expected dictionary response, got {type(partial_toc)}")
            return {}

        # Validate the structure of each topic
        validated_toc = {}
        for topic, items in partial_toc.items():
            if isinstance(items, list):
                validated_items = []
                for item in items:
                    if isinstance(item, dict) and all(
                        k in item for k in ["summary", "timestamp", "link"]
                    ):
                        validated_items.append(item)
                if validated_items:
                    validated_toc[topic] = validated_items

        return validated_toc

    except Exception as e:
        print(f"Unexpected error processing batch: {e}")
        print(f"Raw output: {toc_text[:200]}...")
        return {}


def process_batches(messages, batch_size):
    """
    Process all messages in batches concurrently.
    Returns a list of partial TOCs.
    """
    batches = [
        messages[i : i + batch_size] for i in range(0, len(messages), batch_size)
    ]
    partial_tocs = []
    print(
        f"Processing {len(messages)} messages in {len(batches)} batch(es) (batch size: {batch_size})."
    )
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_batch, batch) for batch in batches]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                partial_tocs.append(result)
    return partial_tocs


def manual_merge_tocs(partial_tocs):
    """
    A fallback method to merge partial TOCs by combining lists for identical topics.
    """
    merged = {}
    for toc in partial_tocs:
        for topic, items in toc.items():
            merged.setdefault(topic, []).extend(items)
    return merged


def merge_partial_tocs(partial_tocs):
    """
    Merge multiple partial TOCs using an additional AI call. If the merge fails,
    fallback to the manual merge strategy.
    """
    merge_prompt = (
        "You are an expert in content organization and summarization. Below are several partial tables of contents, "
        "each in JSON format. Each table organizes messages with the keys 'summary', 'timestamp', and 'link'. "
        "Please merge these partial tables into one consolidated table of contents. Your output should be a JSON "
        "object where each key is a topic and its value is a list of entries (each with 'summary', 'timestamp', and 'link'). "
        "Merge similar topics and remove duplicates if any.\n\n"
        "Partial TOCs:\n\n"
        + json.dumps(partial_tocs, indent=2)
        + "\n\nConsolidated Table of Contents (in JSON):"
    )
    toc_text = call_openai(merge_prompt)
    try:
        final_toc = json.loads(toc_text)
        print("Successfully merged partial TOCs using AI.")
    except Exception as e:
        print(
            "Error merging partial TOCs using AI, falling back to manual merge. Error:",
            e,
        )
        final_toc = manual_merge_tocs(partial_tocs)
    return final_toc


def convert_toc_json_to_markdown(toc_json):
    """
    Convert the JSON table of contents to Markdown format.
    """
    md = "# Organized Table of Contents\n\n"
    for topic, items in toc_json.items():
        md += f"## {topic}\n\n"
        for item in items:
            summary = item.get("summary", "No summary provided")
            timestamp = item.get("timestamp", "")
            link = item.get("link", "N/A")
            md += f"- **Timestamp:** {timestamp}\n  **Link:** {link}\n  **Summary:** {summary}\n\n"
    return md


def parse_arguments():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate an organized table of contents from exported Telegram messages using AI."
    )
    parser.add_argument(
        "--export_file",
        type=str,
        default="telegram_messages.json",
        help="Path to the exported Telegram JSON file with the new schema.",
    )
    parser.add_argument(
        "--sample_size",
        type=int,
        default=50,
        help="Number of messages to sample for table of contents (used when --all is not set).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process and summarize all messages rather than a sample.",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=50,
        help="Number of messages per batch when summarizing all messages.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    print(f"Loading exported messages from: {args.export_file}")
    messages = load_exported_messages(args.export_file)
    if not messages:
        print(
            f"No valid messages loaded from '{args.export_file}'. Please verify the file format."
        )
        return

    # Process all messages in batches if --all is set.
    if args.all:
        partial_tocs = process_batches(messages, args.batch_size)
        if len(partial_tocs) > 1:
            final_toc = merge_partial_tocs(partial_tocs)
        elif partial_tocs:
            final_toc = partial_tocs[0]
        else:
            print("No partial TOCs generated.")
            return
        markdown = convert_toc_json_to_markdown(final_toc)
    else:
        sample_size = min(args.sample_size, len(messages))
        prompt = build_prompt(messages, sample_size=sample_size)
        toc_text = call_openai(prompt)
        print("Raw output from OpenAI:")
        print(toc_text)
        try:
            final_toc = json.loads(toc_text)
        except Exception as e:
            print("Error parsing OpenAI output as JSON. Raw output:")
            print(toc_text)
            print(f"Error: {e}")
            return
        markdown = convert_toc_json_to_markdown(final_toc)

    try:
        with open("table_of_contents.json", "w", encoding="utf-8") as json_file:
            json.dump(final_toc, json_file, indent=2, ensure_ascii=False)
        with open("table_of_contents.md", "w", encoding="utf-8") as md_file:
            md_file.write(markdown)
        print(
            "\nSuccessfully generated and saved the table of contents in JSON and Markdown formats."
        )
    except Exception as e:
        print("Error saving the table of contents:", e)


if __name__ == "__main__":
    main()
