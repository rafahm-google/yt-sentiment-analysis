import streamlit as st
import configparser
import os
import subprocess
import sys
from dotenv import load_dotenv, set_key

# Load environment variables
load_dotenv()

st.set_page_config(page_title="YouTube Sentiment Analysis", page_icon="▶️", layout="wide")

st.title("YouTube Sentiment Analysis Pipeline")
st.markdown("Configure and run the YouTube Sentiment Analysis pipeline directly from this interface.")

# Define file paths
CONFIG_PATH = "config.ini"
ENV_PATH = ".env"

# Initialize ConfigParser
config = configparser.ConfigParser()

# Load existing config or setup defaults
if not os.path.exists(CONFIG_PATH):
    if os.path.exists("config.ini.example"):
        import shutil
        shutil.copy("config.ini.example", CONFIG_PATH)
config.read(CONFIG_PATH)

def save_env(gemini_key, youtube_key):
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'w') as f:
            f.write("")
    
    if gemini_key:
        set_key(ENV_PATH, "GEMINI_API_KEY", gemini_key)
    if youtube_key:
        set_key(ENV_PATH, "YOUTUBE_API_KEY", youtube_key)
    
    st.success("Environment variables saved to `.env`")

def save_config(params):
    # Ensure sections exist
    for section in ["Crawler", "Analysis"]:
        if not config.has_section(section):
            config.add_section(section)
    
    # Crawler
    config.set("Crawler", "search_terms", params.get("search_terms", ""))
    config.set("Crawler", "search_modifiers", params.get("search_modifiers", ""))
    config.set("Crawler", "exclude_keywords", params.get("exclude_keywords", ""))
    config.set("Crawler", "min_view_count", str(params.get("min_view_count", 100000)))
    config.set("Crawler", "sort_by", params.get("sort_by", "relevance"))
    config.set("Crawler", "max_results", str(params.get("max_results", 100)))
    config.set("Crawler", "region_code", params.get("region_code", "US"))
    config.set("Crawler", "video_type", params.get("video_type", "both"))
    config.set("Crawler", "include_channels", params.get("include_channels", ""))
    config.set("Crawler", "exclude_channels", params.get("exclude_channels", ""))
    config.set("Crawler", "max_comments_per_video", str(params.get("max_comments_per_video", 100)))
    config.set("Analysis", "output_language", params.get("output_language", "Portuguese"))
    

    
    # Analysis
    config.set("Analysis", "pro_model_name", params.get("pro_model_name", config.get("Analysis", "pro_model_name", fallback="gemini-2.5-pro")))
    config.set("Analysis", "flash_model_name", params.get("flash_model_name", config.get("Analysis", "flash_model_name", fallback="gemini-3-flash-preview")))
    config.set("Analysis", "pro_prompt_template_path", params.get("pro_prompt_template_path", config.get("Analysis", "pro_prompt_template_path", fallback="templates/prompts/topic_analysis.txt")))
    config.set("Analysis", "flash_prompt_template_path", params.get("flash_prompt_template_path", config.get("Analysis", "flash_prompt_template_path", fallback="templates/prompts/topic_flash.txt")))
    config.set("Analysis", "batch_size", str(params.get("batch_size", config.get("Analysis", "batch_size", fallback="3"))))
    config.set("Analysis", "cache_dir", params.get("cache_dir", config.get("Analysis", "cache_dir", fallback="outputs/cache")))
    config.set("Analysis", "report_format", params.get("report_format", config.get("Analysis", "report_format", fallback="html")))
    config.set("Analysis", "additional_context", params.get("additional_context", ""))
    
    with open(CONFIG_PATH, 'w') as configfile:
        config.write(configfile)
    
    st.success("Configuration saved to `config.ini`")

# --- UI Layout ---

tab1, tab2 = st.tabs(["Pipeline Setup & Execution", "Results & Outputs"])

