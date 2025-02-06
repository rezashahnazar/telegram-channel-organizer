#!/usr/bin/env python3
import json
import os
import sys
import argparse
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console

console = Console()


def log_debug(message: str) -> None:
    """
    Log a debug (step) message in bold blue.
    """
    console.print(f"[bold blue]{message}[/bold blue]")


def log_info(message: str) -> None:
    """
    Log an informational message in bold green.
    """
    console.print(f"[bold green]{message}[/bold green]")


def log_warning(message: str) -> None:
    """
    Log a warning message in bold yellow.
    """
    console.print(f"[bold yellow]{message}[/bold yellow]")


def log_error(message: str) -> None:
    """
    Log an error message in bold red.
    """
    console.print(f"[bold red]{message}[/bold red]")


# Load environment variables from .env
load_dotenv()
log_debug("Environment variables loaded.")


def init_openai_client():
    """
    Initialize the OpenAI client using AI_API_KEY and AI_BASE_URL.
    """
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    if not api_key or not base_url:
        log_error("Error: AI_API_KEY and/or AI_BASE_URL environment variable not set.")
        sys.exit(1)
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        log_debug("Successfully initialized AI client.")
        return client
    except Exception as e:
        log_error(f"Failed to initialize OpenAI client: {e}")
        sys.exit(1)


client = init_openai_client()


