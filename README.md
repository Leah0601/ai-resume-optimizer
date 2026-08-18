# AI Resume Optimizer

Streamlit app that analyzes a DOCX resume against a job description, rewrites experience bullets using AI, and generates an optimized DOCX resume for download.

Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. On Streamlit Community Cloud, create a new app and point it to the GitHub repo.
3. In the app settings -> Secrets, add your OpenAI API key under the name `OPENAI_API_KEY`.

4. Ensure `requirements.txt` includes the dependencies (already present). This app uses `python-docx` for DOCX parsing and generation in addition to the packages below:

```
streamlit
pypdf
openai
pdfminer.six
python-docx
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
- The app expects a DOCX upload and uses `python-docx` for reliable extraction and generation. For PDFs the app has PDF extraction fallbacks (`pypdf`, `pdfminer.six`) but DOCX is preferred.
