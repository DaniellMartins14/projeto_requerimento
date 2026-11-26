## projeto feito por daniel martins, e eduarda koehler
## professor ronan adriel zenati

## caríssimo professor, o código está inteiro comentado para facilitar nosso entendimento. 
## foram usados duas # para que fique claro nossa autoria dos comentários (por mais que uma IA não escreveria como eu)

import os
from functools import wraps

## dotenv permite carregar variaveis secretas e configuracoes do arquivo .env.
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
## Protecao CSRF evita que formularios sejam enviados por paginas externas maliciosas.
from flask_wtf.csrf import CSRFProtect
## para utilizar o sistema de senha
from werkzeug.security import generate_password_hash, check_password_hash
## denuncia os erros do sql
from mysql.connector import Error

##carrega as informação do .env
load_dotenv()

from db import execute_one, execute_query, execute_insert

app = Flask(__name__)
# chave usada para proteger os dados da sessao do usuario.
app.secret_key = os.getenv("SECRET_KEY")
## proteção contra requisição de sites maliciosos, que podem estar em outra guia
CSRFProtect(app)

## fala quais os níveis de acesso
NIVEIS_ACESSO = ["municipe", "servidor", "administrador"]

## função que garante que o usuário esteja logado para acessar outras páginas
def login_required(rota):
    @wraps(rota)
    def verificar_login(*args, **kwargs):
        if "municipe_id" not in session:
            flash("Faça login para acessar esta página.", "warning")
            return redirect(url_for("login"))
        return rota(*args, **kwargs)
    return verificar_login


## função para buscar usuário por email
def buscar_municipe_por_email(email):
    """Busca um munícipe ativo no MySQL, ignorando espaços e caixa."""
    # remove espacos antes e depois do e-mail informado.
    email_normalizado = (email or "").strip()
    return execute_one(
        "SELECT id_municipe AS id, nome, telefone, endereco, cep, numero, cidade, "
        "estado, complemento, email, cpf, data_nascimento, nivel_acesso, senha_hash "
        "FROM municipes WHERE LOWER(TRIM(email)) = LOWER(%s) AND deletado_em IS NULL",
        (email_normalizado,),
    )


## função que busca múnicipe por nome - serve para abrir protocolos apenas para munícipes cadastrados
def buscar_municipe_por_nome(nome):
    """Busca um munícipe ativo pelo nome, sem diferenciar caixa ou espaços."""
    # remove espacos repetidos e normaliza o nome para facilitar a comparacao.
    nome_normalizado = " ".join((nome or "").split())
    return execute_one(
        "SELECT id_municipe AS id, nome FROM municipes "
        "WHERE LOWER(TRIM(nome)) = LOWER(%s) AND deletado_em IS NULL "
        "ORDER BY id_municipe LIMIT 1",
        (nome_normalizado,),
    )


## Busca os dados completos de um cadastro usando seu identificador.
def buscar_municipe_por_id(registro_id):
    return execute_one(
        "SELECT id_municipe AS id, nome, telefone, endereco, cep, numero, cidade, "
        "estado, complemento, email, cpf, data_nascimento, nivel_acesso, senha_hash "
        "FROM municipes WHERE id_municipe = %s AND deletado_em IS NULL",
        (registro_id,),
    )


## Retorna todos os municipes ativos para a pagina de listagem.
def listar_municipes():
    return execute_query(
        "SELECT id_municipe AS id, nome, telefone, email, cpf, data_nascimento, "
        "nivel_acesso, endereco, numero, cep, cidade, estado, complemento "
        "FROM municipes WHERE deletado_em IS NULL ORDER BY nome",
        fetch=True,
    )


## formata cpd no xxx;xxx;xxx-xx
def formatar_cpf(cpf):
    # Mantem somente os caracteres numericos do CPF.
    numeros = "".join(filter(str.isdigit, cpf or ""))
    if len(numeros) == 11:
        return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"
    return cpf

##rota inicial indica para o dashboard já
@app.route("/")
@login_required
def index():
    total_municipes = execute_one(
        "SELECT COUNT(*) AS total FROM municipes WHERE deletado_em IS NULL"
    )["total"]
    total_processos = execute_one(
        "SELECT COUNT(*) AS total FROM processos WHERE deletado_em IS NULL"
    )["total"]
    total_inscricoes = execute_one(
        "SELECT COUNT(*) AS total FROM inscricoes_municipais WHERE deletado_em IS NULL"
    )["total"]

    ultimos_municipes = execute_query(
        "SELECT id_municipe AS id, nome, email, cpf, cidade, estado "
        "FROM municipes WHERE deletado_em IS NULL ORDER BY id_municipe DESC LIMIT 5",
        fetch=True,
    )

    return render_template(
        "dashboard.html",
        total_municipes=total_municipes,
        total_processos=total_processos,
        total_inscricoes=total_inscricoes,
        ultimos_municipes=ultimos_municipes,
    )


