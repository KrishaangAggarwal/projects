# Text-to-SQL Converter (Stock Market Domain)

## What This Project Does

This notebook implements a **natural language to SQL translator** for stock market data. You type a question in plain English like *"What was the highest price for Intel in 2023?"* and it generates the corresponding SQL query, executes it against a SQLite database of stock data, and returns results. It uses a hybrid approach: rule-based regex matching for structured patterns, with a TF-IDF + neural network fallback for more ambiguous queries.

## Architecture & How It Works

### Component 1 — StockMarketDatabase

A wrapper class around SQLite that:

1. Creates a `stock_data` table with columns: `company`, `Date`, `Open`, `High`, `Low`, `Close`, `Adj Close`, `Volume`.
2. Loads CSV files (one per company) into the database.
3. Provides an `execute_query()` method for running arbitrary SQL.

### Component 2 — TextToSQLConverter

This is the core engine with two prediction paths:

#### Path A: Rule-Based (Regex)

The `rule_based_prediction()` method checks the input against regex patterns. Currently implemented:

- **Quarterly volume pattern**: *"total trading volume for [company] in the [first/second/third/fourth] quarter of [year]"* → generates a `SUM(Volume)` query with month filters.

If a pattern matches, the SQL is constructed directly from captured groups. This is precise but limited to predefined patterns.

#### Path B: Neural Network (TF-IDF + Dense)

When no rule matches, the system falls back to a learned mapping:

1. **Training data**: 20 hand-crafted (natural language question, SQL query) pairs covering common stock analysis queries.
2. **Feature extraction**: TF-IDF vectorisation (max 1,000 features) on the natural language side.
3. **Classification model**: A 3-layer dense neural network (`512 → 256 → 128 → softmax`) that classifies the input into one of the 20 known SQL templates.
4. **Prediction**: The input question is vectorised, the network predicts the most similar training query, and the corresponding SQL is returned.

```
Input: "Show the latest stock price for Microsoft"
→ TF-IDF vector → Dense NN → Predicted class index → SQL template
→ "SELECT * FROM stock_data WHERE company = 'MSFT' ORDER BY Date DESC LIMIT 1"
```

### Component 3 — Interactive Loop

The `main()` function orchestrates everything:

1. Prompts for CSV file directory and file paths for each company (MSFT, INTC, IBM, DELL, SONY).
2. Loads data into SQLite.
3. Trains the neural network.
4. Enters a REPL loop: reads questions, generates SQL, executes, prints results.
5. Type `quit` to exit.

## How to Run It

### On Kaggle (Recommended)

1. Create a new Kaggle notebook.
2. Add the dataset: `vivovinco/microsoft-stock-data-and-key-affiliated-companies` (or any dataset with daily stock CSVs for MSFT, INTC, IBM, DELL, SONY).
3. Upload the notebook and run all cells.
4. When prompted for the CSV directory, enter the Kaggle input path (e.g., `/kaggle/input/microsoft-stock-data-and-key-affiliated-companies`).
5. For each company file, press Enter to accept defaults or type the correct filename.
6. Ask questions in the interactive prompt.

### Locally

1. Prepare CSV files with columns: `Date`, `Open`, `High`, `Low`, `Close`, `Adj Close`, `Volume` — one file per company named `MSFT.csv`, `INTC.csv`, `IBM.csv`, `DELL.csv`, `SONY.csv`.
2. Install dependencies:

```bash
pip install numpy pandas scikit-learn tensorflow
```

3. Run the notebook or convert to a script:

```bash
jupyter nbconvert --to script text-to-sql.ipynb
python text-to-sql.py
```

4. Follow the interactive prompts to point to your CSV directory.

### Example Session

```
Enter your question: What was the highest price for Intel in 2023?
Generated SQL: SELECT MAX(High) FROM stock_data WHERE company = 'INTC' AND strftime('%Y', Date) = '2023'
Results: [(55.46,)]

Enter your question: Show the top 5 days with highest volume for Microsoft
Generated SQL: SELECT Date, Volume FROM stock_data WHERE company = 'MSFT' ORDER BY Volume DESC LIMIT 5
Results: [('2024-01-15', 98234567), ...]
```

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `tensorflow` | Dense neural network for query classification |
| `scikit-learn` | TF-IDF vectorisation, label encoding, train/test split |
| `sqlite3` | In-memory database (built into Python) |
| `pandas` / `numpy` | Data loading and manipulation |

## Limitations & Notes

- **Only 20 training examples**: The neural network is essentially doing nearest-neighbour classification over 20 templates. It won't generalise to truly novel queries — it matches to the closest known pattern.
- **No parameterisation**: The NN returns a fixed SQL string from training, including hardcoded company names and dates. It doesn't dynamically substitute entities from the user's query.
- **Rule-based is more reliable**: For production use, expanding the regex rules would give better results than the small NN.
- **Interactive input**: The `main()` function uses `input()` — this works in Jupyter/Kaggle but blocks in non-interactive environments.
- **No query validation**: Generated SQL is executed directly. Malformed predictions could error out.
- **SQLite limitations**: No `CORR()` function, no window functions in older SQLite versions. Some training SQL queries may not execute correctly.

## Possible Extensions

- Replace the NN with an LLM (GPT/Claude) for true natural language understanding.
- Add entity extraction to dynamically slot company names, dates, and thresholds into SQL templates.
- Expand the rule-based patterns to cover more query types.
- Add a feedback loop where correct/incorrect results improve future predictions.
