import os
import sys
import re
import json
import time
import glob
import pandas as pd
import traceback
from googleapiclient.errors import HttpError

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from crawler import YouTubeBrandCrawler

BRANDS = [
    "Creed", "Maison Francis Kurkdjian", "Le Labo", "Byredo", "Diptyque", 
    "Frederic Malle", "Amouage", "Xerjoff", "Parfums de Marly", "Initio Parfums Privés", 
    "Nishane", "Kilian Paris", "Roja Parfums", "Clive Christian", "Penhaligon’s", 
    "Serge Lutens", "Memo Paris", "Maison Crivelli", "BDK Parfums", "Ex Nihilo", 
    "Vilhelm Parfumerie", "Essential Parfums", "Orto Parisi", "Nasomatto", "Tiziana Terenzi", 
    "Mancera", "Montale", "The House of Oud", "Floraïku", "Liquides Imaginaires", 
    "Juliette Has a Gun", "Histoires de Parfums", "L’Artisan Parfumeur", "Atelier Cologne", 
    "Acqua di Parma", "Profumum Roma", "Carner Barcelona", "Fueguia 1833", "Fragrance du Bois", 
    "Stephane Humbert Lucas", "Mind Games", "Bond No. 9", "Widian", "Gritti", 
    "Electimuss", "Argos", "Thameen", "The Harmonist", "Masque Milano", "Jusbox", 
    "Une Nuit Nomade", "Goldfield & Banks", "Heeley", "Imaginary Authors", "Zoologist", 
    "Maison Mataha", "Giardini di Toscana", "D.S. & Durga", "Aesop", "Comme des Garçons Parfums", 
    "Escentric Molecules", "Laboratorio Olfattivo", "Lorenzo Pazzaglia", "Pierre Guillaume Paris", 
    "Jovoy Paris", "Les Indémodables", "Mizensir", "Obvious Parfums", "Gallivant", 
    "Hiram Green", "Frapin", "Papillon Artisan Perfumes", "Bogue Perfumo", "Francesca Bianchi", 
    "Etat Libre d’Orange", "Santa Maria Novella", "Floris", "Trudon", "Eight & Bob", 
    "Ramón Monegal", "Arquiste", "Régime des Fleurs", "Abel", "Matière Première", 
    "Maison Tahité", "Fugazzi", "Bohoboco", "Courrèges", "Dries Van Noten Parfums", 
    "Loewe Perfumes", "Celine Haute Parfumerie", "Louis Vuitton Parfums", "Dior Privée", 
    "Chanel Les Exclusifs", "Armani Privé", "Hermès Hermessence", "Tom Ford Private Blend", 
    "YSL Le Vestiaire des Parfums", "Guerlain L’Art & La Matière", "Cartier Les Heures de Parfum"
]

MODIFIERS = [
    "blind buy", "decant", "decants", "perfume assinatura", "fixação e projeção", 
    "projeção", "silagem", "rastro", "renda elogios", "rende elogios", "bomba", 
    "desempenho", "de nicho", "perfume de nicho", "alta perfumaria", "indie", 
    "exclusivo", "perfume árabe", "árabe", "compartilhável", "unissex", 
    "unboxing", "coleção", "top 10", "top 5", "primeiras impressões", "oud", "gourmand",
    "Baccarat Rouge", "Baccarat Rouge 540", "Aventus", "Erba Pura", "Delina", 
    "Santal 33", "Layton", "Naxos", "Club de Nuit", "Khamrah", "Asad"
]

def clean_invalid_caches():
    print("Cleaning empty caches to prevent skipped searches...")
    # 1. Clean local empty caches
    local_caches = glob.glob("outputs/perfume_crawl_batch/*/search_cache.json")
    for path in local_caches:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not data: # Empty list
                print(f"  Removing empty local cache: {path}")
                os.remove(path)
        except Exception:
            pass
            
    # 2. Clean global empty caches
    global_caches = glob.glob("outputs/cache/youtube_queries/*.json")
    for path in global_caches:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not data: # Empty list
                print(f"  Removing empty global cache: {path}")
                os.remove(path)
        except Exception:
            pass