##rota login
@app.route("/login", methods=["GET", "POST"])
def login():
    if "municipe_id" in session:
        return redirect(url_for("index"))

    # POST indica que o formulario foi enviado; GET apenas solicita a pagina.
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        erros = []

        if not email:
            erros.append("Informe o e-mail.")
        if not senha:
            erros.append("Informe a senha.")

        municipe = None
        if not erros:
            try:
                municipe = buscar_municipe_por_email(email)
            except Error:
                flash("Não foi possível realizar o login neste momento.", "danger")
                return render_template("login.html", dados={"email": email})

            if not municipe or not check_password_hash(municipe["senha_hash"], senha):
                erros.append("E-mail ou senha incorretos.")

        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template("login.html", dados={"email": email})

        session.clear()
        session["municipe_id"] = municipe["id"]
        session["municipe_nome"] = municipe["nome"]
        flash(f"Bem-vindo(a), {municipe['nome']}!", "success")
        return redirect(url_for("index"))

    return render_template("login.html", dados={})


## deslogar 
@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("login"))


## criar cadastro de munícipe
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        endereco = request.form.get("endereco", "").strip()
        cep = request.form.get("cep", "").strip()
        numero = request.form.get("numero", "").strip() or "S/N"
        cidade = request.form.get("cidade", "").strip()
        estado = request.form.get("estado", "").strip()
        complemento = request.form.get("complemento", "").strip()
        email = request.form.get("email", "").strip()
        cpf = request.form.get("cpf", "").strip()
        data_nascimento = request.form.get("data_nascimento", "").strip()
        nivel_acesso = request.form.get("nivel_acesso", "").strip()
        senha = request.form.get("senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")

        erros = []
        if not nome: erros.append("Informe o nome.")
        if not telefone: erros.append("Informe o telefone.")
        if not endereco: erros.append("Informe o endereço.")
        if not cep: erros.append("Informe o CEP.")
        if not cidade: erros.append("Informe a cidade.")
        if not estado: erros.append("Informe o estado.")
        if not email: erros.append("Informe o e-mail.")
        if not cpf: erros.append("Informe o CPF.")
        if not data_nascimento: erros.append("Informe a data de nascimento.")
        if nivel_acesso not in NIVEIS_ACESSO:
            erros.append("Selecione um nível de acesso válido.")
        if not senha: erros.append("Informe a senha.")
        elif senha != confirmar_senha: erros.append("As senhas não conferem.")

        if erros:
            for erro in erros:
                flash(erro, "danger")
            dados = request.form.to_dict()
            dados.pop("senha", None)
            dados.pop("confirmar_senha", None)
            return render_template("usuarios/municipe-form.html", dados=dados, nivel_acesso=nivel_acesso)

        try:
            execute_insert(
                "INSERT INTO municipes (nome, email, senha_hash, telefone, data_nascimento, "
                "cpf, nivel_acesso, cep, endereco, numero, complemento, cidade, estado) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (nome, email, generate_password_hash(senha), telefone, data_nascimento,
                 formatar_cpf(cpf), nivel_acesso, cep, endereco, numero, complemento,
                 cidade, estado),
            )
        except Error:
            flash("Não foi possível salvar os dados. Verifique se e-mail, CPF ou CNPJ já estão cadastrados.", "danger")
            dados = request.form.to_dict()
            dados.pop("senha", None)
            dados.pop("confirmar_senha", None)
            return render_template("usuarios/municipe-form.html", dados=dados, nivel_acesso=nivel_acesso)

        flash("Munícipe cadastrado com sucesso!", "success")
        if "municipe_id" in session:
            return redirect(url_for("listagem"))
        flash("Agora faça login para acessar o sistema.", "info")
        return redirect(url_for("login"))

    return render_template("usuarios/municipe-form.html", dados={}, nivel_acesso="")


## exibe os munícipes
@app.route("/listagem")
@login_required
def listagem():
    try:
        municipes = listar_municipes()
    except Error:
        flash("Não foi possível carregar os munícipes.", "danger")
        municipes = []
    return render_template("usuarios/municipe-listar.html", municipes=municipes)


