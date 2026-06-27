def detect_intent(question):

    question = question.lower()

    website_keywords = [
        "nnrg",
        "college",
        "admission",
        "admissions",
        "course",
        "courses",
        "placement",
        "placements",
        "faculty",
        "department",
        "hostel",
        "transport",
        "library",
        "fees",
        "contact",
        "principal",
        "chairman",
        "campus",
    ]

    pdf_keywords = [
        "pdf",
        "document",
        "prospectus",
        "brochure",
    ]

    if any(word in question for word in pdf_keywords):
        return "pdf"

    if any(word in question for word in website_keywords):
        return "website"

    return "general"