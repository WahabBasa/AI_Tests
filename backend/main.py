from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import anthropic
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Set up Jinja2 templates
templates = Jinja2Templates(directory="../frontend")

api_key = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

prompt = """
Generate a detailed quiz based on the content of this PDF. The quiz should have 5 questions. 
Each question should be specific, testing understanding of key concepts or facts from the PDF.
Return the result as a JSON object with an array of questions, where each question has:
- question_text: The detailed text of the question

Here's the PDF content:
{pdf_content}

Respond only with the JSON object, no additional text.
"""

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("Page1/Page1.html", {"request": request})

@app.get("/quiz", response_class=HTMLResponse)
async def show_quiz(request: Request):
    return templates.TemplateResponse("Page2/Page2.html", {"request": request})

@app.post("/generate-quiz", response_class=HTMLResponse)
async def generate_quiz(request: Request, file: UploadFile = File(...)):
    pdf_content = await file.read()
    pdf_text = pdf_content.decode('utf-8', errors='ignore')
    
    full_prompt = prompt.format(pdf_content=pdf_text)

    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=1500,
        messages=[
            {"role": "user", "content": full_prompt}
        ]
    )

    json_match = re.search(r'\{.*\}', response.content[0].text, re.DOTALL)
    if json_match:
        json_str = json_match.group()
        quiz_details = json.loads(json_str)
    else:
        print("Couldn't find JSON in Claude's response")
        quiz_details = {"questions": [{"question_text": "Failed to generate question"} for _ in range(5)]}

    return templates.TemplateResponse("Page2/Page2.html", {"request": request, "questions": quiz_details['questions']})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)