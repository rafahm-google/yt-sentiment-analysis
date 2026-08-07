import os
import json
import pandas as pd
import configparser
from dotenv import load_dotenv

class NotebookLMExporter:
    """
    Exports sentiment analysis outputs (Discovered Videos CSV, Raw Comments CSV,
    and Strategic Report HTML/Markdown) into a NotebookLM notebook.
    """
    def __init__(self, config_path=None):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if config_path is None:
            config_path = os.path.join(self.project_root, 'config.ini')
        
        self.config_path = config_path
        self._load_configuration()

    def _load_configuration(self):
        config = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            config.read(self.config_path)
            
        self.brand_name = config.get('Crawler', 'search_terms', fallback='Analysis_Topic')
        self.safe_brand_name = self.brand_name.replace(' ', '_')
        run_id = config.get('General', 'run_id', fallback=self.safe_brand_name)
        self.output_dir = os.path.join(self.project_root, 'outputs', run_id)
        
        self.videos_csv_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_discovered_videos.csv")
        self.comments_csv_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_raw_comments.csv")
        self.report_html_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_strategic_report.html")

    def prepare_sources(self):
        """
        Prepares structured text/markdown representations of the CSV datasets and HTML report
        suitable for NotebookLM source ingestion.
        """
        sources = []

        # 1. Strategic Report Source (Prioritize clean Markdown file)
        md_report_path = self.report_html_path.replace('.html', '.md') if self.report_html_path.endswith('.html') else self.report_html_path + '.md'
        
        if os.path.exists(md_report_path):
            with open(md_report_path, 'r', encoding='utf-8') as f:
                report_content = f.read()
            sources.append({
                "title": f"Strategic Report - {self.brand_name}",
                "content": report_content,
                "mime_type": "text/markdown"
            })
        elif os.path.exists(self.report_html_path):
            with open(self.report_html_path, 'r', encoding='utf-8') as f:
                html_raw = f.read()
            # Strip template CSS/HTML tags if falling back to HTML file
            clean_text = re.sub(r'<style.*?>.*?</style>', '', html_raw, flags=re.DOTALL)
            clean_text = re.sub(r'<script.*?>.*?</script>', '', clean_text, flags=re.DOTALL)
            clean_text = re.sub(r'<[^>]+>', '', clean_text)
            clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text).strip()
            sources.append({
                "title": f"Strategic Report - {self.brand_name}",
                "content": clean_text,
                "mime_type": "text/markdown"
            })

        # 2. Discovered Videos CSV Source
        if os.path.exists(self.videos_csv_path):
            try:
                videos_df = pd.read_csv(self.videos_csv_path)
                # Convert top video metadata to clean markdown summary
                video_md = f"# Discovered YouTube Videos for {self.brand_name}\n\n"
                video_md += f"Total Videos: {len(videos_df)}\n\n"
                cols_to_include = [c for c in ['title', 'channel_title', 'view_count', 'like_count', 'comment_count', 'video_url', 'published_at'] if c in videos_df.columns]
                video_md += videos_df[cols_to_include].to_markdown(index=False)
                
                sources.append({
                    "title": f"Discovered Videos Dataset - {self.brand_name}",
                    "content": video_md,
                    "mime_type": "text/markdown"
                })
            except Exception as e:
                print(f"Error parsing videos CSV for NotebookLM: {e}")

        # 3. Raw Comments CSV Source
        if os.path.exists(self.comments_csv_path):
            try:
                comments_df = pd.read_csv(self.comments_csv_path)
                comments_md = f"# Audience Comments Dataset for {self.brand_name}\n\n"
                comments_md += f"Total Comments: {len(comments_df)}\n\n"
                
                cols = [c for c in ['video_title', 'author', 'comment_text', 'like_count', 'published_at'] if c in comments_df.columns]
                # Process top comments in chunks/sample to stay concise
                sample_comments = comments_df[cols].head(200)
                
                for idx, row in sample_comments.iterrows():
                    v_title = row.get('video_title', 'Video')
                    author = row.get('author', 'User')
                    text = row.get('comment_text', '')
                    likes = row.get('like_count', 0)
                    comments_md += f"- **[{v_title}] {author}** ({likes} likes): {text}\n"
                    
                sources.append({
                    "title": f"Audience Comments Sample - {self.brand_name}",
                    "content": comments_md,
                    "mime_type": "text/markdown"
                })
            except Exception as e:
                print(f"Error parsing comments CSV for NotebookLM: {e}")

        return sources

    def export_via_api(self):
        """
        Creates a NotebookLM notebook via API and uploads all sources, returning the direct NotebookLM URL.
        """
        sources = self.prepare_sources()
        if not sources:
            return None, "No source files found to export."

        notebook_title = f"YouTube Sentiment Analysis: {self.brand_name}"
        
        try:
            from notebooklm import NotebookLMClient
            from notebooklm.auth import load_auth_from_storage
            load_dotenv()
            
            auth_tokens = None
            try:
                tokens_data = load_auth_from_storage()
                if tokens_data:
                    from notebooklm.auth import AuthTokens
                    auth_tokens = AuthTokens(**tokens_data) if isinstance(tokens_data, dict) else tokens_data
            except Exception as e_auth:
                print(f"Auth storage load note: {e_auth}")
                
            if not auth_tokens:
                return None, "NotebookLM auth tokens not configured. Please use the Download Bundle option to import into NotebookLM Web!"

            client = NotebookLMClient(auth=auth_tokens)
            nb = client.notebooks.create(title=notebook_title)
            nb_id = nb.id if hasattr(nb, 'id') else str(nb)
            clean_id = nb_id.replace('notebooks/', '')
            url = f"https://notebooklm.google.com/notebook/{clean_id}"
            
            for s in sources:
                try:
                    client.sources.add_text(
                        notebook_id=nb_id,
                        title=s['title'],
                        content=s['content']
                    )
                except Exception as e_src:
                    print(f"Error adding source {s['title']}: {e_src}")
                    
            return url, f"Successfully created NotebookLM notebook with {len(sources)} sources!"
        except Exception as e:
            print(f"API direct export exception: {e}")
            return None, f"NotebookLM API auth required. Use the Download Bundle option below!"

if __name__ == "__main__":
    exporter = NotebookLMExporter()
    prepared = exporter.prepare_sources()
    print(f"Successfully prepared {len(prepared)} NotebookLM sources:")
    for s in prepared:
        print(f"- {s['title']} ({len(s['content'])} characters)")
