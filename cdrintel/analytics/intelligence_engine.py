import pandas as pd


# =====================================================
# REQUIRED COLUMN NAMES IN YOUR CDR DATA
# =====================================================
# msisdn      -> caller number
# other_party -> receiver number
# duration    -> call duration (seconds)
# timestamp   -> full datetime of call

# You can rename columns before passing dataframe if needed.


# =====================================================
# MAIN ANALYSIS FUNCTION
# =====================================================
def analyze_cdr(df: pd.DataFrame):
    if df.empty:
        return {
            "summary": {},
            "top_communicators": pd.DataFrame(),
            "daily_activity": pd.DataFrame(),
            "peak_hours": pd.DataFrame(),
            "insights": ["No data available"]
        }

    df = df.copy()

    # Ensure timestamp is datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour

    # =================================================
    # CALL FREQUENCY & DURATION
    # =================================================
    total_calls = len(df)
    total_duration = df["duration"].sum()
    avg_duration = df["duration"].mean()

    # =================================================
    # TOP COMMUNICATORS
    # =================================================
    top_callers = (
        df.groupby("msisdn")
        .agg(
            total_calls=("msisdn", "count"),
            total_duration=("duration", "sum"),
            avg_duration=("duration", "mean")
        )
        .sort_values("total_calls", ascending=False)
        .head(10)
        .reset_index()
    )

    # =================================================
    # FIRST & LAST CALL PER DAY
    # =================================================
    daily_activity = (
        df.groupby("date")
        .agg(
            first_call=("timestamp", "min"),
            last_call=("timestamp", "max"),
            total_calls=("msisdn", "count")
        )
        .reset_index()
    )

    # =================================================
    # PEAK CALL HOURS
    # =================================================
    peak_hours = (
        df.groupby("hour")
        .size()
        .reset_index(name="call_count")
        .sort_values("call_count", ascending=False)
    )

    # =================================================
    # INTELLIGENCE INSIGHTS
    # =================================================
    insights = []

    if not top_callers.empty:
        top_number = top_callers.iloc[0]["msisdn"]
        insights.append(
            f"Top communicator is {top_number} with highest call frequency."
        )

    if not peak_hours.empty:
        peak_hour = int(peak_hours.iloc[0]["hour"])
        insights.append(
            f"Peak calling activity occurs around {peak_hour}:00 hours."
        )

    if avg_duration > 300:
        insights.append(
            "Average call duration is unusually high — possible close coordination."
        )

    if total_calls > 100:
        insights.append(
            "High call volume detected — subject shows heavy network interaction."
        )

    # =================================================
    # RETURN STRUCTURED INTELLIGENCE
    # =================================================
    return {
        "summary": {
            "total_calls": int(total_calls),
            "total_duration": float(total_duration),
            "avg_duration": float(avg_duration)
        },
        "top_communicators": top_callers,
        "daily_activity": daily_activity,
        "peak_hours": peak_hours,
        "insights": insights
    }
