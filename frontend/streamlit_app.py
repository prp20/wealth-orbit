"""Streamlit dashboard for portfolio review and transaction entry."""

import os
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_SERVICE_ROOT = PROJECT_ROOT / "portfolio-service"
if str(PORTFOLIO_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_SERVICE_ROOT))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, joinedload

from backend.models import Asset, AssetType, Holding, Portfolio, Transaction, TransactionType, User
from backend.reference_service import mutual_funds, stock_categories, stocks
from scripts.import_transactions import import_file


def indian_number(value, decimals: int = 2) -> str:
    """Format a number using Indian comma grouping and fixed decimals."""
    number = Decimal(str(value))
    sign = "-" if number < 0 else ""
    text = f"{abs(number):.{decimals}f}"
    whole, fraction = text.split(".")
    if len(whole) > 3:
        last_three = whole[-3:]
        prefix = whole[:-3]
        groups = []
        while prefix:
            groups.insert(0, prefix[-2:])
            prefix = prefix[:-2]
        whole = ",".join(groups + [last_three])
    return f"{sign}{whole}.{fraction}"


def indian_currency(value) -> str:
    return f"₹{indian_number(value)}"

load_dotenv()


@st.cache_resource
def get_engine():
    url = os.getenv("PORTFOLIO_SQLITE_URL", "sqlite:///./portfolio-service/portfolio.db")
    return create_engine(url, pool_pre_ping=True)


def load_portfolios(session: Session):
    return session.scalars(select(Portfolio).options(joinedload(Portfolio.user)).order_by(Portfolio.created_at)).all()


def portfolio_snapshot(session: Session, portfolio_id):
    holdings = session.scalars(select(Holding).options(joinedload(Holding.asset)).where(Holding.portfolio_id == portfolio_id).order_by(Holding.updated_at.desc())).all()
    transactions = session.scalars(select(Transaction).options(joinedload(Transaction.asset)).where(Transaction.portfolio_id == portfolio_id).order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())).all()
    return holdings, transactions


def holdings_frame(holdings):
    return pd.DataFrame([
        {"Asset": h.asset.asset_name, "Class": h.asset.investment_class, "Type": h.asset.asset_type.value, "Units": indian_number(h.current_quantity), "Invested amount": indian_currency(h.invested_amount), "Average cost": indian_currency(h.average_cost_per_unit), "Status": h.asset.status.value}
        for h in holdings
    ])


def transactions_frame(transactions):
    return pd.DataFrame([
        {"Date": t.transaction_date, "Asset": t.asset.asset_name, "Type": t.transaction_type.value, "Units": indian_number(t.quantity), "Price / unit": indian_currency(t.price_per_unit), "Amount": indian_currency(t.transaction_amount), "Transaction ID": str(t.transaction_id)}
        for t in transactions
    ])


def add_transaction(session: Session, portfolio_id, asset_id, transaction_type, quantity, price, transaction_date):
    from backend.services import InsufficientHoldingsError
    holding = session.scalar(select(Holding).where(Holding.portfolio_id == portfolio_id, Holding.asset_id == asset_id).with_for_update())
    if quantity <= 0 or price <= 0:
        raise ValueError("Quantity and price must be positive")
    amount = quantity * price
    if transaction_type == TransactionType.SELL:
        if holding is None or holding.current_quantity < quantity:
            raise InsufficientHoldingsError("Insufficient holdings for this sell")
        remaining = holding.current_quantity - quantity
        holding.invested_amount -= holding.average_cost_per_unit * quantity
        if remaining == 0:
            session.delete(holding)
        else:
            holding.current_quantity = remaining
    elif holding is None:
        session.add(Holding(portfolio_id=portfolio_id, asset_id=asset_id, current_quantity=quantity, invested_amount=amount, average_cost_per_unit=amount / quantity))
    else:
        holding.current_quantity += quantity
        holding.invested_amount += amount
        holding.average_cost_per_unit = holding.invested_amount / holding.current_quantity
    session.add(Transaction(portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=transaction_type, quantity=quantity, price_per_unit=price, transaction_amount=amount, transaction_date=transaction_date))
    session.commit()


