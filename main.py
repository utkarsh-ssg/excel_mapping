import streamlit as st
import pandas as pd
import google.generativeai as genai
import ast
import re
from io import BytesIO
import os


genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash")

st.title("AI Agent for Column Matcher")

uploaded_x1 = st.file_uploader("Upload Reference Excel (X1)", type=["xlsx"])
uploaded_x2 = st.file_uploader("Upload Excel to Map (X2)", type=["xlsx"])

if uploaded_x1 and uploaded_x2:
    df_x1 = pd.read_excel(uploaded_x1)
    df_x2 = pd.read_excel(uploaded_x2)

    st.subheader("Preview: X1 (Reference Format)")
    st.dataframe(df_x1.head())

    st.subheader("Preview: X2 (To Map Format)")
    st.dataframe(df_x2.head())

    if st.button("Map Columns and Generate Output"):
        prompt = f"""
        You are given two Excel files with different column headers.

        The columns from File X1 (reference format) are:
        {list(df_x1.columns)}

        The columns from File X2 (to be mapped) are:
        {list(df_x2.columns)}

        Your task is to return a Python dictionary where:
        - Each key is a column from X1.
        - Each value is the **most semantically similar** column from X2.
        - If no suitable match exists (e.g., very different meanings), assign the value as `None`.

        Do NOT base matches on column position or order. Only use **textual similarity** of the column names.

        Return ONLY a valid Python dictionary. No explanation.
        """

        try:
            response = model.generate_content(prompt)
            response_text = response.text.strip("` \npython")

            cleaned_text = re.sub(r"datetime\.[a-zA-Z_]+\([^)]+\)", "'datetime_value'", response_text)

            raw_mapping = ast.literal_eval(cleaned_text)
            valid_columns = set(df_x2.columns)

            column_mapping = {}
            rejected_mappings = {}

            for x1_col, x2_col in raw_mapping.items():
                if x2_col is None:
                    column_mapping[x1_col] = None
                elif x2_col in valid_columns:
                    column_mapping[x1_col] = x2_col
                else:
                    column_mapping[x1_col] = None
                    rejected_mappings[x1_col] = x2_col

            st.subheader("Final Column Mapping")
            st.json(column_mapping)

            if rejected_mappings:
                st.warning("These Gemini-suggested mappings were ignored (not found in X2):")
                st.json(rejected_mappings)

            
            output_df = pd.DataFrame()
            for col in df_x1.columns:
                mapped_col = column_mapping.get(col)
                if mapped_col and mapped_col in df_x2.columns:
                    output_df[col] = df_x2[mapped_col]
                else:
                    output_df[col] = None

            output_df = output_df.astype(str)

            output = BytesIO()
            output_df.to_excel(output, index=False, engine="openpyxl")
            output.seek(0)

            st.success("Mapped Excel file created successfully!")
            st.download_button(
                label="Download Mapped Excel",
                data=output,
                file_name="mapped_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Failed to process Gemini response: {e}")
            st.text("Raw Gemini response:")
            st.code(response.text if 'response' in locals() else "No response received")
