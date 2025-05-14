
import streamlit as st
import pandas as pd
import requests
import time
import io

# CONFIGURATION
APIFY_TOKEN = "your_apify_api_token_here"  # Replace with your real token
ACTOR_ID = "vmf6h5lxPAkB1W2gT"  # Your Apify skip trace actor ID

st.title("📦 Automated Owner Skip Tracer via Apify")
st.markdown("Upload your raw or preprocessed CSV file. We'll extract Owner 1 and mailing address, clean it, and run skip tracing.")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    st.success("File uploaded and read successfully.")

    # Intelligent owner promotion if OWNER 1 fields are missing
    if 'OWNER 1 FIRST NAME' not in raw_df.columns:
        # Promote next available owner block (e.g., OWNER 2 → OWNER 1, OWNER 3 → OWNER 2, etc.)
        owner_cols = [col for col in raw_df.columns if col.startswith("OWNER")]
        owner_blocks = sorted(set(col.split()[1] for col in owner_cols))
        if len(owner_blocks) >= 2:
            next_owner = owner_blocks[0]  # e.g., "2"
            new_owner_map = {}
            for col in owner_cols:
                parts = col.split()
                if parts[1] == next_owner:
                    new_col = col.replace(f"OWNER {next_owner}", "OWNER 1")
                    new_owner_map[col] = new_col
                else:
                    new_idx = str(int(parts[1]) - 1)
                    new_col = col.replace(f"OWNER {parts[1]}", f"OWNER {new_idx}")
                    new_owner_map[col] = new_col
            raw_df = raw_df.rename(columns=new_owner_map)
            # Drop previous OWNER 1 (now shifted into OWNER 0)
            raw_df = raw_df[[col for col in raw_df.columns if not col.startswith("OWNER 0")]]
        else:
            st.error("No OWNER 1 or promotable OWNER 2+ found.")
            st.stop()

    # Preview original or promoted file
    if st.checkbox("Preview processed file"):
        st.dataframe(raw_df.head())

    # Extract required fields for skip tracing
    try:
        cleaned_df = pd.DataFrame({
            'firstName': raw_df['OWNER 1 FIRST NAME'].fillna('').astype(str).str.title(),
            'lastName': raw_df['OWNER 1 LAST NAME'].fillna('').astype(str).str.title(),
            'address': raw_df['MAILING ADDRESS LINE 1'].fillna('').astype(str),
            'city': raw_df['MAILING CITY'].fillna('').astype(str),
            'state': raw_df['MAILING STATE'].fillna('').astype(str),
            'zip': raw_df['MAILING ZIP CODE'].fillna('').astype(str)
        })
    except KeyError as e:
        st.error(f"Missing expected column in CSV: {e}")
        st.stop()

    st.subheader("🧹 Cleaned Skip Trace Input")
    st.dataframe(cleaned_df.head())

    if st.button("🚀 Run Skip Trace with Apify"):
        # Convert to CSV for upload
        csv_bytes = cleaned_df.to_csv(index=False).encode("utf-8")

        # Step 1: Create a temporary key-value store to upload input file
        store_res = requests.post(f"https://api.apify.com/v2/key-value-stores?token={APIFY_TOKEN}").json()
        store_id = store_res['data']['id']

        # Step 2: Upload input file
        upload_url = f"https://api.apify.com/v2/key-value-stores/{store_id}/records/INPUT.csv?token={APIFY_TOKEN}&contentType=text/csv"
        requests.put(upload_url, data=csv_bytes)

        # Step 3: Start the actor
        run_res = requests.post(
            f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={APIFY_TOKEN}",
            json={"input": {"csvUrl": f"https://api.apify.com/v2/key-value-stores/{store_id}/records/INPUT.csv?token={APIFY_TOKEN}"}}
        ).json()

        run_id = run_res['data']['id']
        st.info("Skip trace started. Polling for results...")

        # Step 4: Poll for run status
        status = "RUNNING"
        while status in ["RUNNING", "READY", "PENDING"]:
            time.sleep(5)
            poll = requests.get(f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}").json()
            status = poll['data']['status']
            st.write(f"Status: {status}")

        # Step 5: Get results dataset
        dataset_id = poll['data']['defaultDatasetId']
        result_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=csv&clean=true&token={APIFY_TOKEN}"
        result_df = pd.read_csv(result_url)

        st.success("✅ Skip trace complete!")
        st.dataframe(result_df.head())

        # Download button
        st.download_button("Download Results CSV", data=result_df.to_csv(index=False), file_name="skiptrace_results.csv")

        # Step 6: Create remaining_owners.csv
        remaining_cols = [col for col in raw_df.columns if not col.startswith("OWNER 1")]
        remaining_df = raw_df[remaining_cols]
        st.download_button("Download Remaining Owners CSV", data=remaining_df.to_csv(index=False), file_name="remaining_owners.csv")
