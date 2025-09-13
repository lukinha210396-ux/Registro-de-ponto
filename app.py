from flask import Flask, render_template, request, redirect, url_for, session, Response
import sqlite3
from datetime import datetime
import os

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    senha TEXT NOT NULL,
                    tipo TEXT NOT NULL
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pontos (
                latitude TEXT,
                longitude TEXT,
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER,
                    horario TEXT,
                    tipo TEXT,
                    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
                )""")
    # Create a default admin if none exists
    c.execute("SELECT COUNT(*) as cnt FROM usuarios WHERE tipo='admin'")
    row = c.fetchone()
    if row['cnt'] == 0:
        c.execute("INSERT INTO usuarios (nome, senha, tipo) VALUES (?, ?, ?)", ("admin", "admin", "admin"))
    conn.commit()
    conn.close()

# App setup
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)
init_db()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        senha = request.form["senha"].strip()

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE nome=? AND senha=?", (nome, senha))
        user = c.fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["tipo"] = user["tipo"]
            session["nome"] = user["nome"]
            if user["tipo"] == "admin":
                return redirect(url_for("admin"))
            else:
                return redirect(url_for("funcionario"))
        else:
            return render_template("login.html", error="Usuário ou senha incorretos.")
    return render_template("login.html", error=None)

@app.route("/funcionario", methods=["GET", "POST"])
def funcionario():
    if "user_id" not in session or session.get("tipo") != "funcionario":
        return redirect(url_for("login"))

    message = None
    if request.method == "POST":
        tipo = request.form.get("tipo")
        horario = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO pontos (usuario_id, horario, tipo) VALUES (?, ?, ?)",
                  (session["user_id"], horario, tipo))
        conn.commit()
        conn.close()
        message = f"Ponto registrado: {tipo} em {horario}"

    # show recent registros do próprio funcionário
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT horario, tipo FROM pontos WHERE usuario_id = ? ORDER BY horario DESC LIMIT 10", (session["user_id"],))
    registros = c.fetchall()
    conn.close()

    return render_template("funcionario.html", nome=session.get("nome"), message=message, registros=registros)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "user_id" not in session or session.get("tipo") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    c = conn.cursor()

    # Criar novo funcionário via formulário
    create_msg = None
    if request.method == "POST" and request.form.get("action") == "criar":
        novo_nome = request.form.get("nome").strip()
        nova_senha = request.form.get("senha").strip()
        if not novo_nome or not nova_senha:
            create_msg = "Nome e senha são obrigatórios."
        else:
            try:
                c.execute("INSERT INTO usuarios (nome, senha, tipo) VALUES (?, ?, ?)", (novo_nome, nova_senha, "funcionario"))
                conn.commit()
                create_msg = f"Funcionário '{novo_nome}' criado com sucesso."
            except Exception as e:
                create_msg = "Erro ao criar usuário (talvez já exista)."

    # Buscar registros (todos)
    c.execute("""SELECT p.id, u.nome as funcionario, p.horario, p.tipo
                 FROM pontos p JOIN usuarios u ON p.usuario_id = u.id
                 ORDER BY p.horario DESC LIMIT 500""")
    registros = c.fetchall()

    # Listar funcionarios
    c.execute("SELECT id, nome FROM usuarios WHERE tipo='funcionario' ORDER BY nome")
    funcionarios = c.fetchall()

    conn.close()
    return render_template("admin.html", registros=registros, funcionarios=funcionarios, create_msg=create_msg)

@app.route("/exportar")
def exportar():
    if "user_id" not in session or session.get("tipo") != "admin":
        return redirect(url_for("login"))
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""SELECT u.nome, p.horario, p.tipo 
                 FROM pontos p JOIN usuarios u ON p.usuario_id = u.id
                 ORDER BY p.horario DESC""")
    registros = c.fetchall()
    conn.close()

    def generate():
        yield "Funcionario,Horario,Tipo\n"
        for r in registros:
            yield f'{r["nome"]},{r["horario"]},{r["tipo"]}\n'

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=registros.csv"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Safe page to add time manually (optional)
@app.route("/admin/add_time", methods=["POST"])
def admin_add_time():
    if "user_id" not in session or session.get("tipo") != "admin":
        return redirect(url_for("login"))
    usuario_id = request.form.get("usuario_id")
    tipo = request.form.get("tipo")
    if usuario_id and tipo:
        horario = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO pontos (usuario_id, horario, tipo) VALUES (?, ?, ?)",
                  (usuario_id, horario, tipo))
        conn.commit()
        conn.close()
    return redirect(url_for("admin"))

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