st.set_page_config(page_title="Portfolio Management", page_icon="📈", layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #101923; }
[data-testid="stSidebar"] > div:first-child { padding: 1.6rem 1.15rem; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] p,
[data-testid="stSidebar"] label { color: #edf5f2; }
.side-brand { padding: .15rem 0 1.4rem; border-bottom: 1px solid #2a3a46; }
.side-brand .mark { color: #75e0b3; font-size: 1.5rem; font-weight: 700; letter-spacing: -.04em; }
.side-brand .sub { color: #91a6ad; font-size: .74rem; margin-top: .25rem; }
.side-card { background: #182631; border: 1px solid #2a3a46; border-radius: 12px; padding: .85rem .9rem; margin: 1rem 0; }
.side-card .eyebrow { color: #83a0a4; font-size: .68rem; text-transform: uppercase; letter-spacing: .08em; }
.side-card .name { color: #f3faf7; font-size: .98rem; font-weight: 600; margin-top: .35rem; }
.side-card .meta { color: #9fb2b5; font-size: .72rem; margin-top: .2rem; }
.side-rule { height: 1px; background: #2a3a46; margin: 1.1rem 0; }
</style>
""", unsafe_allow_html=True)
st.title("Portfolio Management")
st.caption("Review holdings, trace every portfolio change, and record transactions.")

try:
    with Session(get_engine()) as session:
        portfolios = load_portfolios(session)
        if not portfolios:
            st.info("No portfolios are available yet. Create a user and portfolio before opening the dashboard.")
            st.stop()
        accessible = [p for p in portfolios if p.user and p.user.deleted_at is None]
        labels = {p.portfolio_id: f"Portfolio {i + 1:02d}" for i, p in enumerate(accessible)}
        if not labels:
            st.warning("All users are soft-deleted, so there are no accessible portfolios.")
            st.stop()
        st.sidebar.markdown("<div class='side-brand'><div class='mark'>folio / view</div><div class='sub'>Personal wealth, clearly arranged.</div></div>", unsafe_allow_html=True)
        selected_portfolio = accessible[0]
        st.sidebar.markdown(f"<div class='side-card'><div class='eyebrow'>Account holder</div><div class='name'>{selected_portfolio.user.full_name or 'Portfolio owner'}</div><div class='meta'>{selected_portfolio.user.pan or 'Local portfolio'}<br>{labels[selected_portfolio.portfolio_id]}</div></div>", unsafe_allow_html=True)
        st.sidebar.markdown("<div class='side-rule'></div><div class='eyebrow'>Choose a portfolio</div>", unsafe_allow_html=True)
        # Re-render the selector after the visual context so it reads as a control panel.
        selected_id = st.sidebar.selectbox("Portfolio", list(labels), format_func=lambda value: labels[value], key="portfolio_selector", label_visibility="visible")
        st.sidebar.markdown("<div class='side-rule'></div><div class='eyebrow'>Update portfolio data</div>", unsafe_allow_html=True)
        uploaded_file = st.sidebar.file_uploader("Drop an order-history Excel file here", type=["xlsx", "xls"], label_visibility="visible")
        import_mode = st.sidebar.radio("Import mode", ["Append new rows", "Update this file"], help="Append adds unseen rows. Update rebuilds transactions previously imported from this file.")
        if uploaded_file and st.sidebar.button("Import transactions", type="primary", use_container_width=True):
            suffix = Path(uploaded_file.name).suffix or ".xlsx"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
                temporary.write(uploaded_file.getvalue())
                temporary_path = Path(temporary.name)
            try:
                import_file(temporary_path, os.getenv("PORTFOLIO_SQLITE_URL", "sqlite:///./portfolio-service/portfolio.db"), "append" if import_mode.startswith("Append") else "update", source_name=uploaded_file.name)
                st.sidebar.success("Portfolio data imported.")
                st.rerun()
            except Exception as exc:
                st.sidebar.error(str(exc))
            finally:
                temporary_path.unlink(missing_ok=True)
        holdings, transactions = portfolio_snapshot(session, selected_id)

        total_invested = sum((h.invested_amount for h in holdings), Decimal("0"))
        total_units = sum((h.current_quantity for h in holdings), Decimal("0"))
        equity_invested = sum((h.invested_amount for h in holdings if h.asset.investment_class == "EQUITY"), Decimal("0"))
        debt_invested = sum((h.invested_amount for h in holdings if h.asset.investment_class == "DEBT"), Decimal("0"))
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Invested amount", indian_currency(total_invested))
        c2.metric("Equity", indian_currency(equity_invested))
        c3.metric("Debt", indian_currency(debt_invested))
        c4.metric("Assets held", len(holdings))
        c5.metric("Total units", indian_number(total_units))

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Current holdings", "Transaction history", "Record transaction", "Mutual funds", "Stocks"])
        with tab1:
            if holdings:
                st.dataframe(holdings_frame(holdings), use_container_width=True, hide_index=True)
                st.caption("Market value is not shown because live NAV or market-price data is outside the current scope.")
            else:
                st.info("This portfolio has no active holdings.")
        with tab2:
            if transactions:
                st.dataframe(transactions_frame(transactions), use_container_width=True, hide_index=True)
            else:
                st.info("No transactions have been recorded.")
        with tab3:
            assets = session.scalars(select(Asset).where(Asset.status == "ACTIVE").order_by(Asset.asset_name)).all()
            if not assets:
                st.info("No active assets are available.")
            else:
                with st.form("transaction_form"):
                    asset_id = st.selectbox("Asset", [a.asset_id for a in assets], format_func=lambda value: next(a.asset_name for a in assets if a.asset_id == value))
                    tx_type = st.radio("Transaction type", [TransactionType.BUY, TransactionType.SELL], horizontal=True, format_func=lambda value: value.value)
                    quantity = st.number_input("Quantity", min_value=0.01, value=1.0, format="%.2f")
                    price = st.number_input("Price per unit", min_value=0.01, value=1.0, format="%.2f")
                    tx_date = st.date_input("Transaction date", value=date.today())
                    submitted = st.form_submit_button("Save transaction", type="primary")
                if submitted:
                    try:
                        add_transaction(session, selected_id, asset_id, tx_type, Decimal(str(quantity)), Decimal(str(price)), tx_date)
                        st.success("Transaction saved and holding aggregate updated.")
                        st.rerun()
                    except Exception as exc:
                        session.rollback()
                        st.error(str(exc))
        with tab4:
            st.subheader("Mutual-fund reference list")
            fund_search = st.text_input("Search schemes", key="fund_search")
            fund_categories = mutual_funds()["category_name"].dropna().unique().tolist()
            fund_category = st.selectbox("Category", ["All", *sorted(fund_categories)], key="fund_category")
            try:
                funds = mutual_funds(fund_search, fund_category)
                st.caption(f"{len(funds):,} schemes from Supabase")
                st.dataframe(funds, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Could not load mutual-fund reference data: {exc}")
        with tab5:
            st.subheader("Stock reference list")
            stock_search = st.text_input("Search symbols or companies", key="stock_search")
            sectors = ["All", *stock_categories()]
            stock_sector = st.selectbox("Sector", sectors, key="stock_sector")
            try:
                stock_rows = stocks(stock_search, stock_sector)
                st.caption(f"{len(stock_rows):,} stocks from Supabase")
                st.dataframe(stock_rows, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Could not load stock reference data: {exc}")
except Exception as exc:
    st.error("Could not load the portfolio database.")
    st.exception(exc)
