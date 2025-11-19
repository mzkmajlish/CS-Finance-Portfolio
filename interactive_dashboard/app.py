import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(
    page_title="Interactive Personal Finance Dashboard",
    page_icon="💹",
    layout="wide",
)


def _month_ends(periods: int = 12) -> pd.DatetimeIndex:
    """Create deterministic month-end dates for charts."""
    return pd.date_range(end=pd.Timestamp.today().normalize(), periods=periods, freq="M")


def _build_transactions() -> pd.DataFrame:
    """Generate a synthetic but realistic set of transactions."""
    dates = _month_ends()

    income_streams = [
        {"label": "Graduate Research Stipend", "amounts": np.repeat(2800, len(dates))},
        {"label": "Part-time Analytics Consulting", "amounts": np.linspace(900, 1400, len(dates))},
        {"label": "Scholarship", "amounts": np.repeat(600, len(dates))},
    ]

    expense_categories = [
        {"label": "Rent", "base": 1400},
        {"label": "Groceries", "base": 420},
        {"label": "Transportation", "base": 180},
        {"label": "Education", "base": 300},
        {"label": "Entertainment", "base": 150},
        {"label": "Health & Fitness", "base": 120},
    ]

    records: list[dict[str, object]] = []

    for month, date in enumerate(dates, start=1):
        for stream in income_streams:
            records.append(
                {
                    "date": date,
                    "category": "Income",
                    "subcategory": stream["label"],
                    "amount": stream["amounts"][month - 1],
                }
            )

        for cat in expense_categories:
            seasonal = np.sin(month / 6 * np.pi) * 0.04
            inflation = 1 + 0.02 * (month - 1) / len(dates)
            amount = -(cat["base"] * inflation * (1 + seasonal))
            records.append(
                {
                    "date": date,
                    "category": "Expense",
                    "subcategory": cat["label"],
                    "amount": round(amount, 2),
                }
            )

        investing = -250 if month % 3 else -400
        records.append(
            {
                "date": date,
                "category": "Investment",
                "subcategory": "Index ETF DCA",
                "amount": investing,
            }
        )

    return pd.DataFrame.from_records(records)


def build_dashboard_data() -> dict[str, pd.DataFrame]:
    transactions = _build_transactions()
    transactions["month"] = transactions["date"].dt.to_period("M").dt.to_timestamp()

    cash_flow = (
        transactions.groupby("month")["amount"].sum().reset_index().rename(columns={"amount": "net_flow"})
    )

    expenses = transactions[transactions["category"] == "Expense"].copy()
    expense_summary = (
        expenses.groupby(["month", "subcategory"])["amount"].sum().abs().reset_index()
    )

    income_summary = (
        transactions[transactions["category"] == "Income"]
        .groupby(["month", "subcategory"])["amount"].sum()
        .reset_index()
    )

    return {
        "transactions": transactions,
        "cash_flow": cash_flow,
        "expenses": expenses,
        "expense_summary": expense_summary,
        "income_summary": income_summary,
    }


def project_net_worth(cash_flow: pd.DataFrame, starting_net_worth: float, annual_return: float) -> pd.DataFrame:
    monthly_rate = (1 + annual_return) ** (1 / 12) - 1
    balances = []
    balance = starting_net_worth

    for row in cash_flow.itertuples():
        balance += row.net_flow
        balance *= 1 + monthly_rate
        balances.append({"month": row.month, "net_worth": balance})

    return pd.DataFrame(balances)


def build_allocation_view(transactions: pd.DataFrame) -> pd.DataFrame:
    allocations = transactions.copy()
    allocations.loc[allocations["category"] == "Expense", "direction"] = "Outflows"
    allocations.loc[allocations["category"] == "Income", "direction"] = "Inflows"
    allocations.loc[allocations["category"] == "Investment", "direction"] = "Invested"
    return (
        allocations.groupby(["direction", "subcategory"])["amount"].sum().reset_index().sort_values("amount")
    )


def main() -> None:
    st.sidebar.header("Scenario Controls")
    starting_net_worth = st.sidebar.slider("Starting net worth", 10000, 80000, 30000, step=1000)
    annual_return = st.sidebar.slider("Annual return assumption", 0.0, 0.12, 0.06, step=0.01)
    highlight_category = st.sidebar.selectbox(
        "Focus category", ["All", "Rent", "Groceries", "Transportation", "Education", "Entertainment", "Health & Fitness"],
        index=0,
    )

    data = build_dashboard_data()

    cash_flow = data["cash_flow"]
    net_worth_projection = project_net_worth(cash_flow, starting_net_worth, annual_return)
    allocations = build_allocation_view(data["transactions"])

    monthly_surplus = cash_flow["net_flow"].mean()
    latest_net_worth = net_worth_projection["net_worth"].iloc[-1]

    st.title("Interactive Personal Finance Dashboard")
    st.caption("A finance + analytics dashboard for a Schulich student balancing research, consulting, and investing.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Projected net worth (12m)", f"${latest_net_worth:,.0f}", f"{annual_return*100:.0f}% return")
    col2.metric("Average monthly surplus", f"${monthly_surplus:,.0f}")
    col3.metric("Invested last 12m", f"${abs(data['transactions'][data['category']=='Investment']['amount'].sum()):,.0f}")

    overview_tab, spending_tab, allocation_tab = st.tabs(["Overview", "Spending", "Allocation"])

    with overview_tab:
        st.subheader("Cash flow and net worth")
        st.line_chart(net_worth_projection.set_index("month"), height=320)
        st.bar_chart(cash_flow.set_index("month"), height=220)

    with spending_tab:
        st.subheader("Expense detail")
        if highlight_category != "All":
            filtered = data["expense_summary"][data["expense_summary"]["subcategory"] == highlight_category]
        else:
            filtered = data["expense_summary"]

        st.area_chart(filtered.pivot(index="month", columns="subcategory", values="amount"), height=320)
        st.dataframe(
            data["expenses"][data["expenses"]["amount"] < 0]
            .assign(amount=lambda df: df["amount"].abs())
            .sort_values(["month", "amount"], ascending=[False, False])
            .rename(columns={"amount": "amount (abs)"}),
            use_container_width=True,
            height=340,
        )

    with allocation_tab:
        st.subheader("Sources and uses")
        st.bar_chart(allocations.pivot(index="subcategory", columns="direction", values="amount"), height=340)
        st.caption("Inflows and outflows are aggregated by category to highlight trade-offs between spending and investing.")


if __name__ == "__main__":
    main()
