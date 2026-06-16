# Email Sentiment Analysis (Enron Dataset)

## What This Project Does

This notebook performs **sentiment analysis and emotion detection** on the Enron email corpus (~35,000 emails). It classifies each email body as Positive, Negative, or Neutral using VADER sentiment analysis, detects granular emotions (joy, anger, trust, fear, etc.) using the NRC Emotion Lexicon, and visualises the results through word clouds, funnel charts, bar charts, and donut charts. It also demonstrates TextBlob as an alternative sentiment tool.

## How It Works — Step by Step

### Step 1 — Data Loading & Email Parsing

The Enron email CSV (`emails.csv`) is loaded (first 35,000 rows for speed). Python's built-in `email` parser extracts structured fields: `From`, `To`, `Subject`, `Date`, and the raw text body. A `user` column is derived from the file path.

### Step 2 — Text Cleaning

A thorough `clean_column()` function processes both subject lines and body text:

- Lowercasing, removing `re:` prefixes, stripping punctuation and numbers
- Expanding contractions (`can't` → `cannot`, `I'm` → `I am`)
- Removing HTML tags, square-bracket content, and Enron-specific artifacts
- Handling forwarded-email boilerplate
- Produces `Subject_new` and `body_new` columns

### Step 3 — VADER Sentiment Analysis

VADER (Valence Aware Dictionary and sEntiment Reasoner) is a lexicon-based sentiment tool designed for social media text. It assigns a compound polarity score (-1 to +1) to each email body:

- **Compound ≥ 0.05** → Positive
- **Compound ≤ -0.05** → Negative
- **Otherwise** → Neutral

Results are stored in `Sentiment` column.

### Step 4 — Visualisation

1. **Word Cloud (all emails)** — Most frequent words across all email bodies.
2. **Funnel Chart** — Distribution of Positive / Negative / Neutral emails.
3. **Bar Chart** — Top 20 most common words.
4. **Positive Word Cloud** — Words from positively-classified emails (green background).
5. **Negative Word Cloud** — Words from negatively-classified emails (red background).

### Step 5 — TextBlob (Alternative)

TextBlob provides a second opinion on sentiment using a different lexicon and algorithm. It returns a (polarity, subjectivity) tuple. The notebook applies it to every email for comparison.

### Step 6 — NRC Emotion Detection

The NRCLex library maps words to 8 emotions (anger, anticipation, disgust, fear, joy, sadness, surprise, trust) plus positive/negative. Each email is assigned its dominant emotion. A donut chart shows the distribution of emotions across the corpus (excluding "No emotion" cases).

### Step 7 — Test Cases

Three hand-crafted test emails verify the VADER pipeline produces expected sentiments (Positive, Negative, Neutral).

## How to Run It

### On Kaggle (Recommended)

1. Create a new Kaggle notebook.
2. Add the Enron dataset: `wcukierski/enron-email-dataset`.
3. Upload the notebook and run all cells.
4. No GPU needed — runs on CPU in ~5-10 minutes.

### Locally

1. Download the Enron dataset from Kaggle (you need a `kaggle.json` API key).
2. Install dependencies:

```bash
pip install numpy pandas matplotlib seaborn plotly wordcloud Pillow nltk spacy vaderSentiment NRCLex textblob
python -m nltk.downloader stopwords punkt
```

3. Update the CSV path in `pd.read_csv(...)` to your local file location.
4. Remove or skip the Kaggle setup cell (`!pip install kaggle`, `!kaggle datasets download...`).
5. Run all cells.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `vaderSentiment` | Rule-based sentiment scoring |
| `NRCLex` | Emotion detection via NRC Word-Emotion Lexicon |
| `textblob` | Alternative sentiment analysis |
| `nltk` | Tokenisation, stopwords |
| `wordcloud` | Word cloud generation |
| `plotly` | Interactive funnel and bar charts |
| `matplotlib` / `seaborn` | Static visualisations |
| `spacy` | Imported but not heavily used in this notebook |

## Output

- Inline word clouds (all, positive, negative)
- Interactive Plotly funnel chart (sentiment distribution)
- Interactive Plotly bar chart (common words)
- Donut chart of emotion distribution
- DataFrame columns: `compound`, `Sentiment`, `TB_score`, `TB_sentiment`, `Emotion`

## Limitations & Notes

- Only the first 35,000 emails are loaded (`nrows=35000`) — the full Enron corpus has ~500K. Increase this for full coverage.
- VADER is lexicon-based — it doesn't understand sarcasm, context, or domain-specific jargon well.
- NRCLex emotion detection is word-level (bag-of-words) — it doesn't capture sentence-level meaning.
- The notebook uses `%matplotlib inline` and Plotly, which require Jupyter/Kaggle to render properly.
- `spacy` is imported but not actively used for analysis — it could be leveraged for NER or dependency parsing in an extension.
- The `clean_column` function has hardcoded Enron-specific patterns — adapt it for other email corpora.