with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.header("1. Configuration")
        
        with st.expander("API Keys (.env)", expanded=False):
            gemini_key = st.text_input("GEMINI_API_KEY", value=os.getenv("GEMINI_API_KEY", ""), type="password")
            youtube_key = st.text_input("YOUTUBE_API_KEY", value=os.getenv("YOUTUBE_API_KEY", ""), type="password")
            if st.button("Save Settings"):
                save_env(gemini_key, youtube_key)
                
        with st.expander("Pipeline Configuration (config.ini)", expanded=True):
            crawler_search = st.text_input("Search Terms", value=config.get("Crawler", "search_terms", fallback="copa do mundo"))
            crawler_mod = st.text_input("Search Modifiers (Optional)", value=config.get("Crawler", "search_modifiers", fallback="futebol"))
            crawler_exclude = st.text_input("Exclude Keywords (Optional)", value=config.get("Crawler", "exclude_keywords", fallback="EUA, Americano"))
            crawler_min_view = st.number_input("Min View Count", value=config.getint("Crawler", "min_view_count", fallback=100000), step=10000)
            crawler_sort = st.selectbox("Sort By", options=["relevance", "viewCount", "engagement"], index=["relevance", "viewCount", "engagement"].index(config.get("Crawler", "sort_by", fallback="relevance")))
            crawler_max = st.slider("Videos to Analyze", min_value=1, max_value=50, value=min(config.getint("Crawler", "max_results", fallback=10), 50))
            
            extract_all_comments = st.checkbox("Extract All Comments (Overrides limit)", value=config.getint("Crawler", "max_comments_per_video", fallback=100) == -1)
            
            if not extract_all_comments:
                crawler_max_comments = st.slider("Max Comments per Video", min_value=10, max_value=1000, value=config.getint("Crawler", "max_comments_per_video", fallback=100), step=10)
            else:
                crawler_max_comments = -1
                
            crawler_region = st.text_input("Region Code (Optional)", value=config.get("Crawler", "region_code", fallback="US"))
            crawler_type = st.selectbox("Video Type", options=["both", "videos", "shorts"], index=["both", "videos", "shorts"].index(config.get("Crawler", "video_type", fallback="both")))
            crawler_include_ch = st.text_input("Include Channels (Optional)", value=config.get("Crawler", "include_channels", fallback=""))
            crawler_exclude_ch = st.text_input("Exclude Channels (Optional)", value=config.get("Crawler", "exclude_channels", fallback=""))
            
            st.subheader("Language & Context")
            lang_options = ["Portuguese", "English", "Spanish", "Other"]
            current_lang = config.get("Analysis", "output_language", fallback="Portuguese")
            
            if current_lang in lang_options[:-1]: # Exclude 'Other' for index search
                lang_index = lang_options.index(current_lang)
            else:
                lang_index = lang_options.index("Other")
                
            selected_lang = st.selectbox("Output Language", options=lang_options, index=lang_index)
            
            if selected_lang == "Other":
                custom_lang = st.text_input("Specify Language", value=current_lang if current_lang not in lang_options[:-1] else "")
                output_language = custom_lang
            else:
                output_language = selected_lang
            additional_context = st.text_area("Additional Instructions for Analysis/Presentation (Optional)", value=config.get("Analysis", "additional_context", fallback=""))
            

            

    
            if st.button("Save Configuration"):
                params = {
                    "search_terms": crawler_search,
                    "search_modifiers": crawler_mod,
                    "exclude_keywords": crawler_exclude,
                    "min_view_count": crawler_min_view,
                    "sort_by": crawler_sort,
                    "max_results": crawler_max,
                    "region_code": crawler_region,
                    "video_type": crawler_type,
                    "include_channels": crawler_include_ch,
                    "exclude_channels": crawler_exclude_ch,
                    "additional_context": additional_context,
                    "max_comments_per_video": crawler_max_comments,
                    "output_language": output_language,
                }
                save_config(params)
    
    with col2:
        st.header("2. Execution")
        st.markdown("Select a step to run in the pipeline. Make sure you have saved your configuration first.")
        
        step_to_run = st.selectbox(
            "Select Pipeline Step", 
            options=["all", "crawl", "comments", "analyze", "slides"],
            format_func=lambda x: {
                "all": "Run All Steps (Crawl, Comments, Analyze, Slides)",
                "crawl": "Step 1: Crawl Videos",
                "comments": "Step 2: Extract Comments",
                "analyze": "Step 3: Analyze Data",
                "slides": "Step 4: Generate Presentation Slides"
            }[x]
        )
        
        if st.button("Run Pipeline", type="primary"):
            st.subheader(f"Execution Logs (Step: {step_to_run})")
            
            # Create a container for logs
            log_container = st.empty()
            
            import re
            cmd = [sys.executable, "main.py", step_to_run]
            
            try:
                # We use distinct execution block to display terminal output in real-time
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Combine stderr into stdout
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Show a nice spinner and load logs only when done to avoid WebSocket flooding
                with st.spinner("Executing pipeline... This may take a few minutes while the AI generates content and images."):
                    stdout, _ = process.communicate()
                
                if process.returncode == 0:
                    st.success("🎉 Pipeline executed successfully! Go to the 'Results & Outputs' tab to view the presentation and report.")
                    with st.expander("Show Execution Logs (Advanced)", expanded=False):
                        st.code(stdout, language="bash")
                else:
                    st.error(f"Error executing pipeline (Code: {process.returncode}). Check logs below.")
                    with st.expander("Show Execution Logs (Advanced)", expanded=True):
                        st.code(stdout, language="bash")
                    
            except Exception as e:
                st.error(f"Failed to execute main.py: {e}")

