# Telegram Channel Organizer

This project provides a Python script to generate an organized table of contents from messages exported by the Telegram official app using an advanced AI summarization process. The script processes messages—either by sampling a subset or processing all messages in batches—leveraging the OpenAI API to summarize and categorize content. The latest implementation optimizes performance through concurrent batch processing and utilizes a refined JSON schema for the message export.

## Features

- **Telegram Export Support:**  
  Load and normalize messages from a Telegram channel export (JSON format). The messages follow a streamlined schema with key fields:

  - `id`, `classes`, `type`, `timestamp`, `time`, `content`, `links` (optional), and `media` (optional).

- **Summarization & Organization:**  
  Group messages by topic and obtain concise summaries along with full timestamps and primary links using the OpenAI API.

- **Concurrent Batch Processing & Merging:**  
  For large exports, the script processes messages in batches concurrently and uses intelligent merging (via additional AI calls) to create a coherent, consolidated table of contents.

- **Multiple Output Formats:**  
  Export the final table of contents in both JSON and Markdown formats.

## Installation

### Requirements

- Python 3.8+ (or compatible)
- [pip](https://pip.pypa.io/en/stable/)
- OpenAI API key

### Install Dependencies

Use `pip` to install the required packages:

```bash
pip install -r requirements.txt
```

_Note: Ensure you have a `.env` file in the project root (see Setup below)._

## Setup

1. **Create a `.env` File**

   In the project root directory, create a file named `.env` and add your configuration:

   ```dotenv
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_BASE_URL=your_openai_base_url_here
   ```

   Replace `your_openai_api_key_here` with your actual OpenAI API key. Adjust the base URL if necessary.

2. **Export Telegram Channel Content**

   Use the Telegram macOS app's export feature to export your channel messages. Convert the HTML export to JSON using the provided `convert_to_json.py` script. Save the resulting JSON file (default name: `telegram_messages.json`) in the project directory.

## Usage

Run the Python script (`main.py`) from the command line. The script provides two primary modes:

### 1. Sample Mode (Default)

Processes a subset of messages (default sample size is 50) to generate the table of contents.

```bash
python main.py --export_file telegram_messages.json --sample_size 50
```

If the number of messages in the file is less than the specified sample size, the script adjusts automatically.

### 2. All Messages Mode

Processes all messages by dividing them into batches and then merging the partial outputs with AI-driven re-summarization. Use the `--all` flag:

```bash
python main.py --export_file telegram_messages.json --all --batch_size 50
```

Here, `--batch_size` defines how many messages are processed per batch.

### Output Files

Upon completion, the script generates two files in the project root:

- `table_of_contents.json` – the organized table of contents in JSON format.
- `table_of_contents.md` – the organized table of contents in Markdown format.

## Command-Line Arguments

- **`--export_file`**  
  _Description:_ Specifies the path to the exported Telegram JSON file with the new schema.  
  _Default:_ `telegram_messages.json`

- **`--sample_size`**  
  _Description:_ Number of messages to sample for creating the table of contents (used when `--all` is not set).  
  _Default:_ `50`

- **`--all`**  
  _Description:_ Process and summarize all messages by dividing them into batches. When used, `--sample_size` is ignored.

- **`--batch_size`**  
  _Description:_ Number of messages per batch when processing all messages.  
  _Default:_ `50`

## Troubleshooting

- **No Messages Loaded:**  
  Ensure that your exported JSON file follows the expected schema for Telegram messages.

- **API Errors:**  
  Verify your OpenAI API key and base URL in the `.env` file.

- **Invalid JSON Output:**  
  If the API returns output that cannot be parsed as JSON, check the raw output printed to the console for debugging.

## Author

**Reza Shahnazar**  
GitHub: [rezashahnazar](https://github.com/rezashahnazar)  
Email: `reza.shahnazar@gmail.com`  
Work Email (Digikala): `r.shahnazar@digikala.com`

## License

MIT License

---

© 2025 Reza Shahnazar
