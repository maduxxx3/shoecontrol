from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.config["SECRET_KEY"] = "shoecontrol123"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shoecontrol.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================
# MODELOS
# =========================

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    marca = db.Column(db.String(100))
    categoria = db.Column(db.String(100))
    tamanho = db.Column(db.String(20))
    cor = db.Column(db.String(50))
    quantidade = db.Column(db.Integer, default=0)
    preco_custo = db.Column(db.Float, default=0.0)
    preco_venda = db.Column(db.Float, default=0.0)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    vendas = db.relationship("Venda", backref="produto", lazy=True)


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    cidade = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    vendas = db.relationship("Venda", backref="cliente", lazy=True)


class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=True)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    lucro = db.Column(db.Float, default=0.0)
    forma_pagamento = db.Column(db.String(50))
    data_venda = db.Column(db.DateTime, default=datetime.utcnow)
    observacoes = db.Column(db.Text)


class Caixa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)  # entrada / saida
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_movimento = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# FILTRO DE MOEDA
# =========================

@app.template_filter("brl")
def brl(valor):
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


# =========================
# LOGIN OBRIGATÓRIO
# =========================

@app.before_request
def exigir_login():
    rotas_livres = ["login"]
    if request.endpoint in rotas_livres:
        return

    if request.endpoint and request.endpoint.startswith("static"):
        return

    if "usuario_id" not in session:
        return redirect(url_for("login"))


# =========================
# FUNÇÕES AUXILIARES
# =========================

