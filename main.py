import json
import os
import argparse
from dotenv import load_dotenv
import openai

# Load environment variables from .env file
load_dotenv()

# Set up OpenAI configuration
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.base_url = os.getenv("OPENAI_BASE_URL")


def load_exported_messages(export_file_path):
    """
    Load messages from an exported Telegram channel JSON file.
    Expected format: a dictionary with a "messages" key, or a list.
    Handles cases where the 'text' field might be a list (common in Telegram exports).
    """
    try:
        with open(export_file_path, "r", encoding="utf8") as file:
            data = json.load(file)
    except Exception as e:
        print(f"Error loading exported file '{export_file_path}': {e}")
        return []

    # Determine where the messages are stored if the file uses Telegram's export format.
    if isinstance(data, dict) and "messages" in data:
        messages = data["messages"]
    elif isinstance(data, list):
        messages = data
    else:
        print("Unexpected format in exported file.")
        return []

    # Filter and normalize messages to include only those with a non-empty text.
    filtered = []
    for msg in messages:
        if "text" in msg:
            text_content = msg["text"]
            # Telegram export sometimes represents text as a list of parts.
            if isinstance(text_content, list):
                text_content = "".join(
                    part if isinstance(part, str) else part.get("text", "")
                    for part in text_content
                )
            if text_content.strip():
                filtered.append(
                    {
                        "id": msg.get("id"),
                        "date": msg.get("date"),
                        "text": text_content,
                        "link": msg.get("link", ""),
                    }
                )
    return filtered


def build_prompt(messages, sample_size=50):
    """
    Construct the prompt for the OpenAI API based on the provided messages.
    The 'sample_size' parameter is used to determine how many messages to include
    in the prompt. (When processing batches, we pass the entire chunk.)
    """
    sample_messages = messages[:sample_size]
    prompt = (
        "You are an expert in content organization and summarization. Below is a list of messages "
        "from a public Telegram channel. These messages contain links and snippets related to topics "
        "such as Software Engineering, Artificial Intelligence, Product Management, and Business.\n\n"
        "Your task is to create an organized table of contents that groups these messages by topic. "
        "For each message, provide a concise summary, along with its date and link (if available). "
        "Output the result as a JSON object where each key is one of the topics, and its value is a list "
        "of objects with keys: 'summary', 'date', and 'link'.\n\n"
        "Below are the messages:\n\n"
    )
    prompt += json.dumps(sample_messages, indent=2)
    prompt += "\n\nTable of Contents (in JSON):"
    return prompt


def call_openai(prompt):
    """
    Call OpenAI API to generate table of contents based on the prompt.
    """
    print("Calling OpenAI API to generate table of contents …")
    try:
        response = openai.Completion.create(
            engine="gpt-4o-mini",
            prompt=prompt,
            max_tokens=1500,
            temperature=0.3,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        text = response.choices[0].text.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        text = ""
    return text


def convert_toc_json_to_markdown(toc_json):
    """
    Convert the JSON table of contents to Markdown format.
    """
    md = "# Organized Table of Contents\n\n"
    for topic, items in toc_json.items():
        md += f"## {topic}\n\n"
        for item in items:
            summary = item.get("summary", "No summary provided")
            date = item.get("date", "")
            link = item.get("link", "")
            md += f"- **Date:** {date}  \n  **Link:** {link if link else 'N/A'}  \n  **Summary:** {summary}\n\n"
    return md


def parse_arguments():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate table of contents from Telegram exported messages."
    )
    parser.add_argument(
        "--export_file",
        type=str,
        default="exported_channel.json",
        help="Path to the exported Telegram channel JSON file",
    )
    parser.add_argument(
        "--sample_size",
        type=int,
        default=50,
        help="Number of messages to sample for table of contents (used when --all is not set)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process and summarize all messages by batching them into chunks",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=50,
        help="Number of messages per batch when summarizing all messages",
    )
    return parser.parse_args()


