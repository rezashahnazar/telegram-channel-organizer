# Telegram Channel Organizer

This project provides a Python script to generate an organized table of contents from messages exported by the Telegram official app using an advanced AI summarization process. The script processes messages—either by sampling a subset or processing all messages in batches—leveraging the Gemini API to summarize and categorize content.

## Features

- **Telegram Export Processing:**

  - Converts HTML exports to JSON using `convert_to_json.py`
  - Extracts message content, timestamps, links, and media attachments
  - Supports both service messages and regular content
  - Handles media files with titles, sizes, and thumbnails

- **AI-Powered Summarization:**

  - Uses Gemini 2.0 Flash API for intelligent content organization
  - Groups messages by topics automatically
  - Generates concise summaries with timestamps and links
  - Supports batch processing for large exports

- **Multiple Output Formats:**
  - Generates both JSON and Markdown tables of contents
  - Includes detailed logging of AI operations
  - Preserves message metadata in organized format

## Installation

### Requirements

- Python 3.8+
- [pip](https://pip.pypa.io/en/stable/)
- Gemini API access

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Setup

1. **Create a `.env` File**

   Create a `.env` file in the project root with your AI API configuration:

   ```dotenv
   AI_API_KEY=your_gemini_api_key_here
   AI_BASE_URL=your_gemini_api_base_url_here
   ```

2. **Export Telegram Channel Content**

   a. Use Telegram Desktop to export channel messages as HTML
   b. Convert the HTML export to JSON:

   ```bash
   python convert_to_json.py --input_file export/messages.html --output_file telegram_messages.json
   ```

## Usage

### Converting HTML Export to JSON

```bash
python convert_to_json.py --input_file path/to/messages.html --output_file telegram_messages.json
```

### Generating Table of Contents

The main script (`main.py`) supports two modes:

#### 1. Sample Mode (Default)

```bash
python main.py --export_file telegram_messages.json --sample_size 50
```

#### 2. Batch Processing Mode

```bash
python main.py --export_file telegram_messages.json --all --batch_size 50
```

### Command-Line Arguments

#### convert_to_json.py

- `--input_file`: Path to HTML export (default: "export/messages.html")
- `--output_file`: Path for JSON output (default: "telegram_messages.json")

#### main.py

- `--export_file`: Path to JSON file (default: "telegram_messages.json")
- `--all`: Process all messages in batches
- `--sample_size`: Number of messages to sample (default: 50)
- `--batch_size`: Messages per batch when using --all (default: 50)

### Output Files

The script generates:

- `table_of_contents.json`: Organized content in JSON format
- `table_of_contents.md`: Markdown formatted table of contents
- `logs/ai_calls_YYYY-MM-DD.jsonl`: Daily logs of AI API calls

## Troubleshooting

- **HTML Parsing Issues:**  
  Ensure the HTML export is from the latest version of Telegram Desktop

- **AI API Errors:**

  - Verify AI_API_KEY and AI_BASE_URL in .env
  - Check the logs in logs/ai*calls*\*.jsonl for detailed error information
  - Ensure you have access to the Gemini 2.0 Flash model

- **JSON Parsing Errors:**
  - Ensure the input JSON follows the expected schema
  - Check for proper UTF-8 encoding in the export

## Author

**Reza Shahnazar**  
GitHub: [rezashahnazar](https://github.com/rezashahnazar)  
Email: reza.shahnazar@gmail.com

## License

MIT License

---

© 2025 Reza Shahnazar