def run_batch_robust():
    clean_invalid_caches()
    
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    try:
        crawler = YouTubeBrandCrawler(config_path=config_path)
    except Exception as e:
        print(f"Failed to initialize crawler: {e}")
        traceback.print_exc()
        return

    crawler.search_modifiers = MODIFIERS
    print(f"Using {len(MODIFIERS)} search modifiers.")
    
    results_summary = []
    quota_exceeded = False

    run_id = "perfume_crawl_batch"
    base_output_dir = os.path.join('outputs', run_id)
    os.makedirs(base_output_dir, exist_ok=True)

    print(f"\nStarting batch crawl for {len(BRANDS)} brands...")
    
    for idx, brand in enumerate(BRANDS):
        print(f"\n[{idx+1}/{len(BRANDS)}] Brand: {brand}")
        
        safe_brand_name = re.sub(r'\W+', '', brand.replace(' ', '_'))
        crawler.search_terms = brand
        crawler.output_dir = os.path.join(base_output_dir, safe_brand_name)
        crawler.output_path = os.path.join(crawler.output_dir, f"{safe_brand_name}_discovered_videos.csv")
        os.makedirs(crawler.output_dir, exist_ok=True)

        # Sleep to respect YouTube API rate limits
        time.sleep(4) 
        
        max_retries = 3
        retry_delay = 15 # initial delay in seconds
        
        for attempt in range(max_retries + 1):
            try:
                crawler.run_crawler()
                
                # Load results to summarize
                if os.path.exists(crawler.output_path):
                    df = pd.read_csv(crawler.output_path)
                    num_videos = len(df)
                    if num_videos > 0:
                        top_video = df.iloc[0]
                        results_summary.append({
                            "Brand": brand,
                            "Status": "Success",
                            "Videos Found": num_videos,
                            "Top Video": top_video['title'],
                            "Top Video Views": top_video['views'],
                            "Top Video URL": top_video['url']
                        })
                    else:
                        results_summary.append({
                            "Brand": brand,
                            "Status": "No videos found after filters",
                            "Videos Found": 0,
                            "Top Video": "N/A",
                            "Top Video Views": 0,
                            "Top Video URL": "N/A"
                        })
                else:
                    results_summary.append({
                        "Brand": brand,
                        "Status": "No output file generated",
                        "Videos Found": 0,
                        "Top Video": "N/A",
                        "Top Video Views": 0,
                        "Top Video URL": "N/A"
                    })
                break # Success! Break retry loop.
                
            except HttpError as e:
                print(f"  [Attempt {attempt+1}/{max_retries+1}] HTTP Error for {brand}: {e.resp.status}")
                
                # Rate limit / Too many requests
                if e.resp.status in [403, 429]:
                    content_str = e.content.decode('utf-8')
                    
                    if "quotaExceeded" in content_str:
                        print("\nCRITICAL: YouTube API Quota Exceeded! Stopping crawl.")
                        quota_exceeded = True
                        results_summary.append({
                            "Brand": brand,
                            "Status": "Quota Exceeded",
                            "Videos Found": 0,
                            "Top Video": "N/A",
                            "Top Video Views": 0,
                            "Top Video URL": "N/A"
                        })
                        break # Break the attempt loop and we will handle the outer stop
                        
                    elif "rateLimitExceeded" in content_str:
                        if attempt < max_retries:
                            sleep_time = retry_delay * (2 ** attempt)
                            print(f"  Rate limit hit. Sleeping for {sleep_time}s before retry...")
                            time.sleep(sleep_time)
                            continue
                        else:
                            print("  Max retries reached for rate limit. Skipping brand.")
                            results_summary.append({
                                "Brand": brand,
                                "Status": "Rate Limit Exceeded (Max Retries)",
                                "Videos Found": 0,
                                "Top Video": "N/A",
                                "Top Video Views": 0,
                                "Top Video URL": "N/A"
                            })
                    else:
                        # Other 403/429 errors
                        results_summary.append({
                            "Brand": brand,
                            "Status": f"HTTP Error: {e.resp.status}",
                            "Videos Found": 0,
                            "Top Video": "N/A",
                            "Top Video Views": 0,
                            "Top Video URL": "N/A"
                        })
                        break
                else:
                    results_summary.append({
                        "Brand": brand,
                        "Status": f"HTTP Error: {e.resp.status}",
                        "Videos Found": 0,
                        "Top Video": "N/A",
                        "Top Video Views": 0,
                        "Top Video URL": "N/A"
                    })
                    break
                    
            except Exception as e:
                print(f"  [Attempt {attempt+1}/{max_retries+1}] Unexpected error for {brand}: {e}")
                results_summary.append({
                    "Brand": brand,
                    "Status": f"Error: {type(e).__name__}",
                    "Videos Found": 0,
                    "Top Video": "N/A",
                    "Top Video Views": 0,
                    "Top Video URL": "N/A"
                })
                break
                
        if quota_exceeded:
            break
            
    # Print final results
    print("\n" + "="*80)
    print(" CRAWL RESULTS SUMMARY ")
    print("="*80)
    
    summary_df = pd.DataFrame(results_summary)
    print(summary_df.to_string(index=False))
    
    summary_path = os.path.join(base_output_dir, "batch_crawl_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSummary saved to {summary_path}")
    
    if quota_exceeded:
        print("\nWarning: Batch crawl was interrupted because the YouTube API quota was exceeded.")
        print("Consider running again tomorrow or using a different API key.")

if __name__ == "__main__":
    run_batch_robust()