with tab2:
    st.header("Results & Outputs")
    st.markdown("View the generated analysis reports and raw data.")
    
    output_dir = "outputs"
    
    if os.path.exists(output_dir) and os.path.isdir(output_dir):
        # Find all brand directories (excluding files and the cache dir)
        brand_dirs = [d for d in os.listdir(output_dir) 
                      if os.path.isdir(os.path.join(output_dir, d)) and d != "cache"]
                      
        if not brand_dirs:
            st.info("No output directories found yet. Run the pipeline first.")
        else:
            selected_brand = st.selectbox("Select Brand/Project:", options=brand_dirs)
            
            if selected_brand:
                brand_path = os.path.join(output_dir, selected_brand)
                
                # Specific Visualizations for C-Level
                try:
                    # 1. Visualization for Slides (Interactive Deck)
                    deck_file = os.path.join(brand_path, f"{selected_brand}_deck.html")
                    if os.path.exists(deck_file):
                        st.subheader("Presentation Slides (Use keyboard arrows)")
                        with open(deck_file, 'r', encoding='utf-8') as f:
                            deck_content = f.read()
                        import streamlit.components.v1 as components
                        components.html(deck_content, height=600, scrolling=True)
                        

                        
                        # Provide download button for PDF if it exists
                        pdf_file = os.path.join(brand_path, f"{selected_brand}_presentation.pdf")
                        if os.path.exists(pdf_file):
                            with open(pdf_file, 'rb') as f:
                                pdf_data = f.read()
                            st.download_button(
                                label="Download Presentation PDF",
                                data=pdf_data,
                                file_name=f"{selected_brand}_presentation.pdf",
                                mime='application/pdf'
                            )
                    else:
                        st.info("Interactive slide presentation not found.")
                    
                    st.markdown("---")
                    
                    # 2. Visualization for HTML Report
                    report_file = os.path.join(brand_path, f"{selected_brand}_strategic_report.html")
                    if os.path.exists(report_file):
                        st.subheader("Strategic Report")
                        with open(report_file, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                        import streamlit.components.v1 as components
                        components.html(html_content, height=800, scrolling=True)
                        
                        st.download_button(
                            label="Download HTML Report",
                            data=html_content,
                            file_name=f"{selected_brand}_strategic_report.html",
                            mime='text/html'
                        )
                    else:
                        st.info("Strategic report not found.")
                        
                except Exception as e:
                    st.error(f"Error loading visualizations: {e}")
    else:
        st.info("Outputs directory does not exist yet. Run the pipeline first.")
