# AI Resume Optimizer

Streamlit app that analyzes a PDF resume against a job description and shows AI-powered bullet improvements.

Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. On Streamlit Community Cloud, create a new app and point it to the GitHub repo.
3. In the app settings -> Secrets, add your OpenAI API key:

```
OPENAI_API_KEY = "sk-..."
```

4. Ensure `requirements.txt` includes the dependencies (already present):

```
streamlit
pypdf
openai
pdfminer.six
```

5. Deploy. The app reads `st.secrets["OPENAI_API_KEY"]` for the OpenAI key.

Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Notes

- The app does not write secrets to files. Do not commit secrets to the repo.
- I added a `.gitignore` to avoid committing local environments and secret files.
- If PDF extraction fails (empty text), the app attempts a `pdfminer.six` fallback.
