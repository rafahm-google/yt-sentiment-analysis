import streamlit as st
import configparser
import os
import re
import subprocess
import sys
from dotenv import load_dotenv, set_key

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from drive_uploader import list_folders_in_drive, download_file_from_drive, find_pdf_in_folder, find_file_by_name_in_folder
from briefing_planner import BriefingPlanner

# Load environment variables
load_dotenv()

st.set_page_config(page_title="YouTube Sentiment Analysis", page_icon="▶️", layout="wide")

st.title("YouTube Sentiment Analysis Pipeline")
st.markdown("Configure and run the YouTube Sentiment Analysis pipeline directly from this interface.")

# Define file paths
CONFIG_PATH = "config.ini"
ENV_PATH = ".env"

# Initialize ConfigParser
config = configparser.ConfigParser(interpolation=None)

# Load existing config or setup defaults
if not os.path.exists(CONFIG_PATH):
    if os.path.exists("config.ini.example"):
        import shutil
        shutil.copy("config.ini.example", CONFIG_PATH)
config.read(CONFIG_PATH)

# Helper to safely get config options
def get_config_val(section, key, fallback=""):
    return config.get(section, key, fallback=fallback)

# Initialize session state keys safely (robust against existing sessions)
def init_session_key(key, default_val):
    if key not in st.session_state:
        st.session_state[key] = default_val

init_session_key("crawler_search", get_config_val("Crawler", "search_terms", ""))
init_session_key("crawler_search_queries", get_config_val("Crawler", "search_queries", ""))
init_session_key("crawler_mod", get_config_val("Crawler", "search_modifiers", ""))
init_session_key("crawler_exclude", get_config_val("Crawler", "exclude_keywords", ""))
init_session_key("crawler_min_view", int(get_config_val("Crawler", "min_view_count", "10000")))
init_session_key("crawler_sort", get_config_val("Crawler", "sort_by", "relevance"))
init_session_key("crawler_max", min(max(int(get_config_val("Crawler", "max_results", "10")), 1), 100))
init_session_key("crawler_max_comments", min(max(int(get_config_val("Crawler", "max_comments_per_video", "10")), 10), 50))
init_session_key("crawler_region", get_config_val("Crawler", "region_code", "US"))
init_session_key("crawler_type", get_config_val("Crawler", "video_type", "both"))
init_session_key("crawler_include_ch", get_config_val("Crawler", "include_channels", ""))
init_session_key("crawler_exclude_ch", get_config_val("Crawler", "exclude_channels", ""))
init_session_key("crawler_published_after", get_config_val("Crawler", "published_after", ""))
init_session_key("enable_semantic_filter", get_config_val("Crawler", "enable_semantic_filter", "true").lower() == "true")
init_session_key("relevance_threshold", int(get_config_val("Crawler", "relevance_threshold", "70")))
init_session_key("campaign_briefing", get_config_val("Crawler", "campaign_briefing", ""))
init_session_key("additional_context", get_config_val("Analysis", "additional_context", ""))

lang_options_init = ["Portuguese", "English", "Spanish"]
current_lang_init = get_config_val("Analysis", "output_language", "Portuguese")
if "selected_lang_ui" not in st.session_state:
    if current_lang_init in lang_options_init:
        st.session_state.selected_lang_ui = current_lang_init
        st.session_state.custom_lang_ui = ""
    else:
        st.session_state.selected_lang_ui = "Other"
        st.session_state.custom_lang_ui = current_lang_init

init_session_key("session_runs", [])
init_session_key("current_run_id", None)
init_session_key("pipeline_running", False)

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
    config.set("Crawler", "search_queries", params.get("search_queries", ""))
    config.set("Crawler", "search_modifiers", params.get("search_modifiers", ""))
    config.set("Crawler", "exclude_keywords", params.get("exclude_keywords", ""))
    config.set("Crawler", "min_view_count", str(params.get("min_view_count", 100000)))
    config.set("Crawler", "sort_by", params.get("sort_by", "relevance"))
    config.set("Crawler", "max_results", str(params.get("max_results", 10)))
    config.set("Crawler", "region_code", params.get("region_code", "US"))
    config.set("Crawler", "video_type", params.get("video_type", "both"))
    config.set("Crawler", "include_channels", params.get("include_channels", ""))
    config.set("Crawler", "exclude_channels", params.get("exclude_channels", ""))
    config.set("Crawler", "published_after", params.get("published_after", ""))
    config.set("Crawler", "max_comments_per_video", str(params.get("max_comments_per_video", 100)))
    config.set("Crawler", "enable_semantic_filter", str(params.get("enable_semantic_filter", True)).lower())
    config.set("Crawler", "relevance_threshold", str(params.get("relevance_threshold", 70)))
    config.set("Crawler", "campaign_briefing", params.get("campaign_briefing", ""))
    config.set("Analysis", "output_language", params.get("output_language", "Portuguese"))
    

    
    config.set("Analysis", "pro_model_name", params.get("pro_model_name", config.get("Analysis", "pro_model_name", fallback="gemini-3.7-flash")))
    config.set("Analysis", "flash_model_name", params.get("flash_model_name", config.get("Analysis", "flash_model_name", fallback="gemini-3.7-flash")))
    config.set("Analysis", "fallback_model_name", params.get("fallback_model_name", config.get("Analysis", "fallback_model_name", fallback="gemini-3.6-flash")))
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