def process_batches(messages, batch_size):
    """
    Process the full list of messages in batches. For each batch, a prompt is built and an AI call is made
    to get a partial table of contents.
    """
    partial_tocs = []
    num_batches = (len(messages) + batch_size - 1) // batch_size
    print(
        f"Processing {len(messages)} messages in {num_batches} batches (batch size: {batch_size})."
    )
    for i in range(0, len(messages), batch_size):
        batch_messages = messages[i : i + batch_size]
        print(
            f"Processing batch {i // batch_size + 1} with {len(batch_messages)} messages."
        )
        # Pass the entire batch to the prompt builder.
        prompt = build_prompt(batch_messages, sample_size=len(batch_messages))
        toc_text = call_openai(prompt)
        try:
            partial_toc = json.loads(toc_text)
            partial_tocs.append(partial_toc)
        except Exception as e:
            print(f"Error parsing partial TOC from batch {i // batch_size + 1}: {e}")
            print(f"Raw output: {toc_text}")
    return partial_tocs


def manual_merge_tocs(partial_tocs):
    """
    Manually merge multiple partial table of contents JSON objects into one.
    This fallback simply combines lists for matching topics.
    """
    merged = {}
    for toc in partial_tocs:
        for topic, items in toc.items():
            if topic in merged:
                merged[topic].extend(items)
            else:
                merged[topic] = list(items)  # use a copy of the list
    return merged


def merge_partial_tocs(partial_tocs):
    """
    Merge partial TOCs using an additional AI call.
    Rather than simply concatenating the lists, this call instructs the AI to re-summarize and reorganize
    the aggregated data to produce a new, consolidated table of contents.
    If the AI merging fails, fall back to a manual merge.
    """
    merge_prompt = (
        "You are an expert in content organization and summarization. You have been given several partial tables of contents "
        "generated from batches of Telegram channel messages. Each partial table of contents is a JSON object, where keys are topics and "
        "values are lists of message entries (each with 'summary', 'date', and 'link'). Rather than simply appending these entries, "
        "your task is to re-assess the overall content, identify overlapping themes, merge similar topics, remove redundancies, and refine "
        "the summaries where necessary. Produce a new, consolidated table of contents that reorganizes the entire content logically.\n\n"
        "Partial tables of contents:\n\n"
    )
    merge_prompt += json.dumps(partial_tocs, indent=2)
    merge_prompt += "\n\nConsolidated Table of Contents (in JSON):"
    final_toc_text = call_openai(merge_prompt)
    try:
        final_toc = json.loads(final_toc_text)
        print("Successfully merged partial TOCs using AI.")
    except Exception as e:
        print(
            "Error merging partial TOCs using AI, falling back to manual merge. Error:",
            e,
        )
        final_toc = manual_merge_tocs(partial_tocs)
    return final_toc


def main():
    args = parse_arguments()

    print(f"Loading exported messages from: {args.export_file}")
    messages = load_exported_messages(args.export_file)

    if not messages:
        print(
            f"No messages loaded. Please verify the exported file at '{args.export_file}'."
        )
        return

    # If the --all flag is set, process all messages using batching and merge the results.
    if args.all:
        partial_tocs = process_batches(messages, args.batch_size)
        if len(partial_tocs) > 1:
            final_toc = merge_partial_tocs(partial_tocs)
        elif len(partial_tocs) == 1:
            final_toc = partial_tocs[0]
        else:
            print("No partial TOCs generated from any batch.")
            return
        markdown = convert_toc_json_to_markdown(final_toc)
    else:
        # Legacy behavior: process only a sample subset of messages.
        sample_size = args.sample_size
        if len(messages) < sample_size:
            print(
                f"Warning: Only {len(messages)} messages available, adjusting sample size accordingly."
            )
            sample_size = len(messages)
        prompt = build_prompt(messages, sample_size=sample_size)
        toc_text = call_openai(prompt)
        print("Raw output from OpenAI:")
        print(toc_text)
        try:
            final_toc = json.loads(toc_text)
        except Exception as e:
            print(
                "Could not parse the output as JSON. Here is the raw output for manual inspection:"
            )
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
            "\nSuccessfully generated and saved the table of contents in both JSON and Markdown formats."
        )
    except Exception as e:
        print("Error saving the table of contents:", e)


if __name__ == "__main__":
    main()