def log_ai_call(prompt: str, response: str, model: str, error: str = None) -> None:
    """
    Log details of an AI call with timestamp to a daily JSONL file.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "prompt": prompt,
        "response": response,
        "error": str(error) if error else None,
    }
    try:
        os.makedirs("logs", exist_ok=True)
        log_file = f"logs/ai_calls_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        log_debug("AI call logged to file.")
    except Exception as e:
        log_error(f"Error writing to log file: {e}")


def load_exported_messages(filepath: str) -> list:
    """
    Load messages from the provided JSON file.
    Supports files as a list of messages or a dict with a 'messages' key.
    """
    log_debug(f"Loading messages from {filepath}")
    try:
        with open(filepath, "r", encoding="utf8") as file:
            data = json.load(file)
        if isinstance(data, dict) and "messages" in data:
            messages = data["messages"]
        elif isinstance(data, list):
            messages = data
        else:
            log_error("Unexpected JSON format in exported file.")
            return []
        # Keep only messages with non-empty content
        messages = [msg for msg in messages if msg.get("content", "").strip()]
        log_debug(f"Loaded {len(messages)} valid message(s) from file.")
        return messages
    except Exception as e:
        log_error(f"Error loading file '{filepath}': {e}")
        return []


def build_prompt(messages: list) -> str:
    """
    Build a prompt instructing the AI to organize messages by topic with strict JSON formatting requirements.
    """
    log_debug("Building prompt for AI call...")
    prompt = (
        "You are a JSON formatting assistant. Given a list of messages, organize them by topics. "
        "Return ONLY a valid JSON object following these strict requirements:\n"
        "1. The response must be a single JSON object where each key is a topic name\n"
        "2. Each topic's value must be an array of entry objects\n"
        "3. Each entry object must contain EXACTLY these three keys: 'summary', 'timestamp', and 'link'\n"
        "4. Do not include any explanatory text or markdown formatting\n\n"
        "Expected format example:\n"
        "{\n"
        '  "Topic Name 1": [\n'
        "    {\n"
        '      "summary": "Brief description of the message",\n'
        '      "timestamp": "2025-01-01T12:00:00",\n'
        '      "link": "https://example.com/link"\n'
        "    }\n"
        "  ],\n"
        '  "Topic Name 2": [...]\n'
        "}\n\n"
        "Messages to organize:\n"
        f"{json.dumps(messages, indent=2)}"
    )
    log_debug(f"Prompt built with length: {len(prompt)} characters.")
    return prompt


def parse_ai_response(text: str) -> dict:
    """
    Parse the AI response to extract valid JSON.
    Handles markdown code blocks and extraneous text.
    """
    try:
        # Clean markdown code block delimiters
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]  # Remove ```json
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]  # Remove ```
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]  # Remove trailing ```

        cleaned = cleaned.strip()

        # Handle newlines in the content
        cleaned = cleaned.replace("\n", " ").replace("\r", " ")

        # Normalize multiple spaces
        cleaned = " ".join(cleaned.split())

        # Extract JSON if embedded in other text
        if not cleaned.startswith("{"):
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(0)
            else:
                raise ValueError("JSON object not found in response.")

        result = json.loads(cleaned)
        log_debug("Successfully parsed AI response as JSON.")
        return result
    except Exception as e:
        log_error(f"Error parsing AI response as JSON: {e}")
        return {}


def call_openai(
    prompt: str, model: str = "gemini-2.0-flash", temperature: float = 0.3
) -> dict:
    """
    Call the Gemini model ensuring valid JSON output.
    Retries up to 3 times if the response details are invalid.
    """
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        log_debug(
            f"Attempt {attempt}: Sending AI API call with prompt length {len(prompt)}."
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You must only respond with valid JSON. Do not include any explanations or extra text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
            text = response.choices[0].message.content.strip()
            # Log only first 150 chars to avoid truncation in logs
            log_debug(f"Received AI API response (attempt {attempt}): {text[:150]}...")
            log_ai_call(prompt, text, model)

            # Add debug logging for response length
            log_debug(f"Response length: {len(text)} characters")

            parsed = parse_ai_response(text)
            if parsed:
                log_debug("AI API call returned valid JSON.")
                return parsed
            else:
                log_warning(f"Attempt {attempt}: Invalid JSON received. Retrying...")
        except Exception as e:
            log_ai_call(prompt, None, model, error=str(e))
            log_error(f"Attempt {attempt}: Error during AI API call: {e}")
        time.sleep(attempt)  # incremental backoff
    log_error(
        "Failed to receive a valid response from the AI API after multiple attempts."
    )
    return {}


def process_messages(messages: list) -> dict:
    """
    Process the messages by building the prompt, calling the AI,
    and returning the organized JSON table of contents.
    """
    log_debug(f"Processing {len(messages)} message(s).")
    prompt = build_prompt(messages)
    toc = call_openai(prompt)
    return toc


def convert_toc_to_markdown(toc: dict) -> str:
    """
    Convert the JSON table of contents to Markdown.
    """
    log_debug("Converting JSON TOC to Markdown format.")
    md = "# Organized Table of Contents\n\n"
    for topic, entries in toc.items():
        md += f"## {topic}\n\n"
        for entry in entries:
            summary = entry.get("summary", "No summary provided")
            timestamp = entry.get("timestamp", "")
            link = entry.get("link", "")
            md += f"- **Timestamp:** {timestamp}\n  **Link:** {link}\n  **Summary:** {summary}\n\n"
    log_debug("Conversion to Markdown completed.")
    return md


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    log_debug("Parsing command-line arguments.")
    parser = argparse.ArgumentParser(
        description="Generate an organized Table of Contents from exported Telegram messages."
    )
    parser.add_argument(
        "--export_file",
        type=str,
        default="telegram_messages.json",
        help="Path to the exported Telegram JSON file.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all messages instead of a sample.",
    )
    parser.add_argument(
        "--sample_size",
        type=int,
        default=50,
        help="Number of messages to sample if --all is not used.",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=50,
        help="Batch size for processing messages if --all is used.",
    )
    args = parser.parse_args()
    log_debug("Command-line arguments parsed.")
    return args


def main():
    args = parse_arguments()
    log_info(f"Loading exported messages from: {args.export_file}")
    messages = load_exported_messages(args.export_file)
    if not messages:
        log_error("No valid messages loaded. Exiting.")
        sys.exit(1)

    if args.all:
        # Split messages into batches and process them sequentially.
        batches = [
            messages[i : i + args.batch_size]
            for i in range(0, len(messages), args.batch_size)
        ]
        combined_toc = {}
        log_debug(f"Processing {len(messages)} messages in {len(batches)} batch(es).")
        for i, batch in enumerate(batches, start=1):
            log_debug(
                f"Processing batch {i}/{len(batches)} with {len(batch)} message(s)."
            )
            toc = process_messages(batch)
            for topic, entries in toc.items():
                combined_toc.setdefault(topic, []).extend(entries)
        final_toc = combined_toc
    else:
        sample = messages[: args.sample_size]
        log_debug(f"Processing a sample of {len(sample)} message(s).")
        final_toc = process_messages(sample)

    markdown = convert_toc_to_markdown(final_toc)
    try:
        with open("table_of_contents.json", "w", encoding="utf-8") as f_json:
            json.dump(final_toc, f_json, indent=2, ensure_ascii=False)
        log_debug("Saved JSON output to table_of_contents.json")
        with open("table_of_contents.md", "w", encoding="utf-8") as f_md:
            f_md.write(markdown)
        log_debug("Saved Markdown output to table_of_contents.md")
        log_info(
            "Successfully generated the Table of Contents in both JSON and Markdown formats."
        )
    except Exception as e:
        log_error(f"Error saving output: {e}")


if __name__ == "__main__":
    main()
