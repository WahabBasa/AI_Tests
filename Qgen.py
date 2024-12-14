from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import anthropic
import json
import base64
import PyPDF2
import logging
from io import BytesIO
from pathlib import Path
from flask import Flask, jsonify, request

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)

CORS(app)

# Load environment variables
load_dotenv()

# Set API key directly (for testing only - in production use environment variables)
os.environ['ANTHROPIC_API_KEY'] = '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'

# Initialize Anthropic client
client = anthropic.Anthropic(
    api_key=os.environ['ANTHROPIC_API_KEY']
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
QUIZ_FILE_PATH = PROJECT_ROOT / 'quiz_questions.json'


MAX_CHUNKS = 5
MAX_CHARS_PER_CHUNK = 10000

# Web Routes
@app.route('/')
def home():
    return render_template('testproj.html')

@app.route('/quiz')
def quiz():
    return render_template('Second_Page.html')

@app.route('/test')
def test():
    return render_template('Page3.html')

@app.route('/results')
def results():
    return render_template('Page4.html')

@app.route('/videos')
def videos():
    return render_template('Page5.html')

@app.route('/get-questions')
def get_questions():
    try:
        with open('quiz_questions.json', 'r') as file:
            return file.read(), 200, {'Content-Type': 'application/json'}
    except FileNotFoundError:
        return jsonify({"error": "Questions not found"}), 404
    
@app.route('/save-answers', methods=['POST'])
def save_answers():
    try:
        quiz_data = request.json
        with open('quiz_answers.json', 'w') as file:
            json.dump(quiz_data, file)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get-answers', methods=['GET'])
def get_answers():
    try:
        # Read answers from the file
        with open('quiz_answers.json', 'r') as file:
            answers = json.load(file)
        return jsonify(answers)
    except FileNotFoundError:
        return jsonify({"error": "No answers found"}), 404    

# Keep your existing PDF processing functions
def decode_base64_pdf(pdf_base64_content):
    try:
        if ',' in pdf_base64_content:
            pdf_base64_content = pdf_base64_content.split(',')[1]
        return base64.b64decode(pdf_base64_content)
    except Exception as e:
        logger.error(f"Error decoding PDF: {str(e)}")
        raise Exception("Invalid PDF format")

def extract_text_from_pdf(pdf_bytes):
    try:
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text_content = ""
        for page in pdf_reader.pages:
            text_content += page.extract_text() + "\n"
        return text_content
    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}")
        raise Exception("Could not extract text from PDF")

def split_text_into_chunks(text):
    chunks = []
    current_chunk = ""
    
    for paragraph in text.split('\n'):
        if len(current_chunk) + len(paragraph) < MAX_CHARS_PER_CHUNK:
            current_chunk += paragraph + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = paragraph + "\n"
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks[:MAX_CHUNKS]

def generate_questions_for_chunk(chunk):
    prompt = f"""Generate 2 multiple choice questions based on this text. Each question must include:
    - A clear question based on key concepts from the text
    - Four distinct and realistic options (A, B, C, D)
    - The correct answer letter
    - A brief explanation of why the answer is correct
        
    Text: {chunk}
        
    Format your response EXACTLY as this JSON:
    {{
        "questions": [
            {{
                "index": 1,
                "question": "Question text here?",
                "options": [
                    "A) First option",
                    "B) Second option", 
                    "C) Third option",
                    "D) Fourth option"
                ],
                "correct": "A",
                "explanation": "Explanation here"
            }}
        ]
    }}"""
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Add debug logging
        logger.info(f"API Response: {response.content[0].text}")
        
        # Parse response and validate format
        response_text = response.content[0].text
        try:
            # Find JSON block in response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                questions_data = json.loads(json_str)
                if "questions" in questions_data:
                    return questions_data["questions"]
            raise ValueError("Invalid response format")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON: {response_text}")
            raise Exception("Invalid response format from API")
            
    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        raise Exception("Failed to generate questions")
    
    
def save_questions(questions):
    try:
        with open(QUIZ_FILE_PATH, 'w') as f:
            json.dump({"questions": questions}, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving questions: {str(e)}")
        raise Exception("Failed to save questions")

@app.route('/process-pdf', methods=['POST', 'OPTIONS'])
def process_pdf():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        if not request.is_json:
            return jsonify({"status": "error", "error": "Content-Type must be application/json"}), 415
            
        if not request.json or 'content' not in request.json:
            return jsonify({"status": "error", "error": "No PDF content provided"}), 400

        # Clean up existing questions file
        if QUIZ_FILE_PATH.exists():
            QUIZ_FILE_PATH.unlink()

        # Process PDF
        pdf_base64 = request.json['content']
        pdf_bytes = decode_base64_pdf(pdf_base64)
        logger.info("PDF decoded successfully")

        text_content = extract_text_from_pdf(pdf_bytes)
        if not text_content.strip():
            raise Exception("No text content found in PDF")
        logger.info("Text extracted successfully")

        text_chunks = split_text_into_chunks(text_content)
        logger.info(f"Split into {len(text_chunks)} chunks")
        
        # Generate and save questions
        all_questions = []
        for i, chunk in enumerate(text_chunks, 1):
            logger.info(f"Processing chunk {i}/{len(text_chunks)}")
            chunk_questions = generate_questions_for_chunk(chunk)
            all_questions.extend(chunk_questions)
        
        save_questions(all_questions)
        logger.info(f"Successfully generated and saved {len(all_questions)} questions")
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        error_message = str(e) if str(e) else "An unexpected error occurred"
        logger.error(f"Process failed: {error_message}")
        return jsonify({
            "status": "error",
            "error": error_message
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)