## edita um cadastro de munícipe
@app.route("/editar_municipe/<int:registro_id>", methods=["GET", "POST"])
@login_required
def editar_municipe(registro_id):
    try:
        municipe = buscar_municipe_por_id(registro_id)
    except Error:
        flash("Não foi possível consultar o cadastro.", "danger")
        return redirect(url_for("listagem"))
    if not municipe:
        flash("Munícipe não encontrado.", "warning")
        return redirect(url_for("listagem"))

    if request.method == "POST":
        dados = {campo: request.form.get(campo, "").strip() for campo in [
            "nome", "telefone", "endereco", "cep", "cidade", "estado",
            "email", "cpf", "data_nascimento", "nivel_acesso"
        ]}
        dados["numero"] = request.form.get("numero", "").strip() or "S/N"
        dados["complemento"] = request.form.get("complemento", "").strip()
        senha = request.form.get("senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")
        erros = []
        obrigatorios = ["nome", "telefone", "endereco", "cep", "cidade", "estado",
                        "email", "cpf", "data_nascimento", "nivel_acesso"]
        if any(not dados[campo] for campo in obrigatorios):
            erros.append("Preencha todos os campos obrigatórios.")
        if dados["nivel_acesso"] not in NIVEIS_ACESSO:
            erros.append("Selecione um nível de acesso válido.")
        if senha and senha != confirmar_senha:
            erros.append("As senhas não conferem.")

        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template("usuarios/municipe-form.html", dados=dados,
                                   nivel_acesso=dados["nivel_acesso"],
                                   editando=True, registro_id=registro_id)

        sql = (
            "UPDATE municipes SET nome=%s, telefone=%s, endereco=%s, cep=%s, numero=%s, "
            "cidade=%s, estado=%s, complemento=%s, email=%s, cpf=%s, data_nascimento=%s, "
            "nivel_acesso=%s"
        )
        params = [dados["nome"], dados["telefone"], dados["endereco"], dados["cep"],
                  dados["numero"], dados["cidade"], dados["estado"], dados["complemento"],
                  dados["email"], formatar_cpf(dados["cpf"]), dados["data_nascimento"],
                  dados["nivel_acesso"]]
        if senha:
            sql += ", senha_hash=%s"
            params.append(generate_password_hash(senha))
        sql += " WHERE id_municipe=%s AND deletado_em IS NULL"
        params.append(registro_id)

        try:
            execute_query(sql, tuple(params))
        except Error:
            flash("Não foi possível salvar os dados. Verifique se e-mail, CPF ou CNPJ já estão cadastrados.", "danger")
            return render_template("usuarios/municipe-form.html", dados=dados,
                                   nivel_acesso=dados["nivel_acesso"],
                                   editando=True, registro_id=registro_id)
        if session.get("municipe_id") == registro_id:
            session["municipe_nome"] = dados["nome"]
        flash("Munícipe atualizado com sucesso!", "success")
        return redirect(url_for("listagem"))

    dados = {chave: valor for chave, valor in municipe.items() if chave != "senha_hash"}
    return render_template("usuarios/municipe-form.html", dados=dados,
                           nivel_acesso=municipe["nivel_acesso"],
                           editando=True, registro_id=registro_id)


## soft delete
@app.route("/remover_municipe/<int:registro_id>", methods=["POST"])
@login_required
def remover_municipe(registro_id):
    if registro_id == session.get("municipe_id"):
        flash("Você não pode remover o usuário que está conectado.", "danger")
    else:
        try:
            municipe = buscar_municipe_por_id(registro_id)
            if not municipe:
                flash("Munícipe não encontrado.", "warning")
            else:
                execute_query(
                    "UPDATE municipes SET deletado_em=NOW() "
                    "WHERE id_municipe=%s AND deletado_em IS NULL",
                    (registro_id,),
                )
                flash("Munícipe removido com sucesso!", "success")
        except Error:
            flash("Não foi possível remover o munícipe.", "danger")
    return redirect(url_for("listagem"))


## Busca um processo e o nome do municipe relacionado para visualizar ou editar.
def buscar_processo_por_id(registro_id):
    return execute_one(
        "SELECT p.id_processo AS id, m.nome AS municipe, p.municipe_id, "
        "p.data_execucao, p.solicitacao, p.local_execucao, p.secretaria_destinada "
        "FROM processos p JOIN municipes m ON m.id_municipe=p.municipe_id "
        "WHERE p.id_processo=%s AND p.deletado_em IS NULL AND m.deletado_em IS NULL",
        (registro_id,),
    )


