import requests
from bs4 import BeautifulSoup


def search_website(question):

    url = "https://nnrg.edu.in"

    try:

        response = requests.get(url, timeout=10)

        soup = BeautifulSoup(response.text, "html.parser")

        text = soup.get_text(separator=" ", strip=True)

        return text[:8000]

    except Exception:

        return None