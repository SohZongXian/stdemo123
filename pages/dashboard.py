import streamlit as st
from azure.identity import ClientSecretCredential
import os
import urllib
import sqlalchemy as sa
from itertools import chain, repeat
import struct
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.graph_objects as go
import numpy as np
from datetime import date
import datetime

def show_page1():
    st.title("Procurement Dashboard")
    st.write("Time series chart of Actual vs. Budget Spend")
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    # Initialize the credential
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    resource_url = "https://database.windows.net/.default"

    # Get the token
    token_object = credential.get_token(resource_url)

    sql_endpoint = os.getenv("sql_endpoint")
    database = os.getenv("database")

    connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server={sql_endpoint},1433;Database={database};Encrypt=Yes;TrustServerCertificate=No"
    params = urllib.parse.quote(connection_string)

    # Retrieve and encode access token
    token_as_bytes = bytes(token_object.token, "UTF-8")
    encoded_bytes = bytes(chain.from_iterable(zip(token_as_bytes, repeat(0))))
    token_bytes = struct.pack("<i", len(encoded_bytes)) + encoded_bytes
    attrs_before = {1256: token_bytes}

    # Build the connection
    engine = sa.create_engine("mssql+pyodbc:///?odbc_connect={0}".format(params), connect_args={'attrs_before': attrs_before})
    st.subheader("Asset Management")
    # Summary metrics (placeholder values from image)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Available Hours", "4.83K")
    col2.metric("Total Usage Hours", "1.20K")
    col3.metric("Avg Utilization Rate", "24.65")
    col4.metric("Avg Turnover Rate", "1.47")

    # Query asset_utilization table
    asset_query = text("""
    SELECT 
        asset_name,
        AVG(asset_turnover_rate) AS asset_turnover_rate,
        AVG(utilization_rate) AS utilization_rate,
        MAX(last_maintenance_date) AS last_maintenance_date,
        AVG(usage_hours) AS usage_hours
    FROM 
        sc_stg.asset_utilization
    GROUP BY 
        asset_name
    ORDER BY 
        MAX(last_maintenance_date) ASC
    """)

    with engine.connect() as connection:
        asset_results = connection.execute(asset_query)
        df_assets = pd.DataFrame(asset_results.fetchall(), columns=asset_results.keys())

    # Ensure data types are correct
    df_assets['asset_turnover_rate'] = df_assets['asset_turnover_rate'].fillna(0).astype(float)
    df_assets['utilization_rate'] = df_assets['utilization_rate'].fillna(0).astype(float)
    df_assets['usage_hours'] = df_assets['usage_hours'].fillna(0).astype(float)
    df_assets['last_maintenance_date'] = pd.to_datetime(df_assets['last_maintenance_date'])

    # Generate dummy MonthYear column
    months = pd.date_range(start='2023-01-01', end='2023-12-01', freq='MS')
    dummy_months = np.tile(months.to_pydatetime(), len(df_assets) // len(months) + 1)[:len(df_assets)]
    df_assets['MonthYear'] = [pd.Timestamp(date).strftime('%b %Y') for date in dummy_months]  # Use pd.Timestamp for safety

    # Sort by MonthYear for visualization
    df_assets['MonthYear'] = pd.to_datetime(df_assets['MonthYear'], format='%b %Y')
    df_assets = df_assets.sort_values('MonthYear')
    df_assets['MonthYear'] = df_assets['MonthYear'].dt.strftime('%b %Y')  # Reformat for display

    # Display asset management table
    st.table(df_assets)

    # Utilization & Turnover Rate Analysis Chart
    st.subheader("Utilization & Turnover Rate Analysis")
    # Create Plotly chart
    fig = go.Figure()

    # Add utilization_rate trace with area fill
    fig.add_trace(go.Scatter(
        x=df_assets['MonthYear'],
        y=df_assets['utilization_rate'],
        name='Utilization Rate',
        line=dict(color='#FF4500', width=2),
        fill='tonexty',
        fillcolor='rgba(255, 69, 0, 0.3)',
        mode='lines'
    ))

    # Add asset_turnover_rate trace with area fill
    fig.add_trace(go.Scatter(
        x=df_assets['MonthYear'],
        y=df_assets['asset_turnover_rate'],
        name='Asset Turnover Rate',
        line=dict(color='#4682B4', width=1.5),
        fill='tozeroy',
        fillcolor='rgba(70, 130, 180, 0.2)',
        mode='lines'
    ))

    # Update layout
    fig.update_layout(
        title='Utilization & Turnover Rate Analysis',
        xaxis_title='MonthYear',
        yaxis_title='Rate (%)',
        template='plotly_dark',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Display chart
    st.plotly_chart(fig)

    # SQL query to join dim_calendar and cost_savings
    st.subheader("Actual vs. Budget Spend Over Time")
    business_units_query = text("""
    SELECT 
        FORMAT(dc.date, 'MMM yyyy') AS MonthYear,
        SUM(cs.actual_cost) AS actual_cost,
        SUM(cs.budget_cost) AS budget_cost
    FROM 
        sc_stg.dim_calendar dc
    INNER JOIN 
        sc_stg.cost_savings cs
    ON 
        dc.date = cs.savings_date
    GROUP BY 
        dc.date
    ORDER BY 
        dc.date ASC
    """)

    # Execute query and load data into pandas DataFrame
    with engine.connect() as connection:
        results = connection.execute(business_units_query)
        df = pd.DataFrame(results.fetchall(), columns=results.keys())

    # Ensure data types are correct
    df['actual_cost'] = df['actual_cost'].fillna(0).astype(float)
    df['budget_cost'] = df['budget_cost'].fillna(0).astype(float)

    # Sort by MonthYear index
    df['MonthYear'] = pd.to_datetime(df['MonthYear'], format='%b %Y').dt.to_period('M')
    df = df.sort_values('MonthYear')
    df.set_index('MonthYear', inplace=True)
    df.index = df.index.strftime('%b %Y')

    # Display raw data
    st.write("Data Preview:")
    st.dataframe(df)

    # Create Plotly chart for Actual vs. Budget
    fig_spend = go.Figure()

    # Add actual_cost trace with area fill
    fig_spend.add_trace(go.Scatter(
        x=df.index,
        y=df['actual_cost'],
        name='Actual Cost',
        line=dict(color='#FF4500', width=2),
        fill='tonexty',
        fillcolor='rgba(255, 69, 0, 0.3)',
        mode='lines'
    ))

    # Add budget_cost trace with area fill
    fig_spend.add_trace(go.Scatter(
        x=df.index,
        y=df['budget_cost'],
        name='Budget Cost',
        line=dict(color='#4682B4', width=1.5),
        fill='tozeroy',
        fillcolor='rgba(70, 130, 180, 0.2)',
        mode='lines'
    ))

    # Update layout
    fig_spend.update_layout(
        title='Actual Vs Budget Spend',
        xaxis_title='Date',
        yaxis_title='Cost ($M)',
        template='plotly_dark',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Display chart
    st.plotly_chart(fig_spend)
        