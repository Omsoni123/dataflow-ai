# DataFlow AI

**Upload a dataset, get it cleaned automatically, and ask questions about it in plain English.**

DataFlow AI is an AI-powered analytics SaaS. It takes a raw CSV/Excel file, cleans and profiles it, generates KPIs, and lets you query the data in natural language. An LLM turns each question into safe SQL, runs it on your data, and returns the answer.

**Live app:** [dataflow-ai-sand.vercel.app](https://dataflow-ai-sand.vercel.app)

---

## Demo

> Add your screenshots to a `docs/screenshots/` folder and keep the file names below (or edit the paths).

### 1. Upload and auto-clean
<img width="1851" height="831" alt="image" src="https://github.com/user-attachments/assets/ce9a435d-2705-47f0-b323-653c6c04b60d" />


### 2. Data profiling and dynamic KPIs
<img width="1810" height="792" alt="image" src="https://github.com/user-attachments/assets/a4e7d9db-a17e-468f-928e-abda22cd3c77" />

### 3. Ask questions in plain English
<img width="1885" height="733" alt="image" src="https://github.com/user-attachments/assets/ed5cd99c-f8a2-42c1-a899-de33a3b9ef7b" />


> Optional: a short demo GIF or Loom video link goes here.

---

## What it does

| Feature | What it means for the user |
|---|---|
| **Dataset upload** | Drop in a messy file and start working with it. |
| **Automated cleaning** | Fixes dates, currencies, missing values and duplicates. |
| **Data profiling** | Summarizes columns, types and data quality at a glance. |
| **Dynamic KPIs** | Generates KPIs from the columns in your own data. |
| **Natural-language querying** | Ask "which region had the highest sales?" and get an answer. |
| **Secure by design** | Each user only ever sees their own data. |
| **Auth and payments** | Login with JWT and subscriptions with Razorpay. |

---

## How the AI query workflow works

Every question follows the same agent-style pipeline:

```
User question
     |
     v
1. Schema retrieval     -> reads the actual tables and columns of the uploaded dataset
     |
     v
2. SQL generation       -> Groq LLM writes SQL grounded in that schema
     |
     v
3. Validation           -> guardrails check the SQL before it runs
     |
     v
4. Execution            -> runs on PostgreSQL, scoped to the user's data
     |
     v
5. Result summary       -> answer returned to the user in plain language
```

**Why the schema step matters:** the LLM is given the real table and column names of each uploaded dataset, not a fixed schema. This reduces made-up columns and wrong queries.

### Safety guardrails

The generated SQL is never trusted blindly. Before anything runs:

- **SELECT-only:** no INSERT, UPDATE, DELETE or DROP.
- **Table and column validation:** the query may only use tables and columns that exist in the user's dataset.
- **Multi-statement blocking:** stops chained queries such as `SELECT ...; DROP ...`.
- **User data isolation:** a user can only query their own uploaded data.

---

## Universal Data Engine

Before the AI queries the data, the cleaning engine prepares it:

- Date parsing across mixed formats
- Currency normalization
- Missing-value handling
- Duplicate detection
- Automatic profiling of the cleaned result

Clean input means better SQL and more trustworthy answers.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Data processing | Pandas |
| AI / LLM | Groq LLM API (natural language to SQL) |
| Frontend | Next.js, TypeScript |
| Auth | JWT |
| Payments | Razorpay |
| Deployment | Vercel (frontend), Render (backend) |

---

## Project structure

```
dataflow-ai/
├── Api/                  # API routes and endpoints
├── SRC/                  # Core logic: cleaning engine, profiling, KPI and query pipeline
├── Data/                 # Sample datasets
├── Notebook/             # Exploration and prototyping notebooks
├── frontend/             # Next.js web app
├── app.py                # FastAPI entry point
├── requirements.txt      # Python dependencies
├── test_cleaning_engine.py
└── test_postgres.py
```

---

## Run it locally

**Prerequisites:** Python 3.11, Node.js 18+, PostgreSQL, and a [Groq API key](https://console.groq.com).

### 1. Clone

```bash
git clone https://github.com/Omsoni123/dataflow-ai.git
cd dataflow-ai
```

### 2. Backend

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_key
DATABASE_URL=postgresql://user:password@localhost:5432/dataflow
JWT_SECRET=your_secret
RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
```

Start the API:

```bash
uvicorn app:app --reload
```

The API runs at `http://localhost:8000`, with interactive docs at `/docs`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

### 4. Run the tests

```bash
python test_cleaning_engine.py
python test_postgres.py
```

---

## Roadmap

- [ ] Self-correction loop: feed SQL errors back to the LLM and retry automatically
- [ ] Chart generation from query results
- [ ] Support for multiple linked datasets
- [ ] Query history and saved questions

---

## About the author

**Om Soni**: Data Analyst | Agentic AI & LLM Workflows | SQL | Python | BigQuery | Power BI
M.Sc. Artificial Intelligence, University of Mumbai

[LinkedIn](https://www.linkedin.com/) | om.soni2706@gmail.com

---

*Built as an end-to-end project to make data analysis accessible to people who don't write SQL.*
