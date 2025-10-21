from langchain_core.tools import tool
import pyodbc
import pandas as pd
import groq
import os
from langgraph.prebuilt import create_react_agent
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
import streamlit as st
from dotenv import load_dotenv
load_dotenv() 
db = st.secrets["database"]

def get_api_key(key_name):
    """
    1. Try Streamlit Cloud secrets first
    2. Fallback to local .env or system environment
    """
    try:
        return st.secrets[key_name]  # Streamlit Cloud
    except (AttributeError, KeyError):
        return os.getenv(key_name)   # Local environment / .env

# -------------------------------
# Retrieve your API keys
# -------------------------------
OPENAI_API_KEY = get_api_key("OPENAI_API_KEY")
GROQ_API_KEY   = get_api_key("GROQ_API_KEY")

# Test if keys loaded
st.write("OPENAI_KEY loaded:", bool(OPENAI_API_KEY))
st.write("GROQ_KEY loaded:", bool(GROQ_API_KEY))

# -------------------------------
# Example usage in your code
# -------------------------------
# Replace these with your API calls

# OpenAI example
# import openai
# openai.api_key = OPENAI_API_KEY
# response = openai.ChatCompletion.create(
#     model="gpt-4",
#     messages=[{"role": "user", "content": "Hello!"}]
# )
# st.write(response)

# Groq API example
# import groq_client
# client = groq_client.Client(api_key=GROQ_API_KEY)
# result = client.do_something()
# st.write(result)

#sql conection
conn = pyodbc.connect(
    f"DRIVER={{{db['DRIVER']}}};SERVER={db['SERVER']};DATABASE={db['DATABASE']};UID={db['UID']};PWD={db['PWD']};TrustServerCertificate=yes;Encrypt=no;Connection Timeout=10;"
)

# print("✅ Connected successfully!")


@tool
def check_fg_inventory(FG: str) -> str:
    """Returns a raw SQL query to check if FG is in stock."""
    return f"SELECT SUM(ISNULL(receivedqty, 0) - ISNULL(issuedqty, 0)) AS StkBalance FROM StockLedger_Table WHERE Product = '{FG}' GROUP BY Product"

@tool
def get_bom_for_FG(FG: str) -> str:
    """this funciton will retrurn query to check whether it has the FG in inventory"""
    querry =  f"select * from Master_BillsOfMaterial_Table where product='{FG}'"
    return  {"sql_query": querry}

@tool
def sql_executor(sql_query: str) -> str:
    """This function will take a raw SQL query and return the result as JSON."""
    try:
        # Make sure no parameterization is happening
        df = pd.read_sql_query(sql_query, conn)  # <-- use read_sql_query
        return df.to_json(orient='records')
    except Exception as e:
        return f"SQL execution failed: {e}"
    


tools = [check_fg_inventory,get_bom_for_FG,sql_executor]

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key= GROQ_API_KEY
)


prompt = ChatPromptTemplate.from_messages(
    [
        ("system", """you are a dispatch planner assistant . you have access to 3 tools:1) `check_fg_inventory(FG: str)` , returns an SQL query string to check FG stock.2) `get_bom_for_FG(FG: str)`,  returns an SQL query string to get BOM.3) `sql_executor(sql_query: str)`, executes a RAW SQL string and returns result in JSON. IMPORTANT: Do not write your own SQL query. Always use `check_fg_inventory` or `get_bom_for_FG` to generate the SQL.Then, use the returned SQL string directly with `sql_executor`.Do not modify, rewrite, or ignore the SQL returned by the tools. Always pass the exact SQL as-is to `sql_executor`. Workflow:1. Use `check_fg_inventory(FG)` → pass result to `sql_executor` to get stock and if stock is available return ready to dispatch. 2. If not in stock, use `get_bom_for_FG(FG)` → pass result to `sql_executor`. 3. Count RM rows returned. Dispatch days = RM count + 1.Respond accordingly based on availability."""),


        ("human", "{input}"),
        # Placeholders fill up a **list** of messages
        ("placeholder", "{agent_scratchpad}"),
    ]
)

# query = "i need Blend Blown WHITE 2575 OS check if it is in inventory or not?"

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools,verbose=True)

# chat_bot_output = agent_executor.invoke({"input": query})

# print(chat_bot_output['output'])

# ---------------- Streamlit UI Setup ----------------
st.set_page_config(page_title="ETD Calculator", layout="centered")
st.markdown(
    """
    <style>
    body {
        background-color: #000000;
        color: #FFFFFF;
    }
    .stApp {
        background-color: #000000;
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("🚛 ETD Calculator")

# ---------------- Chat Interface ----------------
user_input = st.text_input("Ask your question about any FG...", "")

if user_input:
    with st.spinner("Calculating ETD..."):
        try:
            result = agent_executor.invoke({"input": user_input})
            st.success("✅ Result:")
            st.write(result["output"])
        except Exception as e:
            st.error(f"Something went wrong: {e}")