## Lista os processos ativos com o nome do municipe vinculado.
def listar_processos():
    return execute_query(
        "SELECT p.id_processo AS id, m.nome AS municipe, p.data_execucao, "
        "p.solicitacao, p.local_execucao, p.secretaria_destinada "
        "FROM processos p JOIN municipes m ON m.id_municipe=p.municipe_id "
        "WHERE p.deletado_em IS NULL AND m.deletado_em IS NULL "
        "ORDER BY p.id_processo DESC",
        fetch=True,
    )


## cadastra processo e conecta a municipe existente
@app.route("/cadastro_processo", methods=["GET", "POST"])
@login_required
def cadastro_processo():
    if request.method == "POST":
        municipe_nome = request.form.get("municipe", "").strip()
        data_execucao = request.form.get("data_execucao", "").strip()
        solicitacao = request.form.get("solicitacao", "").strip()
        local_execucao = request.form.get("local_execucao", "").strip()
        secretaria_destinada = request.form.get("secretaria_destinada", "").strip()
        erros = []
        if not municipe_nome: erros.append("Informe o nome do munícipe.")
        if not data_execucao: erros.append("Informe a data a ser executada.")
        if not solicitacao: erros.append("Descreva a solicitação.")
        if not local_execucao: erros.append("Informe o local de execução.")
        if not secretaria_destinada: erros.append("Informe a secretaria destinada.")

        municipe = None
        if not erros:
            try:
                municipe = buscar_municipe_por_nome(municipe_nome)
                if not municipe:
                    erros.append("Munícipe não encontrado. Faça o cadastro antes de abrir o processo.")
            except Error:
                flash("Não foi possível validar o munícipe no banco de dados.", "danger")
                return render_template("processo/processo-form.html", dados=request.form.to_dict())

        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template("processo/processo-form.html", dados=request.form.to_dict())

        try:
            execute_insert(
                "INSERT INTO processos (municipe_id, data_execucao, solicitacao, "
                "local_execucao, secretaria_destinada) VALUES (%s, %s, %s, %s, %s)",
                (municipe["id"], data_execucao, solicitacao, local_execucao, secretaria_destinada),
            )
        except Error:
            flash("Não foi possível cadastrar o processo. Confira os dados informados.", "danger")
            return render_template("processo/processo-form.html", dados=request.form.to_dict())

        flash("Processo simples cadastrado com sucesso!", "success")
        return redirect(url_for("listagem_processo"))
    return render_template("processo/processo-form.html", dados={})


## mostra os processos cadastrados
@app.route("/listagem_processo")
@login_required
def listagem_processo():
    try:
        processos = listar_processos()
    except Error:
        flash("Não foi possível carregar os processos.", "danger")
        processos = []
    return render_template("processo/processo-listar.html", processos=processos)

## particularidade do nosso sistema
## detalha processo, teve de ser incrementado, pois se o processo fosse mostrado na página de listagem, ia ficar ruim a interface
@app.route("/visualizar_processo/<int:registro_id>")
@login_required
def visualizar_processo(registro_id):
    try:
        processo = buscar_processo_por_id(registro_id)
    except Error:
        flash("Não foi possível consultar o processo.", "danger")
        return redirect(url_for("listagem_processo"))
    if not processo:
        flash("Processo não encontrado.", "warning")
        return redirect(url_for("listagem_processo"))
    return render_template("processo/visualizar.html", processo=processo)


