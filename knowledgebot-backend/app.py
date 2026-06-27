from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.gemini_service import get_response
from services.intent_service import detect_intent
from services.website_service import search_website

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "NNRG Backend Running"}


@app.get("/chat")
def chat(prompt: str):

    intent = detect_intent(prompt)

    if intent == "website":

        website_content = search_website(prompt)

        answer = get_response(
            f"""
Use ONLY the information below to answer.

Website Information:

{website_content}

Question:

{prompt}
"""
        )

    elif intent == "pdf":

        answer = "PDF RAG is under development."

    else:

        answer = get_response(prompt)

    return {"response": answer}