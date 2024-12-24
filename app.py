from flask import Flask, render_template, request, redirect, url_for
from db import create_connection

app = Flask(__name__)

# Главная страница
@app.route("/")
def index():
    connection = create_connection()
    logs = []
    if connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM logs ORDER BY created_at DESC")
            logs = cursor.fetchall()
        connection.close()
    return render_template("index.html", logs=logs)

# Добавление фразы через Flask
@app.route("/add_phrase", methods=["POST"])
def add_phrase():
    new_phrase = request.form["phrase"]
    connection = create_connection()
    if connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO phrases (phrase) VALUES (%s)", (new_phrase,))
            connection.commit()
        connection.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
