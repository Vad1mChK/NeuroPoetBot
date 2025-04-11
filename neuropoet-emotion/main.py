# app.py
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# TODO Replace with actual implementations
# Sample data
books = [
    {"id": 1, "title": "The Great Gatsby", "author": "F. Scott Fitzgerald"},
    {"id": 2, "title": "1984", "author": "George Orwell"}
]

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Book API!", "status": "success"})

@app.route('/api/books', methods=['GET'])
def get_books():
    return jsonify({"books": books})

@app.route('/api/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    book = next((b for b in books if b['id'] == book_id), None)
    if book:
        return jsonify(book)
    return jsonify({"error": "Book not found"}), 404

@app.route('/api/books', methods=['POST'])
def add_book():
    data = request.get_json()
    if not data or 'title' not in data or 'author' not in data:
        return jsonify({"error": "Missing required fields"}), 400

    new_book = {
        "id": len(books) + 1,
        "title": data['title'],
        "author": data['author']
    }
    books.append(new_book)
    return jsonify(new_book), 201

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', False))