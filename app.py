import requests
import json
import os

from duckduckgo_search import DDGS
import streamlit as st
import streamlit_extras
from streamlit_extras.row import row
from openai import OpenAI


solar_llm = OpenAI(
    api_key=st.secrets["SOLAR_API_KEY"],
    base_url="https://api.upstage.ai/v1/solar",
)

solar_model = "solar-1-mini-chat"


def get_search_query(query):
    chat_completion = solar_llm.chat.completions.create(
        model=solar_model,
        messages=[
            {
                "role": "user",
                "content": "Extract good search keywords from user input. Write in json format.",
            },
            {"role": "user", "content": "My windows is broken how to fix it?"},
            {"role": "assistant", "content": '{"search": "fixing broken window"}'},
            {"role": "user", "content": "I am hungray. Best place to eay in New York?"},
            {"role": "assistant", "content": '{"search": "New York Resturent"}'},
            {"role": "user", "content": query},
        ],
    )

    # parse content in json format
    try:
        json_query = json.loads(chat_completion.choices[0].message.content)
        return json_query.get("search", query)
    except:
        return query


def news(query: str):
    """Fetch news articles and process their contents."""
    API_KEY = st.secrets["NEWSAPI_KEY"]  # Fetch API key from environment variable
    base_url = "https://newsapi.org/v2/everything"

    params = {
        "q": query,
        "sortBy": "publishedAt",
        "apiKey": API_KEY,
        "language": "en",
        "pageSize": 5,
    }

    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        return "Failed to retrieve news."

    articles = response.json().get("articles", [])
    return articles


# DDGsearch
def search(query):
    with DDGS() as ddgs:
        results = [r for r in ddgs.text(query, max_results=5)]

    return results


def show_search_results(search_results):
    st.markdown("*Search Results*")
    search_row = row(len(search_results), vertical_align="center")
    for article in search_results:
        search_row.link_button(
            "🌐 " + article["title"],
            article["href"],
            use_container_width=True,
        )


def show_news_articles(news_articles):
    if len(news_articles) == 0:
        return

    st.markdown("*News Results*")
    news_row = row(len(news_articles), vertical_align="center")
    for article in news_articles:
        news_row.link_button(
            "📰 " + article["title"],
            article["url"],
            use_container_width=True,
        )


def perform_search(query):
    with st.chat_message("user"):
        search_query = get_search_query(query)
        st.markdown(f"Search for {query} → `{search_query}`")

        search_results = search(search_query)
        show_search_results(search_results)
        # search_fill_content(search_results)

        news_articles = news(search_query)
        show_news_articles(news_articles)
        # news_fill_content(news_articles)

    st.session_state.messages.append(
        {
            "role": "user",
            "content": query,
            "search_query": search_query,
            "news_articles": news_articles,
            "search_results": search_results,
        }
    )

    final_prompt = f"""Provide a comprehensive answer and get straight to the point to answer the user's query.
Only talk about the search results and nothing else.\n\n
Reply in the language of the query. For example, if the query is in Korean, reply in Korean. If it's in English, reply in English.\n\n
Here are the search results for query '{query}':\n\n
---
SEARCH RESULTS:\n
{str(search_results)}\n\n
---
NEWS RESULTS:\n
{str(news_articles)}\n\n
"""

    with st.chat_message("assistant"):
        stream = solar_llm.chat.completions.create(
            model=solar_model,
            messages=[{"role": "user", "content": final_prompt}],
            stream=True,
        )
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    st.set_page_config(
        page_title="Solar Mini Search",
        page_icon="🌞",
    )
    st.title("🌞 Solar Mini Search")
    st.write("Ask me anything and I will find the best results for you.")
    st.write(
        "Want to make something similar? Visit https://console.upstage.ai to get your Solar API key."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Show previous messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "user":
                show_search_results(message["search_results"])
                show_news_articles(message["news_articles"])

    # Get user input and perform search
    if query := st.chat_input("Search query"):
        perform_search(query)
