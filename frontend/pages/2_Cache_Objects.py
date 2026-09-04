import streamlit as st
import pandas as pd

from frontend.services.api_client import get_cache_objects


st.title("Cache Objects")

st.write("Cached objects and their statistics")

objects = get_cache_objects()

df = pd.DataFrame(objects)

st.subheader("Cached Objects")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
)


st.subheader("Top Valuable Objects")

top_objects = sorted(
    objects,
    key=lambda x: x["score"],
    reverse=True,
)

for obj in top_objects:
    st.write(
        f"**{obj['key']}** — "
        f"Score: {obj['score']} | "
        f"Accesses: {obj['access_count']}"
    )