def resumo_dashboard():
    hoje = date.today()
    inicio_mes = date(hoje.year, hoje.month, 1)

    vendas_dia = db.session.query(func.sum(Venda.valor_total)).filter(
        func.date(Venda.data_venda) == hoje
    ).scalar() or 0

    faturamento_mes = db.session.query(func.sum(Venda.valor_total)).filter(
        func.date(Venda.data_venda) >= inicio_mes
    ).scalar() or 0

    lucro_mes = db.session.query(func.sum(Venda.lucro)).filter(
        func.date(Venda.data_venda) >= inicio_mes
    ).scalar() or 0

    total_produtos = Produto.query.count()
    estoque_baixo = Produto.query.filter(Produto.quantidade <= 3).count()

    return {
        "vendas_dia": vendas_dia,
        "faturamento_mes": faturamento_mes,
        "lucro_mes": lucro_mes,
        "total_produtos": total_produtos,
        "estoque_baixo": estoque_baixo,
    }


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "").strip()

        usuario = Usuario.query.filter_by(email=email, senha=senha).first()

        if usuario:
            session["usuario_id"] = usuario.id
            session["usuario_nome"] = usuario.nome
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("dashboard"))

        flash("E-mail ou senha inválidos.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("login"))


# =========================
# DASHBOARD
# =========================

@app.route("/")
def dashboard():
    dados = resumo_dashboard()

    vendas_recentes = Venda.query.order_by(Venda.id.desc()).limit(5).all()
    produtos_baixo = Produto.query.filter(Produto.quantidade <= 3).order_by(Produto.quantidade.asc()).all()

    grafico_labels = []
    grafico_valores = []

    vendas_por_produto = db.session.query(
        Produto.nome,
        func.sum(Venda.quantidade)
    ).join(Venda, Venda.produto_id == Produto.id).group_by(Produto.nome).all()

    for nome, qtd in vendas_por_produto:
        grafico_labels.append(nome)
        grafico_valores.append(qtd)

    return render_template(
        "dashboard.html",
        dados=dados,
        vendas_recentes=vendas_recentes,
        produtos_baixo=produtos_baixo,
        grafico_labels=grafico_labels,
        grafico_valores=grafico_valores
    )


# =========================
# PRODUTOS
# =========================

@app.route("/produtos")
def produtos():
    busca = request.args.get("busca", "").strip()

    if busca:
        lista = Produto.query.filter(Produto.nome.ilike(f"%{busca}%")).order_by(Produto.id.desc()).all()
    else:
        lista = Produto.query.order_by(Produto.id.desc()).all()

    return render_template("produtos.html", produtos=lista, busca=busca)


@app.route("/produtos/novo", methods=["GET", "POST"])
def produto_novo():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        marca = request.form.get("marca", "").strip()
        categoria = request.form.get("categoria", "").strip()
        tamanho = request.form.get("tamanho", "").strip()
        cor = request.form.get("cor", "").strip()
        quantidade = request.form.get("quantidade", "0").strip()
        preco_custo = request.form.get("preco_custo", "0").strip()
        preco_venda = request.form.get("preco_venda", "0").strip()

        if not nome:
            flash("Informe o nome do produto.", "danger")
            return redirect(url_for("produto_novo"))

        produto = Produto(
            nome=nome,
            marca=marca,
            categoria=categoria,
            tamanho=tamanho,
            cor=cor,
            quantidade=int(quantidade) if quantidade else 0,
            preco_custo=float(preco_custo) if preco_custo else 0,
            preco_venda=float(preco_venda) if preco_venda else 0,
        )

        db.session.add(produto)
        db.session.commit()

        flash("Produto cadastrado com sucesso.", "success")
        return redirect(url_for("produtos"))

    return render_template("produto_novo.html")


@app.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
def produto_editar(produto_id):
    produto = Produto.query.get_or_404(produto_id)

    if request.method == "POST":
        produto.nome = request.form.get("nome", "").strip()
        produto.marca = request.form.get("marca", "").strip()
        produto.categoria = request.form.get("categoria", "").strip()
        produto.tamanho = request.form.get("tamanho", "").strip()
        produto.cor = request.form.get("cor", "").strip()
        produto.quantidade = int(request.form.get("quantidade", "0") or 0)
        produto.preco_custo = float(request.form.get("preco_custo", "0") or 0)
        produto.preco_venda = float(request.form.get("preco_venda", "0") or 0)

        db.session.commit()
        flash("Produto atualizado com sucesso.", "success")
        return redirect(url_for("produtos"))

    return render_template("produto_editar.html", produto=produto)


@app.route("/produtos/<int:produto_id>/excluir", methods=["POST"])
def produto_excluir(produto_id):
    produto = Produto.query.get_or_404(produto_id)

    if produto.vendas:
        flash("Este produto já possui vendas e não pode ser excluído.", "danger")
        return redirect(url_for("produtos"))

    db.session.delete(produto)
    db.session.commit()
    flash("Produto excluído com sucesso.", "success")
    return redirect(url_for("produtos"))


# =========================
# ESTOQUE
# =========================

@app.route("/estoque")
def estoque():
    lista = Produto.query.order_by(Produto.nome.asc()).all()
    return render_template("estoque.html", produtos=lista)


# =========================
# CLIENTES
# =========================

@app.route("/clientes")
def clientes():
    lista = Cliente.query.order_by(Cliente.id.desc()).all()
    return render_template("clientes.html", clientes=lista)


@app.route("/clientes/novo", methods=["GET", "POST"])
def cliente_novo():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        email = request.form.get("email", "").strip()
        cidade = request.form.get("cidade", "").strip()
        observacoes = request.form.get("observacoes", "").strip()

        if not nome:
            flash("Informe o nome do cliente.", "danger")
            return redirect(url_for("cliente_novo"))

        cliente = Cliente(
            nome=nome,
            telefone=telefone,
            email=email,
            cidade=cidade,
            observacoes=observacoes,
        )

        db.session.add(cliente)
        db.session.commit()

        flash("Cliente cadastrado com sucesso.", "success")
        return redirect(url_for("clientes"))

    return render_template("cliente_novo.html")


@app.route("/clientes/<int:cliente_id>/editar", methods=["GET", "POST"])
def cliente_editar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        cliente.nome = request.form.get("nome", "").strip()
        cliente.telefone = request.form.get("telefone", "").strip()
        cliente.email = request.form.get("email", "").strip()
        cliente.cidade = request.form.get("cidade", "").strip()
        cliente.observacoes = request.form.get("observacoes", "").strip()

        db.session.commit()
        flash("Cliente atualizado com sucesso.", "success")
        return redirect(url_for("clientes"))

    return render_template("cliente_editar.html", cliente=cliente)


@app.route("/clientes/<int:cliente_id>/excluir", methods=["POST"])
def cliente_excluir(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if cliente.vendas:
        flash("Cliente possui vendas vinculadas e não pode ser excluído.", "danger")
        return redirect(url_for("clientes"))

    db.session.delete(cliente)
    db.session.commit()

    flash("Cliente excluído com sucesso.", "success")
    return redirect(url_for("clientes"))


# =========================
# VENDAS
# =========================

@app.route("/vendas")
def vendas():
    busca = request.args.get("busca", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()

    query = Venda.query

    if busca:
        query = query.join(Produto).filter(Produto.nome.ilike(f"%{busca}%"))

    if data_inicio:
        query = query.filter(func.date(Venda.data_venda) >= data_inicio)

    if data_fim:
        query = query.filter(func.date(Venda.data_venda) <= data_fim)

    lista = query.order_by(Venda.id.desc()).all()

    return render_template(
        "vendas.html",
        vendas=lista,
        busca=busca,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


@app.route("/vendas/nova", methods=["GET", "POST"])
def venda_nova():
    produtos = Produto.query.order_by(Produto.nome.asc()).all()
    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()

    if request.method == "POST":
        produto_id = request.form.get("produto_id")
        cliente_id = request.form.get("cliente_id")
        quantidade = request.form.get("quantidade", "1").strip()
        forma_pagamento = request.form.get("forma_pagamento", "").strip()
        observacoes = request.form.get("observacoes", "").strip()

        if not produto_id:
            flash("Selecione um produto.", "danger")
            return redirect(url_for("venda_nova"))

        produto = Produto.query.get(produto_id)

        if not produto:
            flash("Produto não encontrado.", "danger")
            return redirect(url_for("venda_nova"))

        qtd = int(quantidade) if quantidade else 0

        if qtd <= 0:
            flash("A quantidade deve ser maior que zero.", "danger")
            return redirect(url_for("venda_nova"))

        if produto.quantidade < qtd:
            flash("Estoque insuficiente para essa venda.", "danger")
            return redirect(url_for("venda_nova"))

        valor_unitario = produto.preco_venda
        valor_total = valor_unitario * qtd
        lucro_unitario = produto.preco_venda - produto.preco_custo
        lucro_total = lucro_unitario * qtd

        venda = Venda(
            produto_id=produto.id,
            cliente_id=int(cliente_id) if cliente_id else None,
            quantidade=qtd,
            valor_unitario=valor_unitario,
            valor_total=valor_total,
            lucro=lucro_total,
            forma_pagamento=forma_pagamento,
            observacoes=observacoes,
        )

        produto.quantidade -= qtd

        movimento = Caixa(
            tipo="entrada",
            descricao=f"Venda do produto {produto.nome}",
            valor=valor_total
        )

        db.session.add(venda)
        db.session.add(movimento)
        db.session.commit()

        flash("Venda realizada com sucesso.", "success")
        return redirect(url_for("vendas"))

    return render_template("venda_nova.html", produtos=produtos, clientes=clientes)


@app.route("/vendas/<int:venda_id>/excluir", methods=["POST"])
def venda_excluir(venda_id):
    venda = Venda.query.get_or_404(venda_id)

    produto = Produto.query.get(venda.produto_id)
    if produto:
        produto.quantidade += venda.quantidade

    movimento_caixa = Caixa.query.filter(
        Caixa.tipo == "entrada",
        Caixa.descricao == f"Venda do produto {venda.produto.nome}",
        Caixa.valor == venda.valor_total
    ).order_by(Caixa.id.desc()).first()

    if movimento_caixa:
        db.session.delete(movimento_caixa)

    db.session.delete(venda)
    db.session.commit()

    flash("Venda excluída e estoque devolvido com sucesso.", "success")
    return redirect(url_for("vendas"))


# =========================
# CAIXA
# =========================

@app.route("/caixa")
def caixa():
    movimentos = Caixa.query.order_by(Caixa.id.desc()).all()

    total_entradas = db.session.query(func.sum(Caixa.valor)).filter(Caixa.tipo == "entrada").scalar() or 0
    total_saidas = db.session.query(func.sum(Caixa.valor)).filter(Caixa.tipo == "saida").scalar() or 0
    saldo = total_entradas - total_saidas

    return render_template(
        "caixa.html",
        movimentos=movimentos,
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        saldo=saldo,
    )


@app.route("/caixa/novo", methods=["POST"])
def caixa_novo():
    tipo = request.form.get("tipo", "").strip()
    descricao = request.form.get("descricao", "").strip()
    valor = request.form.get("valor", "0").strip()

    if tipo not in ["entrada", "saida"]:
        flash("Tipo de movimento inválido.", "danger")
        return redirect(url_for("caixa"))

    if not descricao:
        flash("Informe a descrição.", "danger")
        return redirect(url_for("caixa"))

    movimento = Caixa(
        tipo=tipo,
        descricao=descricao,
        valor=float(valor) if valor else 0
    )

    db.session.add(movimento)
    db.session.commit()

    flash("Movimento lançado com sucesso.", "success")
    return redirect(url_for("caixa"))


# =========================
# RELATÓRIOS
# =========================

@app.route("/relatorios")
def relatorios():
    total_produtos = Produto.query.count()
    total_clientes = Cliente.query.count()
    total_vendas = Venda.query.count()

    faturamento_total = db.session.query(func.sum(Venda.valor_total)).scalar() or 0
    lucro_total = db.session.query(func.sum(Venda.lucro)).scalar() or 0
    entradas = db.session.query(func.sum(Caixa.valor)).filter(Caixa.tipo == "entrada").scalar() or 0
    saidas = db.session.query(func.sum(Caixa.valor)).filter(Caixa.tipo == "saida").scalar() or 0
    saldo = entradas - saidas

    produtos_baixo = Produto.query.filter(Produto.quantidade <= 3).order_by(Produto.quantidade.asc()).all()

    grafico_labels = []
    grafico_valores = []

    vendas_por_produto = db.session.query(
        Produto.nome,
        func.sum(Venda.quantidade)
    ).join(Venda, Venda.produto_id == Produto.id).group_by(Produto.nome).all()

    for nome, qtd in vendas_por_produto:
        grafico_labels.append(nome)
        grafico_valores.append(qtd)

    return render_template(
        "relatorios.html",
        total_produtos=total_produtos,
        total_clientes=total_clientes,
        total_vendas=total_vendas,
        faturamento_total=faturamento_total,
        lucro_total=lucro_total,
        entradas=entradas,
        saidas=saidas,
        saldo=saldo,
        produtos_baixo=produtos_baixo,
        grafico_labels=grafico_labels,
        grafico_valores=grafico_valores
    )


# =========================
# BANCO
# =========================

with app.app_context():
    db.create_all()

    usuario_admin = Usuario.query.filter_by(email="admin@shoecontrol.com").first()
    if not usuario_admin:
        usuario_admin = Usuario(
            nome="Administrador",
            email="admin@shoecontrol.com",
            senha="123456"
        )
        db.session.add(usuario_admin)
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True)