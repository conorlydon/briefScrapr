from ollama import chat

from models.project import ProjectSpecification


MODEL = "gpt-oss:20b"


def analyse_brief(text: str) -> ProjectSpecification:

    prompt = f"""
You are a software project requirements analyst.

Your task is to extract structured information from a college project brief.

IMPORTANT RULES:

1. Analyse the brief itself. Do not ask the user questions.
2. Do not give advice.
3. Do not suggest how the student should complete the project.
4. Do not write any implementation code.
5. Do not invent requirements.
6. Only include information that is explicitly stated or clearly required by the brief.
7. If something is not specified, use an empty list or a reasonable short description.
8. Break large requirements into individual requirements where appropriate.
9. Identify the programming languages and technologies explicitly required.
10. Identify the major components that the student will need to build.
11. Identify the final deliverables explicitly mentioned in the brief.

Return the project information according to the supplied JSON schema.

PROJECT BRIEF:

{text}
"""

    response = chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        format=ProjectSpecification.model_json_schema(),
    )

    return ProjectSpecification.model_validate_json(
        response.message.content
    )