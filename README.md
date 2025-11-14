# YT Sentiment Analysis

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

**YT Sentiment Analysis** is a powerful, fully automated suite of tools designed to analyze brand perception and public sentiment using YouTube data. It leverages the power of Google's Gemini AI to provide deep, strategic insights from user-generated content.

This tool is perfect for marketers, brand strategists, and researchers who want to understand how a brand, product, or topic is perceived by the public, based on authentic user discussions on YouTube.

## How It Works

The pipeline is a four-step process that automates the entire workflow from data discovery to final analysis:

1.  **Crawl:** It starts by searching YouTube for relevant, user-generated videos based on your search terms (e.g., a brand or product name). It intelligently filters out official ads and low-quality content.
2.  **Extract:** It then extracts all user comments and the full audio from the discovered videos.
3.  **Analyze:** Using the Gemini Flash model, it processes the data in small, manageable batches, summarizing the key themes and sentiments.
4.  **Synthesize:** Finally, it feeds these summaries into the more powerful Gemini Pro model to generate a single, comprehensive strategic report in either HTML or Markdown format.

## Features

-   **Automated Pipeline:** Run the entire analysis with a single command.
-   **Intelligent Filtering:** Focus on genuine user content by filtering out ads and irrelevant videos.
-   **Multi-Modal Analysis:** Gathers insights from both text (comments) and audio (transcriptions).
-   **AI-Powered Insights:** Uses Gemini AI for nuanced and sophisticated analysis.
-   **Cached Processing:** Efficiently processes large amounts of data by caching intermediate results.
-   **Professional Reports:** Generates a clean, easy-to-read strategic report.

## Project Structure

```
.
├── config/
│   ├── config_gemini.ini
│   ├── gemini_analysis_prompt.txt
│   └── ...
├── yt-sentiment-analysis/
│   ├── scripts/
│   │   ├── youtube_brand_crawler.py
│   │   ├── youtube_comment_extractor.py
│   │   └── ...
│   └── __init__.py
├── .env.example
├── .gitignore
├── main.py
├── README.md
└── requirements.txt
```

## Setup and Installation

### 1. Prerequisites

-   Python 3.9 or higher
-   `pip` for package management

### 2. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/yt-sentiment-analysis.git
cd yt-sentiment-analysis
```

### 3. Set Up a Virtual Environment

It is highly recommended to use a virtual environment to keep the project's dependencies isolated.

```bash
# Create the virtual environment
python -m venv venv

# Activate it
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 4. Install Dependencies

Install all the required libraries with a single command:

```bash
pip install -r requirements.txt
```

### 5. Configure API Keys

You will need API keys for both the YouTube Data API and the Google Gemini API.

1.  **Copy the example environment file:**
    ```bash
    cp .env.example .env
    ```
2.  **Edit the `.env` file** and add your secret keys:
    -   `GEMINI_API_KEY`: Get this from [Google AI Studio](https://aistudio.google.com/app/apikey).
    -   `YOUTUBE_API_KEY`: Get this from the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).

### 6. Configure the Analysis

Open the `config/config_gemini.ini` file and customize the analysis:

-   **`search_terms`**: The brand, product, or topic you want to analyze (e.g., `Samsung Galaxy S25`).
-   **`search_modifiers`**: Keywords to find relevant videos (e.g., `review`, `opinion`).
-   **`min_view_count`**: The minimum number of views a video must have to be included.
-   **`max_results`**: The maximum number of videos to analyze.

## How to Run

Once everything is set up, you can run the entire analysis pipeline with a single command from the root directory of the project:

```bash
python main.py
```

You can also point to a different configuration file if you have multiple:

```bash
python main.py --config path/to/your/other_config.ini
```

The final report will be saved in the `outputs/` directory, inside a folder named after your search term.

## License

This project is licensed under the MIT License. See the [LICENSE](https://opensource.org/licenses/MIT) file for details.