## edita o processo que já existe
@app.route("/editar_processo/<int:registro_id>", methods=["GET", "POST"])
@login_required
def editar_processo(registro_id):
    try:
        processo = buscar_processo_por_id(registro_id)
    except Error:
        flash("Não foi possível consultar o processo.", "danger")
        return redirect(url_for("listagem_processo"))
    if not processo:
        flash("Processo não encontrado.", "warning")
        return redirect(url_for("listagem_processo"))

    campos = ["municipe", "data_execucao", "solicitacao", "local_execucao", "secretaria_destinada"]
    if request.method == "POST":
        dados = {campo: request.form.get(campo, "").strip() for campo in campos}
        if any(not dados[campo] for campo in campos):
            flash("Preencha todos os campos obrigatórios.", "danger")
            return render_template("processo/processo-form.html", dados=dados,
                                   editando=True, registro_id=registro_id)
        try:
            municipe = buscar_municipe_por_nome(dados["municipe"])
            if not municipe:
                flash("Munícipe não encontrado. Faça o cadastro antes de abrir o processo.", "danger")
                return render_template("processo/processo-form.html", dados=dados,
                                       editando=True, registro_id=registro_id)
            execute_query(
                "UPDATE processos SET municipe_id=%s, data_execucao=%s, solicitacao=%s, "
                "local_execucao=%s, secretaria_destinada=%s "
                "WHERE id_processo=%s AND deletado_em IS NULL",
                (municipe["id"], dados["data_execucao"], dados["solicitacao"],
                 dados["local_execucao"], dados["secretaria_destinada"], registro_id),
            )
        except Error:
            flash("Não foi possível atualizar o processo.", "danger")
            return render_template("processo/processo-form.html", dados=dados,
                                   editando=True, registro_id=registro_id)
        flash("Processo atualizado com sucesso!", "success")
        return redirect(url_for("listagem_processo"))

    dados = dict(processo)
    dados["data_execucao"] = processo["data_execucao"].isoformat() if processo["data_execucao"] else ""
    return render_template("processo/processo-form.html", dados=dados,
                           editando=True, registro_id=registro_id)


## soft delete do processo
@app.route("/remover_processo/<int:registro_id>", methods=["POST"])
@login_required
def remover_processo(registro_id):
    try:
        processo = buscar_processo_por_id(registro_id)
        if not processo:
            flash("Processo não encontrado.", "warning")
        else:
            execute_query(
                "UPDATE processos SET deletado_em=NOW() "
                "WHERE id_processo=%s AND deletado_em IS NULL",
                (registro_id,),
            )
            flash("Processo removido com sucesso!", "success")
    except Error:
        flash("Não foi possível remover o processo.", "danger")
    return redirect(url_for("listagem_processo"))


## busca relação de munícipe com IM
def buscar_inscricao_por_id(registro_id):
    return execute_one(
        "SELECT i.id_inscricao AS id, m.nome AS municipe, i.municipe_id, i.cnpj, "
        "i.codigo_atividade, i.atividade_secundaria, i.nome_fantasia "
        "FROM inscricoes_municipais i JOIN municipes m ON m.id_municipe=i.municipe_id "
        "WHERE i.id_inscricao=%s AND i.deletado_em IS NULL AND m.deletado_em IS NULL",
        (registro_id,),
    )


## listagem das IM e seus municipes 
def listar_inscricoes():
    return execute_query(
        "SELECT i.id_inscricao AS id, m.nome AS municipe, i.cnpj, i.codigo_atividade, "
        "i.atividade_secundaria, i.nome_fantasia "
        "FROM inscricoes_municipais i JOIN municipes m ON m.id_municipe=i.municipe_id "
        "WHERE i.deletado_em IS NULL AND m.deletado_em IS NULL "
        "ORDER BY i.id_inscricao DESC",
        fetch=True,
    )


## cadastra uma IM, municipe tem que existir (tamo usando try e except)
@app.route("/cadastro_inscricao", methods=["GET", "POST"])
@login_required
def cadastro_inscricao():
    if request.method == "POST":
        municipe_nome = request.form.get("municipe", "").strip()
        cnpj = request.form.get("cnpj", "").strip()
        codigo_atividade = request.form.get("codigo_atividade", "").strip()
        atividade_secundaria = request.form.get("atividade_secundaria", "").strip() or None
        nome_fantasia = request.form.get("nome_fantasia", "").strip()
        erros = []
        if not municipe_nome: erros.append("Informe o nome do munícipe.")
        if not cnpj: erros.append("Informe o CNPJ da empresa.")
        if not codigo_atividade: erros.append("Informe o código de atividade.")
        if not nome_fantasia: erros.append("Informe o nome fantasia.")

        municipe = None
        if not erros:
            try:
                municipe = buscar_municipe_por_nome(municipe_nome)
                if not municipe:
                    erros.append("Munícipe não encontrado. Faça o cadastro antes da inscrição municipal.")
            except Error:
                flash("Não foi possível validar o munícipe no banco de dados.", "danger")
                return render_template("inscricao_municipal/inscricao_municipal-form.html", dados=request.form.to_dict())

        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template("inscricao_municipal/inscricao_municipal-form.html", dados=request.form.to_dict())

        try:
            execute_insert(
                "INSERT INTO inscricoes_municipais (municipe_id, cnpj, codigo_atividade, "
                "atividade_secundaria, nome_fantasia) VALUES (%s, %s, %s, %s, %s)",
                (municipe["id"], cnpj, codigo_atividade, atividade_secundaria, nome_fantasia),
            )
        except Error:
            flash("Não foi possível cadastrar a inscrição. Confira se o CNPJ já está cadastrado.", "danger")
            return render_template("inscricao_municipal/inscricao_municipal-form.html", dados=request.form.to_dict())

        flash("Inscrição municipal cadastrada com sucesso!", "success")
        return redirect(url_for("listagem_inscricao"))
    return render_template("inscricao_municipal/inscricao_municipal-form.html", dados={})


