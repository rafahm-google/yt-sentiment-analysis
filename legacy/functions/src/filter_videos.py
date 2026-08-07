import pandas as pd
import os
import re

brand_name = "copa do mundo"
safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
video_dir = os.path.join('outputs', safe_brand_name, 'video')
csv_path = os.path.join('outputs', safe_brand_name, f"{safe_brand_name}_discovered_videos.csv")

# Get list of downloaded video IDs (without extension)
downloaded_ids = [f.replace('.mp4', '') for f in os.listdir(video_dir) if f.endswith('.mp4')]

print(f"Found {len(downloaded_ids)} downloaded videos.")

# Read the original CSV
df = pd.read_csv(csv_path)
original_count = len(df)

# Filter the DataFrame
filtered_df = df[df['video_id'].isin(downloaded_ids)]

print(f"Filtered from {original_count} to {len(filtered_df)} videos.")

# Save the filtered CSV back
filtered_df.to_csv(csv_path, index=False)
print(f"Updated {csv_path}")