tab1, tab2, tab3 = st.tabs(["🆕 Run New Analysis", "📊 Current Session Results", "☁️ Historical Reports (Google Drive)"])

with tab1:
    st.header("🆕 Launch a New Sentiment Analysis")
    
    # Mode Selector
    analysis_mode = st.radio(
        "Choose Analysis Setup Mode:",
        options=[
            "🧠 Gemini AI Campaign Assistant (Guided Mode)",
            "🎯 Manual Mode (Exact Keywords)"
        ],
        index=0,
        horizontal=True,
        help="Select Guided Mode if you have a campaign briefing idea, or Manual Mode if you know the exact search terms."
    )
    
    st.markdown("---")
    
    if "Guided Mode" in analysis_mode:
        st.subheader("🧠 Gemini AI Campaign Assistant (Deep Thinking)")
        st.markdown("Describe your campaign objective or research theme below. **Gemini 3.6 Flash** will use real-time Google Search Grounding to formulate an optimal YouTube search strategy.")
        
        briefing_input = st.text_area(
            "Campaign Briefing / Objective / High-Level Idea",
            placeholder="e.g., We want to run a campaign analyzing consumer reactions and creator reviews around eco-friendly sustainable sneakers and ethical fashion trends in Brazil.",
            key="campaign_briefing_text_input"
        )
        
        col_plan1, col_plan2, col_plan3 = st.columns([1, 1, 1])
        with col_plan1:
            plan_region = st.text_input("Target Region Code", value=st.session_state.crawler_region or "BR", key="plan_region_code", help="2-letter ISO country code (e.g. BR, US)")
        with col_plan2:
            plan_lang = st.selectbox("Briefing Output Language", options=["Portuguese", "English", "Spanish"], index=0, key="plan_lang_sel")
        with col_plan3:
            use_grounding = st.checkbox("Google Search Grounding", value=True, help="Enable real-time Google Search to pull latest news and market context.")

        if st.button("🧠 Generate Search Strategy with Gemini 3.6 Flash", use_container_width=True, type="primary"):
            if not briefing_input.strip():
                st.warning("Please enter a campaign briefing or objective first.")
            else:
                with st.spinner("Analyzing briefing with Gemini 3.6 Flash & Google Search..."):
                    try:
                        planner = BriefingPlanner()
                        target_lang = plan_lang if plan_lang != "Other" else st.session_state.custom_lang_ui or "Portuguese"
                        strategy = planner.plan_campaign(
                            campaign_briefing=briefing_input,
                            output_language=target_lang,
                            region_code=plan_region,
                            additional_context=st.session_state.additional_context,
                            enable_google_search=use_grounding
                        )
                        st.session_state.generated_strategy = strategy
                        st.success("Search strategy generated successfully!")
                    except Exception as e:
                        st.error(f"Error generating search strategy: {e}")

        if "generated_strategy" in st.session_state and st.session_state.generated_strategy:
            strat = st.session_state.generated_strategy
            st.markdown("---")
            st.markdown("### 📋 AI Generated Search Strategy")
            
            st.info(f"**🧠 Strategic Rationale (Deep Thinking):**\n\n{strat.get('strategic_reasoning', '')}")
            
            if strat.get('campaign_objective_summary'):
                st.info(f"**🎯 Campaign Objective Summary (Relevance Filter Target):**\n\n{strat.get('campaign_objective_summary')}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Primary Search Subject:** `{strat.get('primary_search_term', '')}`")
                st.write(f"**Target Region:** `{strat.get('recommended_region', 'BR')}`")
                st.write("**Suggested YouTube Search Queries:**")
                for q in strat.get('search_queries', []):
                    st.markdown(f"- `{q}`")
            with c2:
                st.write(f"**Search Modifiers:** {', '.join(strat.get('search_modifiers', []))}")
                st.write(f"**Exclude Keywords:** {', '.join(strat.get('exclude_keywords', []))}")
                if strat.get('recommended_channels'):
                    st.write(f"**Recommended Channels:** {', '.join(strat.get('recommended_channels', []))}")

            if st.button("⚡ Apply Strategy to Pipeline Form", type="secondary", use_container_width=True):
                if strat.get('primary_search_term'):
                    st.session_state.crawler_search = strat.get('primary_search_term')
                if strat.get('search_queries'):
                    st.session_state.crawler_search_queries = "; ".join(strat.get('search_queries'))
                if strat.get('search_modifiers'):
                    st.session_state.crawler_mod = ", ".join(strat.get('search_modifiers'))
                if strat.get('exclude_keywords'):
                    st.session_state.crawler_exclude = ", ".join(strat.get('exclude_keywords'))
                if strat.get('recommended_region'):
                    st.session_state.crawler_region = strat.get('recommended_region')
                if strat.get('campaign_objective_summary'):
                    st.session_state.campaign_briefing = strat.get('campaign_objective_summary')
                elif briefing_input.strip():
                    st.session_state.campaign_briefing = briefing_input.strip()
                if strat.get('additional_context_for_analysis'):
                    st.session_state.additional_context = strat.get('additional_context_for_analysis')
                st.success("Strategy applied to crawler configuration below!")
                st.rerun()

        st.markdown("---")
        st.subheader("⚙️ Review & Launch Configuration")
    else:
        # Reset AI search queries when explicitly switching to Manual Mode
        st.session_state.crawler_search_queries = ""
        st.subheader("🎯 Manual Mode (Exact Keywords)")
        st.markdown("Directly enter your brand name, target search terms, language, and custom context.")
    
    # Clean main inputs
    crawler_search = st.text_input(
        "Brand or Topic Name", 
        value=st.session_state.crawler_search,
        help="Enter the exact brand name or topic you want to analyze (e.g., 'Coca Cola' or 'iPhone 15 review')."
    )
    # Sync back to session state immediately
    st.session_state.crawler_search = crawler_search
    
    col_lang, col_context = st.columns([1, 2])
    
    with col_lang:
        lang_options = ["Portuguese", "English", "Spanish", "Other"]
        selected_lang = st.selectbox(
            "Output Language", 
            options=lang_options, 
            index=lang_options.index(st.session_state.selected_lang_ui) if st.session_state.selected_lang_ui in lang_options else 0,
            help="The final strategic report and slide presentation will be generated in this language."
        )
        st.session_state.selected_lang_ui = selected_lang
        
        if selected_lang == "Other":
            custom_lang = st.text_input("Specify Language", value=st.session_state.custom_lang_ui)
            st.session_state.custom_lang_ui = custom_lang
            
    with col_context:
        additional_context = st.text_area(
            "Additional Instructions / Briefing (Optional)", 
            value=st.session_state.additional_context,
            placeholder="e.g., Focus on positive customer reviews and highlight complaints about battery life.",
            help="Provide any specific instructions, focus areas, or background context for the AI report."
        )
        st.session_state.additional_context = additional_context
        
    # Advanced Expander (Collapsible, hidden from non-tech users)
    with st.expander("⚙️ Advanced Tuning & Execution Options", expanded=False):
        st.markdown("### 🎯 AI Semantic Relevance Filter")
        st.checkbox("Enable AI Semantic Relevance Filter", key="enable_semantic_filter", help="Use two-stage AI semantic filtering to eliminate off-topic videos before comment extraction.")
        st.slider("Relevance Score Threshold (0-100)", min_value=50, max_value=95, step=5, key="relevance_threshold", help="Minimum relevance score (0-100) required to keep a video (default: 70).")
        
        st.markdown("---")
        st.markdown("### Search Fine-Tuning")
        st.text_input("Search Modifiers (Optional)", key="crawler_mod", help="Keywords appended to search (comma-separated, e.g. 'review, unboxing')")
        st.text_input("Exclude Keywords (Optional)", key="crawler_exclude", help="Ignore videos containing these keywords (comma-separated)")
        
        col_adv1, col_adv2 = st.columns(2)
        with col_adv1:
            st.number_input("Min View Count", key="crawler_min_view", step=10000, help="Only analyze videos with at least this many views")
            st.selectbox("Sort By", options=["relevance", "viewCount", "engagement"], key="crawler_sort", help="How to rank the discovered videos")
            st.text_input("Region Code (Optional)", key="crawler_region", help="Two-letter country code (e.g., 'US', 'BR')")
            st.text_input("Published After (Optional)", key="crawler_published_after", help="Format: YYYY-MM-DD. Only retrieve videos published after this date.")
            
        with col_adv2:
            st.slider("Videos to Analyze", min_value=1, max_value=100, key="crawler_max", help="Maximum number of top videos to process")
            st.slider("Max Comments per Video", min_value=10, max_value=50, step=10, key="crawler_max_comments", help="How many comments to extract per video")
            st.selectbox("Video Type", options=["both", "videos", "shorts"], key="crawler_type", help="Filter by video length/type")
            
        st.text_input("Include Channels (Optional)", key="crawler_include_ch", help="Only search these channels (comma-separated)")
        st.text_input("Exclude Channels (Optional)", key="crawler_exclude_ch", help="Completely ignore these channels (comma-separated)")
        
        st.markdown("---")
        st.markdown("### Pipeline Execution Step")
        step_to_run = st.selectbox(
            "Select Pipeline Step to Execute", 
            options=["all", "crawl", "comments", "analyze", "slides"],
            format_func=lambda x: {
                "all": "Run Full Analysis (Recommended)",
                "crawl": "Step 1 Only: Crawl Videos",
                "comments": "Step 2 Only: Extract Comments",
                "analyze": "Step 3 Only: Run AI Analysis",
                "slides": "Step 4 Only: Generate Presentation Slides"
            }[x]
        )
        
    st.markdown("### 🎯 Desired Output Formats")
    st.markdown("Select which output formats you want to generate. Unchecking formats you don't need (like PDF Slides) skips those steps to save time and API tokens.")
    
    output_format_options = {
        "HTML Strategic Report": "html",
        "Text / Markdown Report": "markdown",
        "PDF Presentation Deck": "pdf"
    }

    selected_format_labels = st.multiselect(
        "Select Output Formats:",
        options=list(output_format_options.keys()),
        default=["HTML Strategic Report", "Text / Markdown Report", "PDF Presentation Deck"],
        help="Uncheck 'PDF Presentation Deck' to skip slide image generation and finish 2 minutes faster!"
    )

    selected_format_codes = [output_format_options[label] for label in selected_format_labels]
    st.session_state.requested_outputs = ",".join(selected_format_codes)
    
    st.markdown("---")
    
    # Action Button
    if st.button("🚀 Launch Sentiment Analysis Pipeline", type="primary", use_container_width=True):
        st.session_state.pipeline_running = True
        try:
            st.subheader("Execution Status & Live Progress")
            
            # Create unique run_id and session config
            import uuid
            from datetime import datetime
            
            search_terms = st.session_state.crawler_search
            safe_brand_name = re.sub(r'\W+', '', search_terms.replace(' ', '_'))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_id = f"{safe_brand_name}_{timestamp}_{str(uuid.uuid4())[:6]}"
            st.session_state.current_run_id = run_id
            
            # Add to session execution history list
            st.session_state.session_runs.append((f"{search_terms} - {datetime.now().strftime('%H:%M:%S')}", run_id))
            
            # Create temp config parser
            temp_config = configparser.ConfigParser(interpolation=None)
            
            # Copy existing config sections
            for section in config.sections():
                temp_config.add_section(section)
                for k, v in config.items(section):
                    temp_config.set(section, k, v)
                    
            # Ensure sections exist
            for section in ["General", "Crawler", "Analysis"]:
                if not temp_config.has_section(section):
                    temp_config.add_section(section)
                    
            # Override with session state values
            temp_config.set("General", "run_id", run_id)
            temp_config.set("Crawler", "search_terms", st.session_state.crawler_search)
            temp_config.set("Crawler", "search_queries", getattr(st.session_state, 'crawler_search_queries', ''))
            temp_config.set("Crawler", "search_modifiers", st.session_state.crawler_mod)
            temp_config.set("Crawler", "exclude_keywords", st.session_state.crawler_exclude)
            temp_config.set("Crawler", "min_view_count", str(st.session_state.crawler_min_view))
            temp_config.set("Crawler", "sort_by", st.session_state.crawler_sort)
            temp_config.set("Crawler", "max_results", str(st.session_state.crawler_max))
            temp_config.set("Crawler", "max_comments_per_video", str(st.session_state.crawler_max_comments))
            temp_config.set("Crawler", "region_code", st.session_state.crawler_region)
            temp_config.set("Crawler", "video_type", st.session_state.crawler_type)
            temp_config.set("Crawler", "include_channels", st.session_state.crawler_include_ch)
            temp_config.set("Crawler", "exclude_channels", st.session_state.crawler_exclude_ch)
            temp_config.set("Crawler", "published_after", st.session_state.crawler_published_after)
            temp_config.set("Crawler", "enable_semantic_filter", str(getattr(st.session_state, 'enable_semantic_filter', True)).lower())
            temp_config.set("Crawler", "relevance_threshold", str(getattr(st.session_state, 'relevance_threshold', 70)))
            
            # Reviewer Finding 4: In Guided Mode, set campaign_briefing to briefing/objective summary; in Manual Mode, set to crawler_search
            if "Guided Mode" in analysis_mode:
                briefing_val = ""
                if "generated_strategy" in st.session_state and st.session_state.generated_strategy and st.session_state.generated_strategy.get('campaign_objective_summary'):
                    briefing_val = st.session_state.generated_strategy.get('campaign_objective_summary')
                elif getattr(st.session_state, 'campaign_briefing_text_input', ''):
                    briefing_val = st.session_state.campaign_briefing_text_input
                elif getattr(st.session_state, 'campaign_briefing', ''):
                    briefing_val = st.session_state.campaign_briefing
                else:
                    briefing_val = st.session_state.crawler_search
                temp_config.set("Crawler", "campaign_briefing", briefing_val)
            else:
                briefing_val = st.session_state.additional_context.strip() if st.session_state.additional_context.strip() else st.session_state.crawler_search
                temp_config.set("Crawler", "campaign_briefing", briefing_val)
            
            if st.session_state.selected_lang_ui == "Other":
                temp_config.set("Analysis", "output_language", st.session_state.custom_lang_ui)
            else:
                temp_config.set("Analysis", "output_language", st.session_state.selected_lang_ui)
                
            temp_config.set("Analysis", "additional_context", st.session_state.additional_context)
            temp_config.set("Analysis", "requested_outputs", getattr(st.session_state, 'requested_outputs', 'html,pdf,markdown,notebooklm'))
            
            # Write temp config to disk
            os.makedirs("outputs/cache", exist_ok=True)
            temp_config_path = f"outputs/cache/config_{run_id}.ini"
            with open(temp_config_path, 'w', encoding='utf-8') as f:
                temp_config.write(f)
            
            status_text = st.empty()
            progress_bar = st.progress(0)
            stdout_acc = []
            
            status_text.text("Starting pipeline...")
            
            # Execute command
            cmd = [sys.executable, "main.py", step_to_run, "--config", temp_config_path]
            
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                for line in iter(process.stdout.readline, ''):
                    stdout_acc.append(line)
                    # Parse for summary
                    if "STEP 1: CRAWLING VIDEOS" in line:
                        status_text.text("Step 1/4: Discovering relevant YouTube videos...")
                        progress_bar.progress(10)
                    elif "STEP 3: EXTRACTING COMMENTS" in line:
                        status_text.text("Step 2/4: Harvesting customer comments...")
                        progress_bar.progress(30)
                    elif "STEP 4: RUNNING ANALYSIS PIPELINE" in line:
                        status_text.text("Step 3/4: Processing & analyzing feedback with Gemini AI...")
                        progress_bar.progress(50)
                    elif "STEP 5: GENERATING SLIDES" in line:
                        status_text.text("Step 4/4: Creating visual presentation slides (this takes a few minutes)...")
                        progress_bar.progress(75)
                    elif "Processing batch" in line:
                        match = re.search(r'Processing batch (\d+)/(\d+)', line)
                        if match:
                            curr = int(match.group(1))
                            total = int(match.group(2))
                            status_text.text(f"Step 3/4: AI Analysis - Batch {curr} of {total}...")
                            progress_bar.progress(50 + int((curr/total)*20))
                    elif "Processando Slide" in line:
                        match = re.search(r'Processando Slide (\d+)', line)
                        if match:
                            curr = int(match.group(1))
                            status_text.text(f"Step 4/4: Designing slide {curr} of 8...")
                            progress_bar.progress(75 + int((curr/8)*20))
                    elif "Enviando Arquivos para o Google Drive" in line:
                        status_text.text("Saving reports and CSV files securely to Google Drive...")
                        progress_bar.progress(95)
                    elif "SUCCESS: Verification passed" in line:
                        status_text.text("Google Drive backups verified successfully!")
                        
                process.wait()
                stdout = "".join(stdout_acc)
                
                if process.returncode == 0:
                    status_text.text("🎉 Pipeline executed successfully!")
                    progress_bar.progress(100)
                    st.success("🎉 Analysis complete! Head over to the '📊 Current Session Results' tab to view your presentation and report.")
                    with st.expander("Show Execution Logs (Advanced Developer View)", expanded=False):
                        st.code(stdout, language="bash")
                else:
                    status_text.text("❌ Error executing pipeline.")
                    st.error(f"Error executing pipeline (Code: {process.returncode}). Check logs below.")
                    with st.expander("Show Execution Logs (Advanced Developer View)", expanded=True):
                        st.code(stdout, language="bash")
                    
            except Exception as e:
                st.error(f"Failed to execute pipeline script: {e}")
        finally:
            st.session_state.pipeline_running = False