## edita uma IM 
@app.route("/editar_inscricao/<int:registro_id>", methods=["GET", "POST"])
@login_required
def editar_inscricao(registro_id):
    try:
        inscricao = buscar_inscricao_por_id(registro_id)
    except Error:
        flash("Não foi possível consultar a inscrição municipal.", "danger")
        return redirect(url_for("listagem_inscricao"))
    if not inscricao:
        flash("Inscrição municipal não encontrada.", "warning")
        return redirect(url_for("listagem_inscricao"))

    campos = ["municipe", "cnpj", "codigo_atividade", "nome_fantasia"]
    if request.method == "POST":
        dados = {campo: request.form.get(campo, "").strip() for campo in campos}
        dados["atividade_secundaria"] = request.form.get("atividade_secundaria", "").strip() or None
        if any(not dados[campo] for campo in campos):
            flash("Preencha todos os campos obrigatórios.", "danger")
            return render_template("inscricao_municipal/inscricao_municipal-form.html", dados=dados,
                                   editando=True, registro_id=registro_id)
        try:
            municipe = buscar_municipe_por_nome(dados["municipe"])
            if not municipe:
                flash("Munícipe não encontrado. Faça o cadastro antes da inscrição municipal.", "danger")
                return render_template("inscricao_municipal/inscricao_municipal-form.html", dados=dados,
                                       editando=True, registro_id=registro_id)
            execute_query(
                "UPDATE inscricoes_municipais SET municipe_id=%s, cnpj=%s, codigo_atividade=%s, "
                "atividade_secundaria=%s, nome_fantasia=%s "
                "WHERE id_inscricao=%s AND deletado_em IS NULL",
                (municipe["id"], dados["cnpj"], dados["codigo_atividade"],
                 dados["atividade_secundaria"], dados["nome_fantasia"], registro_id),
            )
        except Error:
            flash("Não foi possível atualizar a inscrição. Verifique se o CNPJ já está cadastrado.", "danger")
            return render_template("inscricao_municipal/inscricao_municipal-form.html", dados=dados,
                                   editando=True, registro_id=registro_id)
        flash("Inscrição municipal atualizada com sucesso!", "success")
        return redirect(url_for("listagem_inscricao"))

    return render_template("inscricao_municipal/inscricao_municipal-form.html", dados=inscricao,
                           editando=True, registro_id=registro_id)


## deleta IM, (soft)
@app.route("/remover_inscricao/<int:registro_id>", methods=["POST"])
@login_required
def remover_inscricao(registro_id):
    try:
        inscricao = buscar_inscricao_por_id(registro_id)
        if not inscricao:
            flash("Inscrição municipal não encontrada.", "warning")
        else:
            execute_query(
                "UPDATE inscricoes_municipais SET deletado_em=NOW() "
                "WHERE id_inscricao=%s AND deletado_em IS NULL",
                (registro_id,),
            )
            flash("Inscrição municipal removida com sucesso!", "success")
    except Error:
        flash("Não foi possível remover a inscrição municipal.", "danger")
    return redirect(url_for("listagem_inscricao"))


##lista as IM
@app.route("/listagem_inscricao")
@login_required
def listagem_inscricao():
    try:
        inscricoes = listar_inscricoes()
    except Error:
        flash("Não foi possível carregar as inscrições municipais.", "danger")
        inscricoes = []
    return render_template("inscricao_municipal/inscricao_municipal-listar.html", inscricoes=inscricoes)


## not found
@app.errorhandler(404)
def pagina_nao_encontrada(erro):
    return render_template("404.html"), 404


## erro interno
@app.errorhandler(500)
def erro_interno(erro):
    return render_template("500.html"), 500


## ronan falou que é a ultima coisa do código, não mexer. !!! 
if __name__ == "__main__":
    app.run(debug=True)
