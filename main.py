from fastmcp import FastMCP
import os
import aiosqlite 
import tempfile
import json

# Use temporary directory to bypass read-only cloud filesystems
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("ExpenseTracker")

def init_db(): 
    """Initialize database synchronously at module load"""
    import sqlite3
    with sqlite3.connect(DB_PATH) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL, 
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

init_db()

@mcp.tool()
async def add_expense(user_email: str, date: str, amount: float, category: str, subcategory: str = "", note: str = ""): 
    '''Add a new expense entry to the database for a specific user.'''
    try:
        async with aiosqlite.connect(DB_PATH) as c: 
            cur = await c.execute( 
                "INSERT INTO expenses(user_email, date, amount, category, subcategory, note) VALUES (?,?,?,?,?,?)",
                (user_email, date, amount, category, subcategory, note)
            )
            await c.commit() 
            return {"status": "success", "id": cur.lastrowid, "message": "Expense added successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}
    
@mcp.tool()
async def list_expenses(user_email: str, start_date: str, end_date: str): 
    '''List expense entries within an inclusive date range for a specific user.'''
    try:
        async with aiosqlite.connect(DB_PATH) as c: 
            cur = await c.execute( 
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE user_email = ? AND date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (user_email, start_date, end_date)
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()] 
    except Exception as e:
        return {"status": "error", "message": f"Error listing expenses: {str(e)}"}

@mcp.tool()
async def summarize(user_email: str, start_date: str, end_date: str, category: str = None): 
    '''Summarize expenses by category within an inclusive date range for a specific user.'''
    try:
        async with aiosqlite.connect(DB_PATH) as c: 
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) as count
                FROM expenses
                WHERE user_email = ? AND date BETWEEN ? AND ?
            """
            params = [user_email, start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total_amount DESC"

            cur = await c.execute(query, params) 
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()] 
    except Exception as e:
        return {"status": "error", "message": f"Error summarizing expenses: {str(e)}"}

@mcp.resource("expense:///categories", mime_type="application/json") 
def categories():
    """Return available expense categories."""
    try:
        if os.path.exists(CATEGORIES_PATH):
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()
                
        # Fallback if file doesn't exist
        return json.dumps({
            "categories": [
                "Food & Dining", "Transportation", "Shopping", "Entertainment", 
                "Bills & Utilities", "Healthcare", "Travel", "Education", "Business", "Other"
            ]
        }, indent=2)
    except Exception as e:
        return f'{{"error": "Could not load categories: {str(e)}"}}'

if __name__ == "__main__":
    mcp.run()
