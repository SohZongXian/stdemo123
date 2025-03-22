import streamlit as st
from azure.identity import ClientSecretCredential
from langgraph.graph import START, StateGraph
from langchain.sql_database import SQLDatabase
from langchain_openai import AzureChatOpenAI
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
import struct
import os
import urllib
import sqlalchemy as sa
from itertools import chain, repeat
from typing_extensions import TypedDict
from typing import Annotated
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def show_page2():
    # Azure AD credentials from .env
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    resource_url = "https://database.windows.net/.default"

    # Initialize Azure credential with ClientSecretCredential
    credential = ClientSecretCredential(tenant_id, client_id, client_secret)

    # LLM Model for Query Generation
    llm = AzureChatOpenAI(deployment_name="gpt-4o", api_version='2024-08-01-preview')

    # Custom Prompt Template
    custom_template = '''
    Given an input question, create a syntactically correct {dialect} query in T-SQL format to help find the answer.
    Unless the user specifies a specific number of examples, limit your query to at most {top_k} results.
    Order the results by a relevant column to return the most interesting examples in the database.
    Ensure that the order by column appears in the select clause as well.

    ## QUERY CONSTRUCTION RULES:
    1. Never query for all columns from a specific table; only select relevant columns for the question
    2. Do not use LIMIT clauses
    3. For all text filters:
        - Make filters case-insensitive using COLLATE Latin1_General_CI_AI
        - Use pattern matching with LIKE instead of exact matching or IN clauses
        - Example: `BusinessUnit COLLATE Latin1_General_CI_AI LIKE '%textfilter%'`
    4. Empty results handling: If no data is found, make that clear in your response

    Use only the following tables:
    {table_info}

    Question: {input}
    '''

    query_prompt_template = PromptTemplate(
        input_variables=["input", "table_info", "top_k", "dialect"],
        template=custom_template
    )

    # State definition
    class State(TypedDict):
        question: str
        query: str
        result: str
        answer: str

    class QueryOutput(TypedDict):
        query: Annotated[str, ..., "Syntactically valid SQL query."]

    # Database connection setup
    @st.cache_resource
    def init_db_connection():
        try:
            token_object = credential.get_token(resource_url)
            auth_token = token_object.token

            sql_endpoint = os.getenv("sql_endpoint")
            database = os.getenv("database")
            connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server={sql_endpoint},1433;Database={database};Encrypt=Yes;TrustServerCertificate=No"
            params = urllib.parse.quote(connection_string)

            token_as_bytes = bytes(auth_token, "UTF-8")
            encoded_bytes = bytes(chain.from_iterable(zip(token_as_bytes, repeat(0))))
            token_bytes = struct.pack("<i", len(encoded_bytes)) + encoded_bytes
            attrs_before = {1256: token_bytes}

            engine = sa.create_engine("mssql+pyodbc:///?odbc_connect={0}".format(params), connect_args={'attrs_before': attrs_before})
            db = SQLDatabase(engine)
            return db
        except Exception as e:
            st.error(f"Database connection error: {e}")
            return None

    # Query generation
    def write_query(state: State, db):
        prompt = query_prompt_template.format(
            dialect=db.dialect,
            top_k=100,
            table_info=db.get_table_info(),
            input=state["question"]
        )
        structured_llm = llm.with_structured_output(QueryOutput, method="function_calling")
        try:
            result = structured_llm.invoke(prompt)
            return {"query": result["query"]}
        except Exception as e:
            st.error(f"Error generating query: {e}")
            return {"query": "", "error": str(e)}

    # Query execution
    def execute_query(state: State, db):
        execute_query_tool = QuerySQLDataBaseTool(db=db)
        try:
            result = execute_query_tool.invoke(state["query"])
            return {"result": result}
        except Exception as e:
            st.error(f"Error executing query: {e}")
            return {"result": "", "error": str(e)}

    # Answer generation
    def generate_answer(state: State):
        prompt = (
            "Given the following user question, corresponding SQL query, "
            "and SQL result, answer the user question. If the result is empty, tell the user that the sql query returned empty result\n\n"
            f'Question: {state["question"]}\n'
            f'SQL Query: {state["query"]}\n'
            f'SQL Result: {state["result"]}'
        )
        try:
            response = llm.invoke(prompt)
            return {"answer": response.content}
        except Exception as e:
            st.error(f"Error generating answer: {e}")
            return {"answer": "", "error": str(e)}

    # Define the graph
    db = init_db_connection()
    graph_builder = StateGraph(State)
    graph_builder.add_node("write_query", lambda state: write_query(state, db))
    graph_builder.add_node("execute_query", lambda state: execute_query(state, db))
    graph_builder.add_node("generate_answer", generate_answer)
    graph_builder.add_edge(START, "write_query")
    graph_builder.add_edge("write_query", "execute_query")
    graph_builder.add_edge("execute_query", "generate_answer")
    graph = graph_builder.compile()

    # Streamlit UI
    st.markdown('<h1 class="header">Simple GenBI Chatbot</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subheader">Ask questions and get insights from your database!</p>', unsafe_allow_html=True)
    st.divider()

    if db is None:
        st.error("Failed to connect to the database. Please check your credentials and try again.")
    else:
        # Input form
        with st.form(key='chat_form', clear_on_submit=True):
            question = st.text_input("Enter your question:", placeholder="e.g., What is the average total spend for bumiputra vendor type?")
            submit_button = st.form_submit_button(label="Ask Now")

        if submit_button and question:
            with st.spinner("Processing your request..."):
                state = {"question": question}
                response = None
                for update in graph.stream(state, stream_mode="updates"):
                    if 'generate_answer' in update:
                        response = update['generate_answer'].get('answer')
                
                if response:
                    st.markdown(f'<div class="answer-box"><strong>Answer:</strong> {response}</div>', unsafe_allow_html=True)
                else:
                    st.error("Failed to process your request. Please try again.")
        elif submit_button and not question:
            st.warning("Please enter a question to proceed.")
