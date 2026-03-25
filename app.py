from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "erp.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "erp-prototipo-secret-key"
app.config["DATABASE"] = str(DATABASE)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error: Exception | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def format_currency(value: float | int | None) -> str:
    number = float(value or 0)
    text = f"{number:,.2f}"
    return f"R$ {text.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def format_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return value


app.jinja_env.filters["brl"] = format_currency
app.jinja_env.filters["brdate"] = format_date


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    document TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    city TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sku TEXT UNIQUE NOT NULL,
    price REAL NOT NULL,
    cost REAL NOT NULL,
    stock_qty INTEGER NOT NULL DEFAULT 0,
    min_stock INTEGER NOT NULL DEFAULT 0,
    category TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total REAL NOT NULL,
    sale_date TEXT NOT NULL,
    payment_status TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY(client_id) REFERENCES clients(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS financial_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    amount REAL NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL,
    category TEXT,
    related_sale_id INTEGER,
    notes TEXT,
    FOREIGN KEY(related_sale_id) REFERENCES sales(id) ON DELETE SET NULL
);
"""


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.commit()


def seed_db() -> None:
    db = get_db()
    has_users = db.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    if has_users:
        return

    users = [
        ("carlos", generate_password_hash("demo", method="pbkdf2:sha256"), "Carlos Faria", "admin"),
        ("clawdinha", generate_password_hash("demo", method="pbkdf2:sha256"), "Clawdinha", "financeiro"),
        ("donaluci", generate_password_hash("demo", method="pbkdf2:sha256"), "Dona Luci", "financeiro"),
    ]
    db.executemany(
        """
        INSERT INTO users (username, password_hash, full_name, role)
        VALUES (?, ?, ?, ?)
        """,
        users,
    )

    today = date.today()
    current_month = today.replace(day=5)
    prev_month = (today.replace(day=1) - timedelta(days=4)).replace(day=18)

    clients = [
        ("Mercadinho Beira Rio", "12.345.678/0001-90", "compras@beirario.com", "(11) 99888-1001", "Campinas", today.isoformat()),
        ("Distribuidora Sol Nascente", "45.987.321/0001-12", "financeiro@solnascente.com", "(11) 99888-1002", "São Paulo", today.isoformat()),
        ("Bistrô da Praça", "78.654.321/0001-44", "contato@bistropraca.com", "(19) 99888-1003", "Valinhos", today.isoformat()),
    ]
    db.executemany(
        """
        INSERT INTO clients (name, document, email, phone, city, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        clients,
    )

    products = [
        ("Chopp Pilsen 30L", "CHO-30-PIL", 420.00, 300.00, 8, 5, "Bebidas", today.isoformat()),
        ("Gin London 750ml", "GIN-750-LON", 82.90, 51.00, 3, 4, "Destilados", today.isoformat()),
        ("Xarope Grenadine 1L", "XAR-1L-GRE", 24.50, 13.20, 15, 6, "Insumos", today.isoformat()),
        ("Taça Gin 600ml", "TAC-600-GIN", 18.90, 9.80, 22, 10, "Acessórios", today.isoformat()),
    ]
    db.executemany(
        """
        INSERT INTO products (name, sku, price, cost, stock_qty, min_stock, category, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        products,
    )

    stock_movements = [
        (1, "entrada", 10, "Carga inicial de barris", current_month.isoformat()),
        (2, "entrada", 6, "Reposição fornecedor", current_month.isoformat()),
        (3, "entrada", 20, "Estoque inicial", current_month.isoformat()),
        (4, "entrada", 24, "Compra inicial", current_month.isoformat()),
        (2, "saida", 3, "Vendas balcão", today.isoformat()),
    ]
    db.executemany(
        """
        INSERT INTO stock_movements (product_id, movement_type, quantity, note, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        stock_movements,
    )

    sales = [
        (1, 1, 2, 420.00, 840.00, current_month.isoformat(), "receber", "Pedido mensal"),
        (2, 2, 1, 82.90, 82.90, current_month.isoformat(), "pago", "Reposição urgente"),
        (3, 3, 4, 18.90, 75.60, prev_month.isoformat(), "receber", "Evento especial"),
    ]
    db.executemany(
        """
        INSERT INTO sales (client_id, product_id, quantity, unit_price, total, sale_date, payment_status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sales,
    )

    financial_entries = [
        ("Recebimento Mercadinho Beira Rio", "receber", 840.00, (today + timedelta(days=7)).isoformat(), "pendente", "Vendas", 1, "Boleto 7 dias"),
        ("Recebimento Bistrô da Praça", "receber", 75.60, (today + timedelta(days=10)).isoformat(), "pendente", "Vendas", 3, "Venda evento"),
        ("Compra fornecedor bebidas", "pagar", 1250.00, (today + timedelta(days=5)).isoformat(), "pendente", "Compras", None, "Lote mensal"),
        ("Internet escritório", "pagar", 149.90, today.isoformat(), "pago", "Despesas fixas", None, "Competência atual"),
    ]
    db.executemany(
        """
        INSERT INTO financial_entries
        (description, entry_type, amount, due_date, status, category, related_sale_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        financial_entries,
    )

    db.commit()


def bootstrap_db() -> None:
    with app.app_context():
        init_db()
        seed_db()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_user() -> None:
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT id, username, full_name, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Bem-vindo, {user['full_name']}.", "success")
            return redirect(url_for("dashboard"))

        flash("Usuário ou senha inválidos.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    month_prefix = date.today().strftime("%Y-%m")

    stats = {
        "clients_total": db.execute("SELECT COUNT(*) AS total FROM clients").fetchone()["total"],
        "products_total": db.execute("SELECT COUNT(*) AS total FROM products").fetchone()["total"],
        "low_stock": db.execute(
            "SELECT COUNT(*) AS total FROM products WHERE stock_qty <= min_stock"
        ).fetchone()["total"],
        "sales_month": db.execute(
            "SELECT COALESCE(SUM(total), 0) AS total FROM sales WHERE sale_date LIKE ?",
            (f"{month_prefix}%",),
        ).fetchone()["total"],
        "receivable": db.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM financial_entries
            WHERE entry_type = 'receber' AND status != 'pago'
            """
        ).fetchone()["total"],
        "payable": db.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM financial_entries
            WHERE entry_type = 'pagar' AND status != 'pago'
            """
        ).fetchone()["total"],
    }

    recent_sales = db.execute(
        """
        SELECT sales.id, clients.name AS client_name, products.name AS product_name, sales.total, sales.sale_date
        FROM sales
        JOIN clients ON clients.id = sales.client_id
        JOIN products ON products.id = sales.product_id
        ORDER BY sales.sale_date DESC, sales.id DESC
        LIMIT 5
        """
    ).fetchall()

    low_stock_products = db.execute(
        """
        SELECT name, sku, stock_qty, min_stock
        FROM products
        WHERE stock_qty <= min_stock
        ORDER BY stock_qty ASC, name ASC
        LIMIT 5
        """
    ).fetchall()

    finance_due = db.execute(
        """
        SELECT description, entry_type, amount, due_date, status
        FROM financial_entries
        ORDER BY due_date ASC, id DESC
        LIMIT 6
        """
    ).fetchall()

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_sales=recent_sales,
        low_stock_products=low_stock_products,
        finance_due=finance_due,
    )


@app.route("/clientes")
@login_required
def clients_list():
    clients = get_db().execute("SELECT * FROM clients ORDER BY name").fetchall()
    return render_template("clients/list.html", clients=clients)


@app.route("/clientes/novo", methods=["GET", "POST"])
@login_required
def clients_create():
    if request.method == "POST":
        db = get_db()
        db.execute(
            """
            INSERT INTO clients (name, document, email, phone, city, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["name"].strip(),
                request.form["document"].strip(),
                request.form["email"].strip(),
                request.form["phone"].strip(),
                request.form["city"].strip(),
                date.today().isoformat(),
            ),
        )
        db.commit()
        flash("Cliente cadastrado com sucesso.", "success")
        return redirect(url_for("clients_list"))
    return render_template("clients/form.html", client=None)


@app.route("/clientes/<int:client_id>/editar", methods=["GET", "POST"])
@login_required
def clients_edit(client_id: int):
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if client is None:
        flash("Cliente não encontrado.", "danger")
        return redirect(url_for("clients_list"))

    if request.method == "POST":
        db.execute(
            """
            UPDATE clients
            SET name = ?, document = ?, email = ?, phone = ?, city = ?
            WHERE id = ?
            """,
            (
                request.form["name"].strip(),
                request.form["document"].strip(),
                request.form["email"].strip(),
                request.form["phone"].strip(),
                request.form["city"].strip(),
                client_id,
            ),
        )
        db.commit()
        flash("Cliente atualizado.", "success")
        return redirect(url_for("clients_list"))
    return render_template("clients/form.html", client=client)


@app.route("/clientes/<int:client_id>/excluir", methods=["POST"])
@login_required
def clients_delete(client_id: int):
    db = get_db()
    related_sales = db.execute("SELECT COUNT(*) AS total FROM sales WHERE client_id = ?", (client_id,)).fetchone()["total"]
    if related_sales:
        flash("Cliente vinculado a vendas não pode ser excluído neste protótipo.", "warning")
    else:
        db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        db.commit()
        flash("Cliente removido.", "info")
    return redirect(url_for("clients_list"))


@app.route("/produtos")
@login_required
def products_list():
    products = get_db().execute("SELECT * FROM products ORDER BY name").fetchall()
    return render_template("products/list.html", products=products)


@app.route("/produtos/novo", methods=["GET", "POST"])
@login_required
def products_create():
    if request.method == "POST":
        db = get_db()
        db.execute(
            """
            INSERT INTO products (name, sku, price, cost, stock_qty, min_stock, category, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["name"].strip(),
                request.form["sku"].strip(),
                float(request.form["price"] or 0),
                float(request.form["cost"] or 0),
                int(request.form["stock_qty"] or 0),
                int(request.form["min_stock"] or 0),
                request.form["category"].strip(),
                date.today().isoformat(),
            ),
        )
        db.commit()
        flash("Produto cadastrado.", "success")
        return redirect(url_for("products_list"))
    return render_template("products/form.html", product=None)


@app.route("/produtos/<int:product_id>/editar", methods=["GET", "POST"])
@login_required
def products_edit(product_id: int):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        flash("Produto não encontrado.", "danger")
        return redirect(url_for("products_list"))

    if request.method == "POST":
        db.execute(
            """
            UPDATE products
            SET name = ?, sku = ?, price = ?, cost = ?, stock_qty = ?, min_stock = ?, category = ?
            WHERE id = ?
            """,
            (
                request.form["name"].strip(),
                request.form["sku"].strip(),
                float(request.form["price"] or 0),
                float(request.form["cost"] or 0),
                int(request.form["stock_qty"] or 0),
                int(request.form["min_stock"] or 0),
                request.form["category"].strip(),
                product_id,
            ),
        )
        db.commit()
        flash("Produto atualizado.", "success")
        return redirect(url_for("products_list"))
    return render_template("products/form.html", product=product)


@app.route("/produtos/<int:product_id>/excluir", methods=["POST"])
@login_required
def products_delete(product_id: int):
    db = get_db()
    related_sales = db.execute("SELECT COUNT(*) AS total FROM sales WHERE product_id = ?", (product_id,)).fetchone()["total"]
    if related_sales:
        flash("Produto vinculado a vendas não pode ser excluído neste protótipo.", "warning")
    else:
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit()
        flash("Produto removido.", "info")
    return redirect(url_for("products_list"))


@app.route("/estoque")
@login_required
def stock_list():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    movements = db.execute(
        """
        SELECT stock_movements.*, products.name AS product_name, products.sku
        FROM stock_movements
        JOIN products ON products.id = stock_movements.product_id
        ORDER BY stock_movements.created_at DESC, stock_movements.id DESC
        LIMIT 20
        """
    ).fetchall()
    return render_template("stock/list.html", products=products, movements=movements)


@app.route("/estoque/movimentar", methods=["POST"])
@login_required
def stock_move():
    db = get_db()
    product_id = int(request.form["product_id"])
    movement_type = request.form["movement_type"]
    quantity = int(request.form["quantity"] or 0)
    note = request.form["note"].strip()

    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None or quantity <= 0:
        flash("Dados inválidos para movimentação.", "danger")
        return redirect(url_for("stock_list"))

    new_qty = product["stock_qty"] + quantity if movement_type == "entrada" else product["stock_qty"] - quantity
    if new_qty < 0:
        flash("Estoque insuficiente para saída.", "danger")
        return redirect(url_for("stock_list"))

    db.execute(
        "UPDATE products SET stock_qty = ? WHERE id = ?",
        (new_qty, product_id),
    )
    db.execute(
        """
        INSERT INTO stock_movements (product_id, movement_type, quantity, note, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (product_id, movement_type, quantity, note, date.today().isoformat()),
    )
    db.commit()
    flash("Movimentação registrada.", "success")
    return redirect(url_for("stock_list"))


@app.route("/vendas")
@login_required
def sales_list():
    db = get_db()
    sales = db.execute(
        """
        SELECT sales.*, clients.name AS client_name, products.name AS product_name, products.sku
        FROM sales
        JOIN clients ON clients.id = sales.client_id
        JOIN products ON products.id = sales.product_id
        ORDER BY sales.sale_date DESC, sales.id DESC
        """
    ).fetchall()
    return render_template("sales/list.html", sales=sales)


@app.route("/vendas/nova", methods=["GET", "POST"])
@login_required
def sales_create():
    db = get_db()
    clients = db.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
    products = db.execute("SELECT id, name, sku, price, stock_qty FROM products ORDER BY name").fetchall()

    if request.method == "POST":
        client_id = int(request.form["client_id"])
        product_id = int(request.form["product_id"])
        quantity = int(request.form["quantity"] or 0)
        sale_date = request.form["sale_date"] or date.today().isoformat()
        payment_status = request.form["payment_status"]
        notes = request.form["notes"].strip()

        product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None or quantity <= 0:
            flash("Produto ou quantidade inválidos.", "danger")
            return render_template("sales/form.html", sale=None, clients=clients, products=products)
        if product["stock_qty"] < quantity:
            flash("Estoque insuficiente para concluir a venda.", "danger")
            return render_template("sales/form.html", sale=None, clients=clients, products=products)

        unit_price = float(product["price"])
        total = unit_price * quantity

        cursor = db.execute(
            """
            INSERT INTO sales (client_id, product_id, quantity, unit_price, total, sale_date, payment_status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (client_id, product_id, quantity, unit_price, total, sale_date, payment_status, notes),
        )
        sale_id = cursor.lastrowid
        db.execute(
            "UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?",
            (quantity, product_id),
        )
        db.execute(
            """
            INSERT INTO stock_movements (product_id, movement_type, quantity, note, created_at)
            VALUES (?, 'saida', ?, ?, ?)
            """,
            (product_id, quantity, f"Venda #{sale_id}", sale_date),
        )
        if payment_status == "receber":
            db.execute(
                """
                INSERT INTO financial_entries
                (description, entry_type, amount, due_date, status, category, related_sale_id, notes)
                VALUES (?, 'receber', ?, ?, 'pendente', 'Vendas', ?, ?)
                """,
                (f"Recebimento venda #{sale_id}", total, sale_date, sale_id, notes or "Gerado automaticamente"),
            )
        db.commit()
        flash("Venda registrada.", "success")
        return redirect(url_for("sales_list"))

    return render_template("sales/form.html", sale=None, clients=clients, products=products)


@app.route("/vendas/<int:sale_id>/editar", methods=["GET", "POST"])
@login_required
def sales_edit(sale_id: int):
    db = get_db()
    sale = db.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    clients = db.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
    products = db.execute("SELECT id, name, sku, price, stock_qty FROM products ORDER BY name").fetchall()

    if sale is None:
        flash("Venda não encontrada.", "danger")
        return redirect(url_for("sales_list"))

    if request.method == "POST":
        client_id = int(request.form["client_id"])
        product_id = int(request.form["product_id"])
        quantity = int(request.form["quantity"] or 0)
        sale_date = request.form["sale_date"] or date.today().isoformat()
        payment_status = request.form["payment_status"]
        notes = request.form["notes"].strip()

        old_product = db.execute("SELECT * FROM products WHERE id = ?", (sale["product_id"],)).fetchone()
        new_product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if new_product is None or old_product is None or quantity <= 0:
            flash("Dados inválidos para atualizar a venda.", "danger")
            return render_template("sales/form.html", sale=sale, clients=clients, products=products)

        if product_id == sale["product_id"]:
            available_stock = old_product["stock_qty"] + sale["quantity"]
            if available_stock < quantity:
                flash("Estoque insuficiente para atualizar a venda.", "danger")
                return render_template("sales/form.html", sale=sale, clients=clients, products=products)
            updated_stock = available_stock - quantity
            db.execute("UPDATE products SET stock_qty = ? WHERE id = ?", (updated_stock, product_id))
        else:
            if new_product["stock_qty"] < quantity:
                flash("Estoque insuficiente no novo produto.", "danger")
                return render_template("sales/form.html", sale=sale, clients=clients, products=products)
            db.execute(
                "UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?",
                (sale["quantity"], sale["product_id"]),
            )
            db.execute(
                "UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?",
                (quantity, product_id),
            )

        unit_price = float(new_product["price"])
        total = unit_price * quantity

        db.execute(
            """
            UPDATE sales
            SET client_id = ?, product_id = ?, quantity = ?, unit_price = ?, total = ?, sale_date = ?, payment_status = ?, notes = ?
            WHERE id = ?
            """,
            (client_id, product_id, quantity, unit_price, total, sale_date, payment_status, notes, sale_id),
        )
        db.execute(
            """
            DELETE FROM stock_movements
            WHERE product_id = ? AND movement_type = 'saida' AND note = ?
            """,
            (sale["product_id"], f"Venda #{sale_id}"),
        )
        db.execute(
            """
            INSERT INTO stock_movements (product_id, movement_type, quantity, note, created_at)
            VALUES (?, 'saida', ?, ?, ?)
            """,
            (product_id, quantity, f"Venda #{sale_id}", sale_date),
        )

        existing_entry = db.execute(
            "SELECT id FROM financial_entries WHERE related_sale_id = ?",
            (sale_id,),
        ).fetchone()
        if payment_status == "receber":
            if existing_entry:
                db.execute(
                    """
                    UPDATE financial_entries
                    SET description = ?, amount = ?, due_date = ?, status = 'pendente', notes = ?
                    WHERE id = ?
                    """,
                    (f"Recebimento venda #{sale_id}", total, sale_date, notes or "Gerado automaticamente", existing_entry["id"]),
                )
            else:
                db.execute(
                    """
                    INSERT INTO financial_entries
                    (description, entry_type, amount, due_date, status, category, related_sale_id, notes)
                    VALUES (?, 'receber', ?, ?, 'pendente', 'Vendas', ?, ?)
                    """,
                    (f"Recebimento venda #{sale_id}", total, sale_date, sale_id, notes or "Gerado automaticamente"),
                )
        elif existing_entry:
            db.execute("DELETE FROM financial_entries WHERE id = ?", (existing_entry["id"],))

        db.commit()
        flash("Venda atualizada.", "success")
        return redirect(url_for("sales_list"))

    return render_template("sales/form.html", sale=sale, clients=clients, products=products)


@app.route("/vendas/<int:sale_id>/excluir", methods=["POST"])
@login_required
def sales_delete(sale_id: int):
    db = get_db()
    sale = db.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if sale is None:
        flash("Venda não encontrada.", "danger")
        return redirect(url_for("sales_list"))

    db.execute(
        "UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?",
        (sale["quantity"], sale["product_id"]),
    )
    db.execute(
        """
        DELETE FROM stock_movements
        WHERE product_id = ? AND movement_type = 'saida' AND note = ?
        """,
        (sale["product_id"], f"Venda #{sale_id}"),
    )
    db.execute("DELETE FROM financial_entries WHERE related_sale_id = ?", (sale_id,))
    db.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    db.commit()
    flash("Venda excluída e estoque recomposto.", "info")
    return redirect(url_for("sales_list"))


@app.route("/financeiro")
@login_required
def finance_list():
    entries = get_db().execute(
        "SELECT * FROM financial_entries ORDER BY due_date ASC, id DESC"
    ).fetchall()
    return render_template("finance/list.html", entries=entries)


@app.route("/financeiro/novo", methods=["GET", "POST"])
@login_required
def finance_create():
    if request.method == "POST":
        db = get_db()
        db.execute(
            """
            INSERT INTO financial_entries
            (description, entry_type, amount, due_date, status, category, related_sale_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                request.form["description"].strip(),
                request.form["entry_type"],
                float(request.form["amount"] or 0),
                request.form["due_date"],
                request.form["status"],
                request.form["category"].strip(),
                request.form["notes"].strip(),
            ),
        )
        db.commit()
        flash("Lançamento financeiro cadastrado.", "success")
        return redirect(url_for("finance_list"))
    return render_template("finance/form.html", entry=None)


@app.route("/financeiro/<int:entry_id>/editar", methods=["GET", "POST"])
@login_required
def finance_edit(entry_id: int):
    db = get_db()
    entry = db.execute("SELECT * FROM financial_entries WHERE id = ?", (entry_id,)).fetchone()
    if entry is None:
        flash("Lançamento não encontrado.", "danger")
        return redirect(url_for("finance_list"))

    if request.method == "POST":
        db.execute(
            """
            UPDATE financial_entries
            SET description = ?, entry_type = ?, amount = ?, due_date = ?, status = ?, category = ?, notes = ?
            WHERE id = ?
            """,
            (
                request.form["description"].strip(),
                request.form["entry_type"],
                float(request.form["amount"] or 0),
                request.form["due_date"],
                request.form["status"],
                request.form["category"].strip(),
                request.form["notes"].strip(),
                entry_id,
            ),
        )
        db.commit()
        flash("Lançamento atualizado.", "success")
        return redirect(url_for("finance_list"))
    return render_template("finance/form.html", entry=entry)


@app.route("/financeiro/<int:entry_id>/excluir", methods=["POST"])
@login_required
def finance_delete(entry_id: int):
    db = get_db()
    db.execute("DELETE FROM financial_entries WHERE id = ?", (entry_id,))
    db.commit()
    flash("Lançamento removido.", "info")
    return redirect(url_for("finance_list"))


def ensure_directories() -> None:
    (BASE_DIR / "templates").mkdir(exist_ok=True)
    (BASE_DIR / "static").mkdir(exist_ok=True)


ensure_directories()
bootstrap_db()


if __name__ == "__main__":
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=True, host=host, port=port)
