# YouTube Sentiment Analysis

(THIS IS NOT AN OFFICIAL GOOGLE TOOL) 

This project performs a comprehensive sentiment analysis of a brand on YouTube using Google's Gemini AI. It crawls for relevant videos, extracts comments and audio, and generates a strategic report summarizing brand perception.

## ⚠️ Disclaimer

**Please read this carefully before using this tool.**

1.  **Terms of Service Compliance:** This tool automates interactions with YouTube. Users are strictly responsible for ensuring their usage complies with [YouTube's Terms of Service](https://www.youtube.com/t/terms).
2.  **Cookie Usage:** This tool may require the use of browser cookies (`cookies.txt`) to access certain content (e.g., age-restricted videos) or to avoid bot detection. By providing your cookies, you are authorizing this script to act on your behalf. **Do not share your `cookies.txt` file with anyone.**
3.  **Rate Limiting:** Aggressive scraping can lead to IP bans or account restrictions. This tool is intended for personal research and analysis, not for high-volume data harvesting.


## Project Structure

- **`src/`**: Contains the core Python scripts for crawling, downloading, extracting comments/audio, and analysis.
- **`templates/`**: Contains HTML templates for reports and text prompts for Gemini.
- **`outputs/`**: Generated data (CSVs, audio/video files) and final reports are stored here.
- **`config.ini`**: Configuration file for search terms, models, and paths.

## Prerequisites

- Python 3.8+
- A Google Cloud Project with the **YouTube Data API v3** enabled.
- A Google AI Studio API Key for **Gemini**.
- `yt-dlp` (installed automatically via requirements, but ensures you have ffmpeg installed on your system for audio extraction).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd sentiment-analysis
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables:**
    - Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    - Open `.env` and add your API keys:
        ```env
        GEMINI_API_KEY=your_gemini_api_key
        YOUTUBE_API_KEY=your_youtube_api_key
        ```

4.  **Configure the Analysis:**
    - Copy `config.ini.example` to `config.ini` (if not already present):
        ```bash
        cp config.ini.example config.ini
        ```
    - Open `config.ini` and set your `search_terms`, `models`, and other preferences.
    - **Advanced Filtering & Sorting:**
        - `video_type`: Filter by format. Options: `shorts`, `videos`, or `both`.
        - `published_after`: Only analyze videos posted after a specific date (Format: `YYYY-MM-DD`).
        - `sort_by`: Order results by `relevance`, `viewCount`, `engagement`, or `date` (latest first).
        - `max_results`: Limit the number of videos to analyze (e.g., 100).

## Usage

You can run the entire pipeline or individual steps using `main.py`.

### Run the Full Pipeline
This will crawl videos, download them, extract comments, and generate the report.
```bash
python main.py all
```

### Run Individual Steps

1.  **Crawl Videos:** Finds relevant videos based on your search terms.
    ```bash
    python main.py crawl
    ```

2.  **Download Videos:** Downloads video/audio for the found videos.
    ```bash
    python main.py download
    ```

3.  **Extract Comments:** Fetches comments for the found videos.
    ```bash
    python main.py comments
    ```

4.  **Extract Audio (Optional):** Explicitly extracts audio (usually handled by download step).
    ```bash
    python main.py audio
    ```

5.  **Run Analysis:** Uses Gemini to analyze the data and generate the report.
    ```bash
    python main.py analyze
    ```

## Outputs

All outputs are saved in the `outputs/<brand_name>/` directory:
- `*_discovered_videos.csv`: List of videos found.
- `*_raw_comments.csv`: Extracted comments.
- `*_strategic_report.html`: The final analysis report.
- `audio/` & `video/`: Temporary media files (cleaned up after analysis).
