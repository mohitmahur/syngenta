import pandas as pd
import os

# Update to go up two folder levels (../../) from backend to reach the root folder
file_path = '../../Syngenta_IITM_Hackathon_2026_dataset/growers.csv'

try:
    df = pd.read_csv(file_path)
    unique_values = df['district'].unique()

    print(f"✅ Successfully loaded {len(df)} grower profiles.")
    print("\n📍 Unique Districts in Dataset:")
    print(unique_values)

except FileNotFoundError:
    print(f"❌ Error: Could not locate the dataset file at '{file_path}'.")