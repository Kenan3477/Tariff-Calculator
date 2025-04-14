
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests

st.set_page_config(page_title="Steel Tariff Estimator", page_icon="🔩", layout="centered")

st.title("🔩 Steel Landed Cost Estimator")

st.markdown("""
📄 **Download the input CSV template:**
[Click here to download](https://raw.githubusercontent.com/Kenan3477/Tariff-Calculator/main/Steel_Upload_Template.csv)
""")

try:
    tariff_df = pd.read_csv("tariff_rates.csv")
except:
    tariff_df = pd.DataFrame(columns=["HTS Code", "Country of Origin", "Tariff Rate (%)"])

@st.cache_data(show_spinner=False)
def query_uk_tariff_api(hts_code):
    try:
        url = f"https://www.trade-tariff.service.gov.uk/api/v2/commodities/{hts_code}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for measure in data.get("included", []):
                if measure.get("type") == "measure" and measure.get("attributes", {}).get("duty_expression", {}).get("formatted"):
                    rate = measure["attributes"]["duty_expression"]["formatted"].replace("%", "").strip()
                    return float(rate)
    except:
        pass
    return None

def normalize_quantity(row):
    if row["Unit"].lower() == "tonnes":
        return row["Quantity"] * 1000
    return row["Quantity"]

def get_tariff_rate(hts, country):
    rate = query_uk_tariff_api(hts)
    if rate is not None:
        return rate
    match = tariff_df[(tariff_df["HTS Code"] == hts) & (tariff_df["Country of Origin"].str.lower() == country.lower())]
    if not match.empty:
        return match.iloc[0]["Tariff Rate (%)"]
    return 0

alternatives = {
    "Flat-rolled coil": [
        {"Country": "Vietnam", "Tariff": 15, "Supplier": "VN Steel Co", "URL": "https://vnsteelco.vn"},
        {"Country": "Turkey", "Tariff": 18, "Supplier": "Ankara Metals", "URL": "https://ankarametals.com"}
    ],
    "Galvanized steel": [
        {"Country": "India", "Tariff": 12, "Supplier": "Tata Steel", "URL": "https://www.tatasteel.com"},
        {"Country": "Brazil", "Tariff": 20, "Supplier": "CSN Brazil", "URL": "https://www.csn.com.br"}
    ]
}

uploaded_file = st.file_uploader("Upload your CSV file", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    df["Normalized Quantity (kg)"] = df.apply(normalize_quantity, axis=1)

    if "Tariff Rate (%)" not in df.columns:
        df["Tariff Rate (%)"] = df.apply(lambda row: get_tariff_rate(row["HTS Code"], row["Country of Origin"]), axis=1)
    else:
        df["Tariff Rate (%)"] = df.apply(
            lambda row: row["Tariff Rate (%)"] if pd.notna(row["Tariff Rate (%)"]) else get_tariff_rate(row["HTS Code"], row["Country of Origin"]),
            axis=1
        )

    df["Base Cost (£)"] = df["Normalized Quantity (kg)"] * df["Unit Value (£)"]
    df["Tariff Amount (£)"] = df["Tariff Rate (%)"] / 100 * df["Base Cost (£)"]
    df["Landed Cost (£)"] = df["Base Cost (£)"] + df["Tariff Amount (£)"] + df["Shipping Cost (£)"]

    st.success("Calculation complete!")
    st.dataframe(df)

    st.markdown("### 📊 Cost Breakdown per Product")
    for idx, row in df.iterrows():
        labels = ["Base Cost", "Tariff", "Shipping"]
        sizes = [row["Base Cost (£)"], row["Tariff Amount (£)"], row["Shipping Cost (£)"]]
        fig, ax = plt.subplots()
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
        ax.axis('equal')
        st.markdown(f"**{row['Product Type']} from {row['Country of Origin']}**")
        st.pyplot(fig)

        alt_sources = alternatives.get(row["Product Type"])
        if alt_sources:
            current_tariff = row["Tariff Rate (%)"]
            sorted_alts = sorted(alt_sources, key=lambda x: x["Tariff"])
            lowest_tariff = sorted_alts[0]["Tariff"]
            st.markdown("**💡 Alternative sources with potential savings:**")
            for alt in sorted_alts:
                savings = max(0, (current_tariff - alt["Tariff"]) / 100 * row["Base Cost (£)"])
                flag = "🌟 Recommended" if alt["Tariff"] == lowest_tariff else ""
                st.markdown(
                    f"- [{alt['Supplier']}]({alt['URL']}) from {alt['Country']} → {alt['Tariff']}% tariff {flag}"
                    + (f" → 💰 Savings: £{savings:,.2f}" if savings > 0 else "")
                )
                    savings = (current_tariff - alt["Tariff"]) / 100 * row["Base Cost (£)"]
                    st.markdown(
                        f"- [{alt['Supplier']}]({alt['URL']}) from {alt['Country']} → {alt['Tariff']}% tariff → 💰 Savings: £{savings:,.2f}"
                    )

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="💾 Download Results as CSV",
        data=csv,
        file_name="steel_landed_costs_calculated.csv",
        mime="text/csv",
    )
else:
    st.info("👆 Upload your CSV above to get started.")
