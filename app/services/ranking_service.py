def sort_top_places(df):
    if "rating" in df.columns and "visitors" in df.columns:
        return df.sort_values(
            by=["rating", "visitors"],
            ascending=False
        )

    return df


def sort_budget_places(df):
    if "price_level" in df.columns:
        return df[df["price_level"] == "low"]

    return df