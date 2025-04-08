import os
import time
import base64
import pandas as pd
import plotly.graph_objects as go
from functools import reduce
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date 
from app.scripts.data_fetchers.broker_data import BrokerData
from app.logger import logger

def load_bse500_data():
    day_time = []
    last_eod_date = datetime(2020, 1, 1).date()

    start_time_day = last_eod_date
    current_time = datetime.now().date()
    back_time_day = current_time - timedelta(days = 1000)

    if back_time_day < start_time_day:
        back_time_day = start_time_day

    i = 0
    while back_time_day >= start_time_day:
        append_time = [str(current_time), str(back_time_day), 'day']
        day_time.append(append_time)  
        if back_time_day == start_time_day:
            break   
        current_time = back_time_day
        back_time_day = current_time - timedelta(days = 2000)
        if current_time >= start_time_day >= back_time_day:
            back_time_day = start_time_day
        i += 1

    store_dfs = []
    for value in day_time:
        from_date = value[1]
        to_date = value[0]
        interval = value[2]
        exchange = "BSE"
        exchange_token = "4"
        instrument_type = "INDEX"
        instrument = {
            "from_date": str(from_date),
            "to_date": str(to_date),
            "interval": interval,
            "exchange": exchange,
            "exchange_token": exchange_token,
            "instrument_type": instrument_type
        }
        time.sleep(1)
        bse500_data = BrokerData.historical_data(instrument)
        bse500_data = bse500_data['data']
        bse500_df = pd.DataFrame(bse500_data)
        if not bse500_df.empty:
            bse500_df = bse500_df.fillna(0)
            store_dfs.append(bse500_df)
        else:
            print("dataset is empty")
        
        complete_bse500_data = pd.concat(store_dfs, ignore_index=True)
        complete_bse500_data['datetime'] = pd.to_datetime(complete_bse500_data['datetime'])
        complete_bse500_data['datetime'] = complete_bse500_data['datetime'].dt.date
        complete_bse500_data = complete_bse500_data.drop_duplicates().sort_values(by="datetime").reset_index()
        return complete_bse500_data

