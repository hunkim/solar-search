import requests
import json
import os

from duckduckgo_search import DDGS
import streamlit as st
import streamlit_extras
from streamlit_extras.add_vertical_space import add_vertical_space
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
                "role": "system",
                "content": "You are a search query generator. Find the best search keywords.",
            },
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


def answer_verifier(query, context, answer):
    chat_completion = solar_llm.chat.completions.create(
        model=solar_model,
        messages=[
            {
                "role": "system",
                "content": "Your answer verifier. Verify the answer is correct or incorrect based on the context. The answer should be always from the context.",
            },
            {
                "role": "user",
                "content": """Query: How many dogs do we have?
---
Context: We have 3 dogs. They are all golden retrievers. They are very friendly.
---
Answer: I have three dogs and they are golden retrievers.
             """,
            },
            {"role": "assistant", "content": '{"verification_result": "correct"}'},
            {
                "role": "user",
                "content": """Query: Why sky is blue?
---
Context: Sky is blue because of Rayleigh scattering. The sky is blue because of the way the Earth's atmosphere scatters sunlight.
---
Answer: Sky is blue because of people like blue colors.
             """,
            },
            {"role": "assistant", "content": '{"verification_result": ""}'},
            {
                "role": "user",
                "content": """Query: What is the capital of France?
--- 
Context: The capital of France is Paris. The Eiffel Tower is in Paris. Food in Paris is good.
---
Answer: The capital of France is Seoul. I love seoul.
             """,
            },
            {"role": "assistant", "content": '{"verification_result": "incorrect"}'},
            {
                "role": "user",
                "content": f"""Query: {query}\n---\nContext: {context}\n---\nAnswer: {answer}
             """,
            },
        ],
    )

    # parse content in json format
    try:
        json_query = json.loads(chat_completion.choices[0].message.content)
        return json_query.get("verification_result", query)
    except:
        return "not sure"


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


import requests

def you_search(query):
    headers = {"X-API-Key": st.secrets["YDC_API_KEY"]}
    params = {"query": query}
    return requests.get(
        f"https://api.ydc-index.io/search?query={query}",
        params=params,
        headers=headers,
    ).json()['hits'][:5]



def show_search_results(search_results):
    if not search_results or len(search_results) == 0:
        return

    st.markdown("*Search Results*")
    search_row = row(len(search_results), vertical_align="center")
    for article in search_results:
        search_row.link_button(
            "🌐 " + article["title"],
            article["url"],
            use_container_width=True,
        )


def show_news_articles(news_articles):
    if not news_articles or len(news_articles) == 0:
        return

    st.markdown("*News Results*")
    news_row = row(len(news_articles), vertical_align="center")
    for article in news_articles:
        news_row.link_button(
            "📰 " + article["title"],
            article["url"],
            use_container_width=True,
        )


def find_answer(query, search_results, news_articles):
    context = f"""
---
SEARCH RESULTS:\n
{str(search_results)[:2000]}\n\n
---
NEWS RESULTS:\n
{str(news_articles)[:1000]}\n\n
"""
    final_prompt = f"""Provide a comprehensive answer and get straight to the point to answer the question.
Only use the results to answer. Do not use any other knowledges.\n\n
Reply in the language of the query. For example, if the query is in Korean, reply in Korean. If it's in English, reply in English.\n\n
Here are the search results for question '{query}':\n\n
{context}
"""

    with st.chat_message("assistant"):
        stream = solar_llm.chat.completions.create(
            model=solar_model,
            messages=[{"role": "user", "content": final_prompt}],
            stream=True,
        )
        response = st.write_stream(stream)
    return response, context


def perform_search(query):
    with st.chat_message("user"):
        search_query = get_search_query(query)
        st.markdown(f"Search for {query} → `{search_query}`")

        search_results = you_search(search_query)
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

    verify_result = "not sure"
    response = ""
    for attempt in range(3):
        response, context = find_answer(query, search_results, news_articles)
        with st.spinner(f"Verifying the answer ({attempt})..."):
            verify_result = answer_verifier(query, context, response)
        if verify_result == "correct":
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "✅ " + response,
                }
            )
            st.success(f"The answer is {verify_result}")

            break
        st.warning(f"It seems the answer is {verify_result}. Attempting again...")
        st.rerun()
        
    if verify_result != "correct":
        st.error("I am not sure about the answer. Please ask me another question.")
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"I am not sure about the answer. Please ask me another question.\n\n🤷🤷‍♀️ Answer: {response}",
            }
        )


if __name__ == "__main__":
    st.set_page_config(
        page_title="Solar Mini Search",
        page_icon="🌞",
    )
    st.title("🌞 Solar Mini Search")
    st.write("Ask me anything and I will find the best results for you.")
    st.write(
        """Want to make something similar? 
        Visit https://console.upstage.ai to get your Solar API key.
        Check out the source code at https://github.com/hunkim/solar-search.
        """
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
    elif len(st.session_state.messages) == 0:
        sample_fun_questions = [
            "Tell me about upstage.ai",
            "Why we love You.com",
            "What is better, Python or Java?",
            "What is the meaning of life?",
            "What is LLM, GPT, SolarLLM?",
            "Best Place to visit in Korea?",
            "Is Kimchi good for health?",
        ]

        add_vertical_space(3)

        for question in sample_fun_questions:
            if st.button(question):
                perform_search(question)
                st.rerun()