with tab2:
    st.header("📊 Current Session Results")
    st.markdown("Interactive visualization of the sentiment analysis reports generated during your current browser session.")
    
    if not st.session_state.session_runs:
        st.info("No runs completed during this session yet. Go to the first tab to launch a new sentiment analysis!")
    else:
        # User select box showing only the current session's runs
        run_display_names = [r[0] for r in st.session_state.session_runs]
        run_mapping = {r[0]: r[1] for r in st.session_state.session_runs}
        
        selected_run_name = st.selectbox("Select Run to View:", options=run_display_names, index=len(run_display_names)-1)
        selected_run_id = run_mapping[selected_run_name]
        
        brand_path = os.path.join("outputs", selected_run_id)
        
        if os.path.exists(brand_path) and os.path.isdir(brand_path):
            # Add Drive link
            folder_id = config.get('Drive', 'folder_id', fallback=None)
            resource_key = config.get('Drive', 'resource_key', fallback=None)
            if folder_id:
                drive_url = f"https://drive.google.com/corp/drive/folders/{folder_id}"
                if resource_key:
                    drive_url += f"?resourcekey={resource_key}"
                st.markdown(f"📁 **[View all historical files for this project in Google Drive]({drive_url})**")
            
            try:
                # 1. Find and render HTML Deck
                deck_files = [f for f in os.listdir(brand_path) if f.endswith("_deck.html")]
                deck_file = os.path.join(brand_path, deck_files[0]) if deck_files else None
                
                if deck_file and os.path.exists(deck_file):
                    st.subheader("Presentation Slides (Use keyboard arrows)")
                    with open(deck_file, 'r', encoding='utf-8') as f:
                        deck_content = f.read()
                    import streamlit.components.v1 as components
                    components.html(deck_content, height=600, scrolling=True)
                    
                    pdf_files = [f for f in os.listdir(brand_path) if f.endswith("_presentation.pdf")]
                    pdf_file = os.path.join(brand_path, pdf_files[0]) if pdf_files else None
                    if pdf_file and os.path.exists(pdf_file):
                        with open(pdf_file, 'rb') as f:
                            pdf_data = f.read()
                        st.download_button(
                            label="Download Presentation PDF",
                            data=pdf_data,
                            file_name=os.path.basename(pdf_file),
                            mime='application/pdf',
                            key=f"sess_pdf_{selected_run_id}"
                        )
                else:
                    if st.session_state.pipeline_running and selected_run_id == st.session_state.current_run_id:
                        st.info("⏳ **Os slides estão sendo gerados pela IA...** (Esta etapa inicia após a colheita de vídeos e comentários e leva cerca de 1 a 2 minutos).")
                    else:
                        st.info("Interactive slide presentation not found.")
                
                st.markdown("---")
                
                # 2. Find and render HTML Report
                report_files = [f for f in os.listdir(brand_path) if f.endswith("_strategic_report.html")]
                report_file = os.path.join(brand_path, report_files[0]) if report_files else None
                
                if report_file and os.path.exists(report_file):
                    st.subheader("Strategic Report")
                    with open(report_file, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    import streamlit.components.v1 as components
                    components.html(html_content, height=800, scrolling=True)
                    
                    col_rep1, col_rep2 = st.columns(2)
                    with col_rep1:
                        st.download_button(
                            label="📥 Download HTML Report",
                            data=html_content,
                            file_name=os.path.basename(report_file),
                            mime='text/html',
                            key=f"sess_html_{selected_run_id}",
                            use_container_width=True
                        )
                    
                    md_files = [f for f in os.listdir(brand_path) if f.endswith("_strategic_report.md")]
                    if md_files:
                        md_path = os.path.join(brand_path, md_files[0])
                        with open(md_path, 'r', encoding='utf-8') as f:
                            md_content = f.read()
                        with col_rep2:
                            st.download_button(
                                label="📄 Download Markdown Report (.md)",
                                data=md_content,
                                file_name=os.path.basename(md_path),
                                mime='text/markdown',
                                key=f"sess_md_{selected_run_id}",
                                use_container_width=True
                            )
                else:
                    if st.session_state.pipeline_running and selected_run_id == st.session_state.current_run_id:
                        st.info("⏳ **O relatório estratégico está sendo redigido pela IA...**")
                    else:
                        st.info("Strategic report not found.")

                st.markdown("---")
                st.subheader("🎯 Video Curation & Relevance Audit")
                st.markdown("Review all discovered videos, AI relevance scores (0–100), content archetypes, and curation rationales.")

                # Locate discovered_videos.csv
                brand_name_base = selected_run_name.split(' - ')[0]
                safe_name = re.sub(r'\W+', '', brand_name_base.replace(' ', '_'))
                videos_csv_path = os.path.join(brand_path, f"{safe_name}_discovered_videos.csv")
                
                # Fallback to any *_discovered_videos.csv in the directory if exact name not found
                if not os.path.exists(videos_csv_path):
                    v_files = [f for f in os.listdir(brand_path) if f.endswith("_discovered_videos.csv")]
                    if v_files:
                        videos_csv_path = os.path.join(brand_path, v_files[0])

                if os.path.exists(videos_csv_path):
                    import pandas as pd
                    try:
                        df_discovered = pd.read_csv(videos_csv_path)
                        if df_discovered.empty:
                            st.warning("⚠️ No videos met the strict campaign relevance criteria (threshold >= 70). Try broadening search queries or lowering the relevance threshold in the setup tab.")
                        else:
                            # Map and select required columns: Title, Channel, Views, Relevance Score, Content Archetype, Reason
                            col_mapping = {
                                'title': 'Title',
                                'channel': 'Channel',
                                'views': 'Views',
                                'relevance_score': 'Relevance Score',
                                'content_archetype': 'Content Archetype',
                                'relevance_reason': 'Reason'
                            }
                            # Ensure columns exist
                            for k in col_mapping.keys():
                                if k not in df_discovered.columns:
                                    df_discovered[k] = 0 if k in ['views', 'relevance_score'] else 'N/A'
                            
                            display_df = df_discovered[list(col_mapping.keys())].rename(columns=col_mapping)
                            
                            # Summary metrics
                            col_m1, col_m2 = st.columns(2)
                            with col_m1:
                                st.metric("Total Curated Videos", len(df_discovered))
                            with col_m2:
                                avg_score = df_discovered['relevance_score'].mean() if not df_discovered['relevance_score'].empty else 0
                                st.metric("Average Relevance Score", f"{avg_score:.1f} / 100")
                            
                            st.dataframe(
                                display_df,
                                use_container_width=True,
                                column_config={
                                    "Relevance Score": st.column_config.ProgressColumn(
                                        "Relevance Score",
                                        help="AI Semantic Relevance Score (0-100)",
                                        format="%d",
                                        min_value=0,
                                        max_value=100,
                                    ),
                                    "Views": st.column_config.NumberColumn(
                                        "Views",
                                        format="%d",
                                    ),
                                },
                                hide_index=True
                            )
                    except Exception as e:
                        st.error(f"Error loading discovered videos table: {e}")
                else:
                    if st.session_state.pipeline_running and selected_run_id == st.session_state.current_run_id:
                        st.info("⏳ **Os vídeos estão sendo descobertos e avaliados pela IA...**")
                    else:
                        st.info("Discovered videos dataset not found.")

                st.markdown("---")
                st.subheader("📁 Input Files & Raw Datasets")
                st.markdown("Download the raw YouTube video metadata (CSV), audience comments dataset (CSV), and formatted markdown files that were harvested and used as inputs to generate the strategic report and presentation slides.")
                
                if st.button("📥 Download Input Files & Datasets", key=f"nlm_btn_{selected_run_id}", use_container_width=True):
                    from notebooklm_exporter import NotebookLMExporter
                    exporter = NotebookLMExporter()
                    exporter.output_dir = brand_path
                    exporter.brand_name = selected_run_name.split(' - ')[0]
                    exporter.safe_brand_name = re.sub(r'\W+', '', exporter.brand_name.replace(' ', '_'))
                    exporter.report_html_path = report_file or ""
                    exporter.videos_csv_path = os.path.join(brand_path, f"{exporter.safe_brand_name}_discovered_videos.csv")
                    exporter.comments_csv_path = os.path.join(brand_path, f"{exporter.safe_brand_name}_raw_comments.csv")
                    
                    sources = exporter.prepare_sources()
                    if sources:
                        st.session_state[f"nlm_sources_{selected_run_id}"] = sources
                        st.success(f"Successfully prepared {len(sources)} Input Files & Datasets!")
                    else:
                        st.warning("No output files found in this run directory.")

                if f"nlm_sources_{selected_run_id}" in st.session_state:
                    sources = st.session_state[f"nlm_sources_{selected_run_id}"]
                    for s in sources:
                        col_s1, col_s2 = st.columns([3, 1])
                        with col_s1:
                            st.write(f"📄 **{s['title']}** (`{len(s['content'])}` chars)")
                        with col_s2:
                            st.download_button(
                                label=f"📥 Download File",
                                data=s['content'],
                                file_name=f"{re.sub(r'\\W+', '_', s['title'])}.md",
                                mime="text/markdown",
                                key=f"dl_nlm_{re.sub(r'\\W+', '_', s['title'])}_{selected_run_id}"
                            )
                    
            except Exception as e:
                st.error(f"Error loading visualizations: {e}")
        else:
            st.error(f"Output files for this run were not found locally (Run ID: {selected_run_id}).")

with tab3:
    st.header("☁️ Historical Reports (Google Drive)")
    st.markdown("Retrieve and view historical analyses saved securely in your company's Google Drive folder.")
    
    # Read config for Drive
    folder_id = os.getenv('DRIVE_FOLDER_ID', config.get('Drive', 'folder_id', fallback=None))
    resource_key = os.getenv('DRIVE_RESOURCE_KEY', config.get('Drive', 'resource_key', fallback=None))
    
    @st.cache_data(ttl=3600)
    def fetch_folders(fid, rkey):
        if not fid:
            return []
        return list_folders_in_drive(fid, resource_key=rkey)
        
    col_dd, col_ref = st.columns([3, 1])
    
    with col_ref:
        if st.button("🔄 Refresh Drive List"):
            st.cache_data.clear()
            
    folders = fetch_folders(folder_id, resource_key)
        
    options = ["Select a historical topic..."]
    mapping = {}
    
    for f in folders:
        name = f['name']
        import re
        match = re.search(r'(.*)_(\d{8})_(\d{6})', name)
        if match:
            topic = match.group(1).replace('_', ' ')
            date_str = match.group(2)
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            display_name = f"{topic} - {formatted_date}"
        else:
            display_name = name.replace('_', ' ')
            
        options.append(display_name)
        mapping[display_name] = f['id']
        
    with col_dd:
        selected_option = st.selectbox("Available Decks in Drive:", options=options)
        
    if selected_option != "Select a historical topic...":
        selected_id = mapping[selected_option]
        
        # Create tabs for PDF and Strategic Report
        drive_pdf_tab, drive_report_tab = st.tabs(["📊 Presentation PDF", "📄 Strategic Report HTML"])
        
        with drive_pdf_tab:
            st.info(f"Downloading PDF for: {selected_option}...")
            # Find PDF in folder
            pdf_info = find_pdf_in_folder(selected_id, resource_key=resource_key)
            if pdf_info:
                pdf_id = pdf_info['id']
                pdf_name = pdf_info['name']
                
                # Download PDF bytes
                pdf_bytes = download_file_from_drive(pdf_id, resource_key=resource_key)
                
                if pdf_bytes:
                    # Display PDF using base64 in iframe
                    import base64
                    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    
                    # Also provide download button
                    st.download_button(
                        label="Download Presentation PDF",
                        data=pdf_bytes,
                        file_name=pdf_name,
                        mime='application/pdf',
                        key=f"drive_pdf_{pdf_id}"
                    )
                else:
                    st.error("Failed to download PDF content from Drive.")
            else:
                st.warning("No PDF presentation found in this folder on Drive.")
                
        with drive_report_tab:
            st.info(f"Downloading Strategic Report for: {selected_option}...")
            # Find HTML report in folder
            report_info = find_file_by_name_in_folder(selected_id, "strategic_report", resource_key=resource_key)
            if report_info:
                report_id = report_info['id']
                report_name = report_info['name']
                
                # Download HTML bytes
                report_bytes = download_file_from_drive(report_id, resource_key=resource_key)
                
                if report_bytes:
                    # Decode and render the HTML report
                    html_content = report_bytes.decode('utf-8', errors='replace')
                    import streamlit.components.v1 as components
                    components.html(html_content, height=600, scrolling=True)
                    
                    # Provide download button
                    st.download_button(
                        label="Download Strategic Report HTML",
                        data=html_content,
                        file_name=report_name,
                        mime='text/html',
                        key=f"drive_html_{report_id}"
                    )
                else:
                    st.error("Failed to download Strategic Report HTML from Drive.")
            else:
                st.warning("No Strategic Report HTML found in this folder on Drive.")
                
    st.markdown("---")