def read_image_as_base64(file_path):
    with open(file_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode()
    
def calculate_years(start_date: str, end_date: str):
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    years = end_date.year - start_date.year
    months_diff = end_date.month - start_date.month
    days_diff = end_date.day - start_date.day
    
    if months_diff < 0 or (months_diff == 0 and days_diff < 0):
        years -= 1
        months_diff += 12
    fraction_of_year = months_diff / 12 + days_diff / 365.25
    return years + fraction_of_year

def get_bse500_twrr_cagr(acc_start_date: str, snapshot_date: str, bse500_df: pd.DataFrame):
    acc_start_date = pd.to_datetime(acc_start_date)
    snapshot_date = pd.to_datetime(snapshot_date)
    bse500_df['datetime'] = pd.to_datetime(bse500_df['datetime'])
    bse500_df = bse500_df[
        (bse500_df['datetime'] >= acc_start_date) &
        (bse500_df['datetime'] <= snapshot_date)
    ]
    bse500_df['year'] = bse500_df['datetime'].dt.year
    bse500_df['month'] = bse500_df['datetime'].dt.month
    bse500_df['day'] = bse500_df['datetime'].dt.day

    march_values = []
    for year, year_group in bse500_df.groupby('year'):
        for month, month_group in year_group.groupby('month'):
            for day, day_group in month_group.groupby('day'):
                if month == 4 and day == 1:
                    march_values.append(month_group.iloc[-1])

    march_df = pd.DataFrame(march_values)

    first_row = bse500_df.iloc[[0]]
    last_row = bse500_df.iloc[[-1]]

    bse500_df = pd.concat([first_row, last_row, march_df], ignore_index=False)
    bse500_df = bse500_df[['datetime', 'close']]
    bse500_df = bse500_df.sort_values(by='datetime').reset_index(drop=True)

    bse500_df['start_date'] = bse500_df['datetime']
    bse500_df['end_date'] = bse500_df['datetime'].shift(-1).fillna(0)
    bse500_df['start_value'] = bse500_df['close']
    bse500_df['end_value'] = bse500_df['close'].shift(-1).fillna(0)
    bse500_df = bse500_df.drop(columns=['datetime', 'close'])
    bse500_df = bse500_df[bse500_df['end_value'] != 0]
    bse500_df['Returns'] = (bse500_df['end_value'] / bse500_df['start_value']) - 1
    bse500_df['Returns+1'] = bse500_df['Returns'] + 1

    absolute_twrr = ((bse500_df['end_value'].iloc[-1] / bse500_df['start_value'].iloc[0]) - 1) * 100
    current_year_twrr = bse500_df['Returns'].iloc[-1] * 100
    
    cagrs = list(bse500_df['Returns+1'])
    product = reduce(lambda x, y: x * y, cagrs)
    absolute_cagr = 0
    years_value = calculate_years(start_date=str(acc_start_date.date()), end_date=str(snapshot_date.date()))
    if years_value > 1:
        absolute_cagr = ((product ** (1/years_value)) - 1) * 100
    return round(current_year_twrr, 2), round(absolute_twrr, 2), round(absolute_cagr, 2)

def get_portfolio_summary(inception_date: str, total_holdings: float, invested_amt: float) -> pd.DataFrame:
    pnl = int(total_holdings - invested_amt)
    summary_data = {
        "PORTFOLIO SUMMARY": [f"SINCE - {inception_date}", "NET CAPITAL INVESTED", "TOTAL GAIN/LOSS", "PORTFOLIO VALUE"],
        "": [ "Amount(INR)", f"₹{round(invested_amt, 2)}", f"₹{pnl}", f"₹{round(total_holdings, 2)}"]
    }
    portfolio_summary = pd.DataFrame(summary_data)
    portfolio_summary.set_index("PORTFOLIO SUMMARY", inplace=True)
    return portfolio_summary

def get_returns_table(
        plus91_current_year_twrr: float = 0,
        plus91_absolute_twrr: float = 0,
        plus91_absolute_cagr: float = 0,
        bse500_current_year_twrr: float = 0,
        bse500_absolute_twrr: float = 0,
        bse500_absolute_cagr: float = 0
    ) -> pd.DataFrame:
    returns_data = {
    'RETURNS': ['PLUS91', 'BSE500'],
    'FY 24-25': [f'{round(plus91_current_year_twrr, 1)}%', f'{round(bse500_current_year_twrr, 1)}%'],
    'ABSOLUTE RETURNS': [f'{round(plus91_absolute_twrr, 1)}%', f'{round(bse500_absolute_twrr, 1)}%'],
    'SINCE INCEPTION CAGR': [f'{round(plus91_absolute_cagr, 1)}%', f'{round(bse500_absolute_cagr, 1)}%']
    }
    returns_df = pd.DataFrame(returns_data)
    returns_df.replace('0%', 'NA', inplace=True)
    return returns_df

def get_portfolio_report(
        actual_portfolio: pd.DataFrame, 
        cash_value: float, 
        total_holdings: float
    ) -> pd.DataFrame:
    actual_portfolio = actual_portfolio.rename(columns={
        'trading_symbol': 'SECURITY',
        'quantity': 'QUANTITY',
        'market_value': 'MARKET VALUE',
    })
    actual_portfolio['MARKET VALUE'] = actual_portfolio['MARKET VALUE'].astype(float)
    actual_portfolio['QUANTITY'] = actual_portfolio['QUANTITY'].astype(float)
    actual_portfolio = actual_portfolio.sort_values(by='MARKET VALUE', ascending=False)
    actual_portfolio['ASSETS'] = (actual_portfolio['MARKET VALUE'] / total_holdings) * 100
    actual_portfolio['ASSETS'] = actual_portfolio['ASSETS'].round(1)
    actual_portfolio['ASSETS'] = actual_portfolio['ASSETS'].astype(str) + '%'
    actual_portfolio['SECURITY'] = actual_portfolio['SECURITY'].str.replace(r' (EQ|MF)$', '', regex=True)
    actual_portfolio = actual_portfolio.sort_values(by='MARKET VALUE', ascending=False)

    logger.debug(f"Cash value: {cash_value}, Total holdings: {total_holdings}")
    if pd.isna(cash_value) or pd.isna(total_holdings) or total_holdings == 0:
        logger.warning("Invalid cash_value or total_holdings, setting cash ASSETS to 0%")
        cash_percentage = 0
    else:
        cash_percentage = int((cash_value / total_holdings) * 100)

    merge_data = {
        'SECURITY': ['TOTAL HOLDINGS VALUE', 'CASH', 'TOTAL PORTFOLIO VALUE'],
        'QUANTITY': [0, 0, 0],
        'MARKET VALUE': [
            actual_portfolio['MARKET VALUE'].sum(), 
            cash_value, 
            total_holdings
        ],
        'ASSETS': [
            '0%', 
            f'{int(((cash_percentage) * 100))}%', 
            '0%'
        ]
    }
    merged_df = pd.DataFrame(merge_data)
    actual_portfolio = pd.concat([actual_portfolio, merged_df], ignore_index=True)
    actual_portfolio[['MARKET VALUE']] = actual_portfolio[['MARKET VALUE']].astype(int)
    actual_portfolio.replace(0, '', inplace=True)
    return actual_portfolio

def generate_report(
        portfolio_report
        : pd.DataFrame,
        portfolio_summary: pd.DataFrame,
        returns_df: pd.DataFrame, 
        logo_path: str,
        down_design_path: str,
        account_name: str,
        broker_code: str,
        acc_start_date: str
    ) -> bytes:
    page_width = 18
    base_page_height = 20
    page_dpi = 50
    page_margin = 0

    num_table_rows = 28
    table_row_height = 20
    table_height_in_inches = 11.2
    total_page_height = 31.2

    downDesign_base64 = read_image_as_base64(down_design_path)
    logo_base64 = read_image_as_base64(logo_path)
    account_name = account_name.strip()
    broker_code = broker_code.strip()

    # CREATE SUBPLOT
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.5, 0.6],
        vertical_spacing=0.2,
        specs=[[{"type": "xy"}], [{"type": "domain"}]]
    )

    fig.update_layout(
        width=page_width * page_dpi,
        height=total_page_height * page_dpi,
        margin=dict(l=page_margin, r=page_margin, t=page_margin, b=page_margin),
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False)
    )

    # Add down design
    fig.add_layout_image(
        dict(
            source=f"data:image/png;base64,{downDesign_base64}",
            xref='paper', yref='paper',
            x=1, y=0,
            sizex=0.25, sizey=0.25,
            xanchor='right', yanchor='bottom',
            layer='below'
        )
    )

    # ADD HORIZONTAL BLACK TOP LINE
    fig.add_shape(
        type='line',
        x0=0.015, y0=0.937,
        x1=0.985, y1=0.937,
        xref='paper', yref='paper',
        line=dict(color='black', width=3)
    )

    # ADD VERTICAL RED TOP LINE
    fig.add_shape(
        type='line',
        x0=0.65, y0=0.993,
        x1=0.65, y1=0.95,
        xref='paper', yref='paper',
        line=dict(color='red', width=3)
    )

    # ADD PLUS91 LOGO
    fig.add_layout_image(
        dict(
            source=f"data:image/png;base64,{logo_base64}",
            xref='paper', yref='paper',
            x=0.63, y=0.952,
            sizex=0.065, sizey=0.065,
            xanchor='right', yanchor='bottom',
            layer='below'
        )
    )

    # ADD RED BOX
    fig.add_shape(
        type='rect',
        x0=0.015, y0=0.87,
        x1=0.49, y1=0.925,
        xref='paper', yref='paper',
        line=dict(color='black', width=2),
        fillcolor='rgba(255,0,0,0.5)',
        opacity=1
    )

    # ADD TWRR TABLE
    #############################################################################################################
    twrr_values = [returns_df[col].tolist() for col in returns_df.columns]

    fig.add_trace(
        go.Table(
            columnwidth=[0.25, 0.25, 0.25, 0.25],
            header=dict(
                values=["<b>RETURNS</b>", "<b>FY 24-25 %</b>", "<b>ABSOLUTE RETURNS %</b>", "<b>SINCE INCEPTION CAGR %</b>"],
                fill_color='rgba(211, 211, 211, 0.2)',
                align='center',
                line_color='black',
                height=25,
                font=dict(size=11, color='black', family='Arial')
            ),
            cells=dict(
                values=twrr_values,
                fill_color='rgba(0,0,0,0)',
                align=['center', 'center', 'center', 'center'],
                line_color='black',
                height=25,
                font=dict(
                    size=11,
                    color='black',
                    family='Arial'
                )
            ),
            domain=dict(x=[0.02, 0.49], y=[0.1, 0.716])  # Adjust domain to position the table correctly
        )
    )



    # ADD PORTFOLIO SUMMARY
    #############################################################################################################
    portfolio_summary_values = [portfolio_summary.index.tolist(), portfolio_summary.iloc[:, 0].tolist()]

    fig.add_trace(
        go.Table(
            columnwidth=[0.7, 0.3],
            header=dict(
                values=["<b>PORTFOLIO SUMMARY", ""],
                fill_color='rgba(211, 211, 211, 0.2)',
                align='left',
                line_color='black',
                height=25,
                font=dict(size=11, color='black', family='Arial')
            ),
            cells=dict(
                values=portfolio_summary_values,
                fill_color='rgba(0,0,0,0)',
                align=['left', 'right'],
                line_color='black',
                height=25,
                font=dict(
                    size=11,
                    color='black',
                    family='Arial'
                )
            ),
            domain=dict(x=[0.02, 0.49], y=[0.25, 0.815])
        )
    )


    # ADD PORTFOLIO TABLE
    #############################################################################################################

    light_grey = 'rgba(211, 211, 211, 0.35)'

    values = [portfolio_report[col].tolist() for col in portfolio_report.columns]
    values[0][-1] = f"<b>{values[0][-1]}</b>"
    values[2][-1] = f"<b>{values[2][-1]}</b>"

    fig.add_trace(
        go.Table(
            columnwidth=[0.4, 0.2, 0.27, 0.2],
            header=dict(
                values=["<b>SECURITY</b>", "<b>QUANTITY</b>", "<b>MARKET VALUE</b>", "<b>ASSETS</b>"],
                fill_color='rgba(211, 211, 211, 0.2)',
                align='center',
                line_color='black',
                height=25,
                font=dict(size=11, color='black', family='Arial')
            ),
            cells=dict(
                values=[portfolio_report['SECURITY'], portfolio_report['QUANTITY'], portfolio_report['MARKET VALUE'], portfolio_report['ASSETS'].round(1)],
                fill_color='rgba(0,0,0,0)',
                align=['left', 'right', 'right', 'right'],
                line_color='black',
                height=20,
                font=dict(
                    size=11,
                    color='black',
                    family='Arial',
                    )
            ),
            domain=dict(x=[0.51, 0.985], y=[0, min(1.1, 0.925)])
        )
    )

    # ADD HEADING RECTANGLE
    fig.add_shape(
        type="rect",
        x0=0.015, y0=0.99, x1=0.5, y1=0.95,
        line=dict(color="black", width=3),
        fillcolor="rgba(0, 0, 0, 0)",
        layer='below'
    )

    # ADD PLUS91 ASSET MANAGEMENT HEADING TEXT
    fig.add_annotation(
        x=0.02, y=0.99,
        text=f'PLUS91 ASSET MANAGEMENT',
        showarrow=False,
        font=dict(family='Arial', size=25, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    # ADD AS OF: HEADING
    today_date = date.today().strftime('%d-%m-%Y')
    fig.add_annotation(
        x=0.02, y=0.968,
        text=f'AS OF: {today_date}',
        showarrow=False,
        font=dict(family='Arial', size=19, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    # ADD EXPERTISE YOU NEED
    fig.add_annotation(
        x=0.7, y=0.985,
        text=f'EXPERTISE YOU NEED',
        showarrow=False,
        font=dict(family='Arial', size=15, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    # ADD SERVICE YOU DESERVE
    fig.add_annotation(
        x=0.68, y=0.972,
        text=f'SERVICE YOU DESERVE',
        showarrow=False,
        font=dict(family='Arial', size=18, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    # ADD REDBOX DETAILS
    # Add Strategy Name
    fig.add_annotation(
        x=0.02, y=0.922,
        text=f'STRATEGY: PLUS91 CUSTOMIZED PORTFOLIO',
        showarrow=False,
        font=dict(family='Arial', size=14, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    client_name = f"{account_name.upper()} {broker_code}"
    # Add Account
    fig.add_annotation(
        x=0.02, y=0.906,
        text=f'ACCOUNT: {client_name}',
        showarrow=False,
        font=dict(family='Arial', size=14, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    # Add Inception Date
    fig.add_annotation(
        x=0.02, y=0.889,
        text=f'INCEPTION DATE: {acc_start_date}',
        showarrow=False,
        font=dict(family='Arial', size=14, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    # ADD INVESTMENT OBJECTIVE TITLE:
    fig.add_annotation(
        x=0.02, y=0.86,
        text=f"<span style='text-decoration:underline;'>INVESTMENT OBJECTIVE</span>:",
        showarrow=False,
        font=dict(family='Arial', size=14, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    # ADD INVESTMENT OBJECTIVE CONTENT:
    fig.add_annotation(
        x=0.02, y=0.845,
        text=f"To achieve greater than average market return with customized<br>baskets based on the client's risk profile and objectives.",
        showarrow=False,
        align='left',
        font=dict(family='Arial', size=12, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )

    # ADD RETURNS STATEMENT:
    fig.add_annotation(
        x=0.02, y=0.635,
        text=f"Portfolio returns are after advisory fees and other expenses.",
        showarrow=False,
        align='left',
        font=dict(family='Arial', size=12, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )


    # ADD MANAGER DETAILS:
    fig.add_annotation(
        x=0.015, y=0.02,
        text=f"plus91.co    parth@plus91.co     +91-9930795667",
        showarrow=False,
        align='left',
        font=dict(family='Arial', size=18, color='black'),
        yanchor='top',
        xanchor='left',
        bgcolor=None,
        opacity=1
    )
    
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)

    pdf_bytes = fig.to_image(format="pdf", engine="kaleido", scale=3)
    return pdf_bytes
