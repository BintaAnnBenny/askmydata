import os, re, time
import pandas as pd
import sqlglot
from sqlglot import exp
from sqlalchemy import create_engine
from dotenv import load_dotenv, find_dotenv
from google import genai

load_dotenv(find_dotenv(usecwd=True), override=True)
MOCK_AI = os.getenv("MOCK_AI") == "1"
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
client = None if MOCK_AI else genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def make_engine():
    url = os.getenv("READONLY_DATABASE_URL")
    if not url:
        raise RuntimeError("READONLY_DATABASE_URL is missing from your .env file.")
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+pg8000://" + url[len(prefix):]
            break
    ssl = "sslmode=" in url          # pg8000 doesn't accept sslmode in the URL
    if ssl:
        url = url.split("?")[0]
    return create_engine(url, connect_args={"ssl_context": True} if ssl else {})
ro_engine = None if MOCK_AI else make_engine()

SYSTEM_PROMPT ="""You are a data analyst assistant. Convert the user's question into ONE PostgreSQL SELECT query.

Table: sales
Columns: order_id, order_date, ship_date, ship_mode, customer_id, customer_name,
segment, country, city, state, postal_code, region, product_id, category,
sub_category, product_name, sales, quantity, discount, profit, profit_margin,
order_year, order_month, ship_days

Rules:
- Return ONLY the SQL query. No markdown, no explanation, no backticks.
- Only SELECT statements are allowed. Never write INSERT, UPDATE, DELETE, or DROP.
- Always add LIMIT 100 to the end, unless the query is a single aggregate (like a total or count).
- When rounding a division result to decimal places, always cast to numeric first,
  for example: ROUND((100 * SUM(profit) / SUM(sales))::numeric, 1)
- If the question cannot be answered using this table, respond with exactly: CANNOT_ANSWER
"""

ALLOWED_TABLES = {"sales"}


def call_gemini(prompt, retries=4, wait=3):
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL, contents=prompt
            )
            return response.text
        except Exception as e:
            msg = str(e).lower()
            if "perday" in msg:
                raise RuntimeError("Daily Gemini quota used up. Try again after the reset.") from e
            temporary = any(k in msg for k in ["503", "429", "overloaded", "high demand", "unavailable", "resource_exhausted"])
            if temporary and attempt < retries - 1:
                m = re.search(r"retry in ([\d.]+)s", msg)
                delay = float(m.group(1)) + 2 if m else wait * (attempt + 1)
                time.sleep(delay)
            else:
                raise


def question_to_sql(question):
    text = call_gemini(f"{SYSTEM_PROMPT}\n\nQuestion: {question}")
    return text.strip().replace("```sql", "").replace("```", "").strip()


def is_safe(sql):
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception:
        return False
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        return False
    tables = {t.name.lower() for t in statements[0].find_all(exp.Table)}
    return tables.issubset(ALLOWED_TABLES) and len(tables) > 0


def explain_result(question, sql, df):
    prompt = f"""Question: {question}
SQL used: {sql}
Result:
{df.to_string()}


Explain this result in 1-2 plain sentences for a business owner who doesn't know SQL. Be specific with numbers. Do not use markdown formatting."""
    try:
        return call_gemini(prompt)
    except Exception as e:
        return f"(Explanation unavailable right now: {e})"


def answer(question):
    if MOCK_AI:
        df = pd.DataFrame({"region": ["West"], "total_profit": [43900.63]})
        return {
            "sql": "SELECT region, SUM(profit) AS total_profit FROM sales GROUP BY region LIMIT 1",
            "data": df,
            "explanation": "(mock) The West region made the most profit, about $43,900.63.",
        }
    try:
        sql = question_to_sql(question)
    except Exception as e:
        return {"error": str(e)}
    if sql == "CANNOT_ANSWER":
        return {"error": "I can't answer that from this data."}
    if not is_safe(sql):
        return {"error": "That query was blocked for safety reasons.", "sql": sql}
    try:
        df = pd.read_sql(sql, ro_engine)
    except Exception as e:
        return {"error": f"The query failed to run: {e}", "sql": sql}
    return {"sql": sql, "data": df, "explanation": explain_result(question, sql, df)}