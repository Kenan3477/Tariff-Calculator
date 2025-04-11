
import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import matplotlib.pyplot as plt
import requests
import os

st.set_page_config(page_title="Steel Tariff Estimator", page_icon="🔩", layout="centered")

# Use /tmp for user storage on Streamlit Cloud
USER_DB = "/tmp/users.csv"
if not os.path.exists(USER_DB):
    df_users = pd.DataFrame([{
        "name": "Kenan Davies",
        "username": "kenan",
        "password": "admin123"
    }])
    df_users.to_csv(USER_DB, index=False)
else:
    df_users = pd.read_csv(USER_DB)

# --- Registration Form ---
with st.sidebar.expander("📝 Register New Account"):
    with st.form("register_form"):
        new_name = st.text_input("Full Name")
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        register = st.form_submit_button("Register")
        if register:
            if new_username in df_users["username"].values:
                st.warning("❗ Username already exists.")
            elif not new_name or not new_username or not new_password:
                st.warning("Please fill in all fields.")
            else:
                new_user = pd.DataFrame([{
                    "name": new_name,
                    "username": new_username,
                    "password": new_password
                }])
                new_user.to_csv(USER_DB, mode="a", header=False, index=False)
                st.success("✅ Registered! Please log in using your new credentials.")

# Load and validate users
df_users = pd.read_csv(USER_DB)
valid_users = df_users.dropna(subset=["password"])
names = valid_users["name"].tolist()
usernames = valid_users["username"].tolist()
passwords = valid_users["password"].tolist()
hashed_passwords = stauth.Hasher(passwords).generate()

credentials = {
    "usernames": {
        usernames[i]: {
            "name": names[i],
            "password": hashed_passwords[i]
        } for i in range(len(usernames))
    }
}

authenticator = stauth.Authenticate(credentials, "tariff_auth", "tariff_cookie", cookie_expiry_days=30)

name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"Welcome {name} 👋")

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

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Download Results as CSV",
            data=csv,
            file_name="steel_landed_costs_calculated.csv",
            mime="text/csv",
        )
    else:
        st.info("👆 Upload your CSV above to get started.")

elif authentication_status is False:
    st.error("Incorrect username or password.")
elif authentication_status is None:
    st.warning("Please enter your username and password.")
