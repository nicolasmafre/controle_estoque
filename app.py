"""
Este é o arquivo principal da aplicação Flask para o sistema de controle de estoque.
Ele define todas as rotas (URLs), a lógica de negócios e a interação com o banco de dados.
"""

# --- Importação e Instalação de Módulos Essenciais ---
import os
import subprocess
import sys
import sqlite3
import json
import locale
from datetime import datetime, timedelta
from functools import wraps
from collections import OrderedDict
import io # Para criar o arquivo em memória
import csv # Para gerar o arquivo CSV
import xml.etree.ElementTree as ET # Import para gerar XML
from xml.dom import minidom # Import para formatar (indentar) o XML

# Bloco para tentar importar as bibliotecas necessárias e instalá-las se não existirem.
try:
    from flask import (Flask, render_template, request, redirect, url_for,
                       session, flash, jsonify, g, Response)
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError:
    print("Tentando instalar dependências ausentes (Flask, Werkzeug)...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "werkzeug"])
        # Reimporta após a instalação
        from flask import (Flask, render_template, request, redirect, url_for,
                           session, flash, jsonify, g, Response )
        from werkzeug.security import generate_password_hash, check_password_hash
        print("Dependências instaladas com sucesso.")
    except Exception as e:
        print(f"Não houve êxito na instalação das bibliotecas fundamentais: {e}")
        print("Por favor, instale 'flask' e 'werkzeug' manualmente.")
        sys.exit(1)

# --- Configuração Inicial da Aplicação Flask ---

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = os.path.join(app.root_path, 'controle_estoque.db')

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_TIME, '')


# --- Gerenciamento Padronizado do Banco de Dados ---

def get_db():
    """
    Abre uma nova conexão com o banco de dados se não houver uma para a requisição atual.
    A conexão é armazenada no objeto `g` do Flask, que é único para cada requisição.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """
    Fecha a conexão com o banco de dados automaticamente no final da requisição.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Lê o schema.sql e cria as tabelas do banco de dados."""
    db = get_db()
    with open('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()
    print("Banco de dados inicializado com sucesso.")

# ===================== NOVO COMANDO DE INICIALIZAÇÃO =====================
@app.cli.command('init-db')
def init_db_command():
    """Cria um novo comando de terminal: 'flask init-db' para inicializar o BD."""
    init_db()
# =======================================================================


def query_db(query, args=(), one=False):
    """
    Executa uma consulta de LEITURA (SELECT) usando a conexão da requisição atual.
    """
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """
    Executa uma consulta de ESCRITA (INSERT, UPDATE, DELETE) e faz o commit.
    """
    db = get_db()
    try:
        db.execute(query, args)
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        print(f"Erro no banco de dados: {e}")


# --- Decorador de Autenticação ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            print('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function

# --- Rotas de Autenticação e Usuário ---
@app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        print('Tentando fazer login...')
        email = request.form['email']
        senha = request.form['senha']
        usuario = query_db('SELECT * FROM usuarios WHERE email = ?', [email], one=True)

        if usuario and check_password_hash(usuario['senha_hash'], senha):
            session['usuario_id'] = usuario['id']
            return redirect(url_for('dashboard'))
        else:
            print('E-mail ou senha inválidos.', 'danger')
    # Verifica se o usuário com ID 1 (administrador) já existe.
    admin_existe = query_db('SELECT id FROM usuarios WHERE id = ?', [1], one=True)

    # Passa a variável 'admin_existe' para o template.
    # A função bool() converterá o resultado (que pode ser uma linha ou None) para True ou False.
    return render_template('index.html', admin_existe=bool(admin_existe))


@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form['nome']
        sobrenome = request.form['sobrenome']
        data_nascimento = request.form['data_nascimento']
        email = request.form['email']
        senha = request.form['senha']
        confirmar_senha = request.form['confirmar_senha']

        if senha != confirmar_senha:
            print('As senhas não coincidem.', 'danger')
            return render_template('registrar.html')

        senha_hash = generate_password_hash(senha)
        try:
            execute_db(
                'INSERT INTO usuarios (nome, sobrenome, data_nascimento, email, senha_hash) VALUES (?, ?, ?, ?, ?)',
                (nome, sobrenome, data_nascimento, email, senha_hash))
            print('Registro bem-sucedido! Faça o login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            print('Este e-mail já está cadastrado.', 'danger')
    return render_template('registrar.html')


@app.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form['email']
        data_nascimento = request.form['data_nascimento']
        usuario = query_db("SELECT * FROM usuarios WHERE email = ? AND data_nascimento = ?", (email, data_nascimento),
                           one=True)
        if usuario:
            session['email_recuperacao'] = email
            return render_template('recuperar_senha.html', mostrar_novo_formulario=True, email=email)
        else:
            print('E-mail ou data de nascimento incorretos.', 'danger')
    return render_template('recuperar_senha.html', mostrar_novo_formulario=False)


@app.route('/atualizar_senha', methods=['POST'])
def atualizar_senha():
    email = request.form.get('email') or session.get('email_recuperacao')
    nova_senha = request.form['nova_senha']
    confirmar_senha = request.form['confirmar_senha']

    if not email:
        print('Sessão de recuperação expirada. Tente novamente.', 'danger')
        return redirect(url_for('recuperar_senha'))
    if nova_senha != confirmar_senha:
        print('As senhas não correspondem.', 'danger')
        return render_template('recuperar_senha.html', mostrar_novo_formulario=True, email=email)

    senha_hash = generate_password_hash(nova_senha)
    execute_db("UPDATE usuarios SET senha_hash = ? WHERE email = ?", (senha_hash, email))
    session.pop('email_recuperacao', None)
    print('Senha atualizada com sucesso!', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    usuario = query_db('SELECT nome FROM usuarios WHERE id = ?', [session['usuario_id']], one=True)
    return render_template('dashboard.html', usuario=usuario)


@app.route('/logout')
def logout():
    session.clear()
    print('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('login'))


# --- Rotas de Gerenciamento de Roupas ---
@app.route('/adicionar_roupa', methods=['GET', 'POST'])
@login_required
def adicionar_roupa():
    if request.method == 'POST':
        try:
            execute_db('''
                       INSERT INTO roupas (usuario_id, codigo_produto, data_entrada, tipo_roupa, tecido, quantidade,
                                           cor, tamanhos, detalhes, preco_unitario, quantida_vendas)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ''', (session['usuario_id'], request.form['codigo_produto'], request.form['data_entrada'],
                             request.form['tipo_roupa'],
                             request.form['tecido'], request.form['quantidade'], request.form['cor'],
                             request.form['tamanhos'],
                             request.form['detalhes'], request.form['preco_unitario'], 0))
            print('Roupa adicionada com sucesso!', 'success')
            return redirect(url_for('listar_roupas'))
        except Exception as e:
            print(f"Ocorreu um erro ao adicionar a roupa: {e}", "danger")
    return render_template('adicionar_roupa.html')


@app.route('/listar_roupas')
@login_required
def listar_roupas():
    ordenar_por = request.args.get('ordenar_por', 'id')
    ordem = request.args.get('ordem', 'asc')
    campos_validos = ['id', 'codigo_produto', 'tipo_roupa', 'tecido', 'quantidade', 'cor', 'tamanhos', 'detalhes',
                      'preco_unitario', 'quantida_vendas']
    if ordenar_por not in campos_validos:
        ordenar_por = 'id'
    if ordem.upper() not in ['ASC', 'DESC']:
        ordem = 'ASC'

    query = f"SELECT * FROM roupas WHERE usuario_id = ? ORDER BY {ordenar_por} {ordem}"
    roupas = query_db(query, [session['usuario_id']])

    def url_for_listar_roupas(campo_ordenacao, ordem_padrao, campo_atual, ordem_atual):
        nova_ordem = 'desc' if campo_ordenacao == campo_atual and ordem_atual == 'asc' else 'asc'
        return url_for('listar_roupas', ordenar_por=campo_ordenacao, ordem=nova_ordem)

    return render_template('listar_roupas.html', roupas=roupas, ordenar_por=ordenar_por, ordem=ordem,
                           url_for_listar_roupas=url_for_listar_roupas)


@app.route('/editar_roupa/<int:roupa_id>', methods=['GET', 'POST'])
@login_required
def editar_roupa(roupa_id):
    db = get_db()
    roupa = db.execute('SELECT * FROM roupas WHERE id = ? AND usuario_id = ?',
                       (roupa_id, session['usuario_id'])).fetchone()
    if roupa is None:
        print('Roupa não encontrada.', 'warning')
        return redirect(url_for('listar_roupas'))

    if request.method == 'POST':
        try:
            quantidade_nova = int(request.form['quantidade'])
            vendas_novas = roupa['quantida_vendas'] if roupa['quantida_vendas'] is not None else 0
            if quantidade_nova < roupa['quantidade']:
                vendas_novas += roupa['quantidade'] - quantidade_nova

            if quantidade_nova < 0:
                print('A quantidade em estoque não pode ser negativa.', 'danger')
                return render_template('editar_roupa.html', roupa=roupa)

            db.execute('''
                       UPDATE roupas
                       SET codigo_produto  = ?,
                           tipo_roupa      = ?,
                           tecido          = ?,
                           quantidade      = ?,
                           quantida_vendas = ?,
                           cor             = ?,
                           tamanhos        = ?,
                           detalhes        = ?,
                           preco_unitario  = ?
                       WHERE id = ?
                       ''', (request.form['codigo_produto'], request.form['tipo_roupa'], request.form['tecido'],
                             quantidade_nova, vendas_novas, request.form['cor'], request.form['tamanhos'],
                             request.form['detalhes'], float(request.form['preco_unitario']), roupa_id))
            db.commit()
            print('Roupa atualizada com sucesso!', 'success')
            return redirect(url_for('listar_roupas'))
        except Exception as e:
            print(f'Ocorreu um erro ao editar a roupa: {e}', 'danger')
            return redirect(url_for('listar_roupas'))

    return render_template('editar_roupa.html', roupa=roupa)

# --- ROTAS DE GERENCIAMENTO DE FUNCIONÁRIOS ---
@app.route('/gerenciar_funcionarios')
@login_required
def gerenciar_funcionarios():
    """ Rota para listar todos os funcionários, agora com dados de vendas do mês atual."""
    ordenar_por = request.args.get('ordenar_por', 'nome_completo')
    ordem = request.args.get('ordem', 'asc')

    # Adiciona os novos campos calculados à lista de campos válidos para ordenação
    campos_validos = ['nome_completo', 'cargo', 'data_inicio_contrato', 'total_valor_mes', 'numero_vendas_mes']
    if ordenar_por not in campos_validos:
        ordenar_por = 'nome_completo'
    if ordem.upper() not in ['ASC', 'DESC']:
        ordem = 'ASC'

    # Query aprimorada com LEFT JOIN para buscar dados de vendas do mês atual
    query = f"""
        SELECT
            f.id, f.nome_completo, f.cargo, f.data_inicio_contrato, f.data_fim_contrato, f.cidade, f.estado,
            COALESCE(SUM(v.valor_total_venda), 0) as total_valor_mes,
            COUNT(v.id) as numero_vendas_mes
        FROM 
            funcionarios f
        LEFT JOIN 
            vendas v ON f.id = v.funcionario_id AND STRFTIME('%Y-%m', v.data_venda) = STRFTIME('%Y-%m', 'now', 'localtime')
        WHERE 
            f.usuario_id = ?
        GROUP BY 
            f.id
        ORDER BY 
            {ordenar_por} {ordem}
    """
    funcionarios = query_db(query, [session['usuario_id']])
    return render_template('listar_funcionarios.html', funcionarios=funcionarios, ordenar_por=ordenar_por, ordem=ordem)

@app.route('/cadastrar_funcionario', methods=['GET', 'POST'])
@login_required
def cadastrar_funcionario():
    """ Rota para cadastrar um novo funcionário."""
    if request.method == 'POST':
        try:
            # Verifica se a checkbox 'is_gerente' foi marcada. Se sim, o valor é 'on'.
            is_gerente = 1 if 'is_gerente' in request.form else 0

            dados = (
                session['usuario_id'],
                request.form['nome_completo'], request.form['cep'], request.form['rua'],
                request.form['numero'], request.form['cidade'], request.form['estado'],
                request.form['pais'], request.form['data_inicio_contrato'],
                request.form.get('data_fim_contrato') or None,
                request.form['cargo'], request.form['definicao_cargo'],
                request.form.get('observacoes') or None,
                is_gerente # Adiciona o novo campo
            )
            execute_db('''
                       INSERT INTO funcionarios (usuario_id, nome_completo, cep, rua, numero, cidade, estado, pais,
                                                 data_inicio_contrato, data_fim_contrato, cargo, definicao_cargo,
                                                 observacoes, is_gerente)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ''', dados)
            print('Funcionário cadastrado com sucesso!', 'success')
            return redirect(url_for('gerenciar_funcionarios'))
        except Exception as e:
            print(f'Erro ao cadastrar funcionário: {e}', 'danger')
    return render_template('cadastrar_funcionario.html')

@app.route('/editar_funcionario/<int:funcionario_id>', methods=['GET', 'POST'])
@login_required
def editar_funcionario(funcionario_id):
    """ Rota para editar um funcionário existente."""
    db = get_db()
    funcionario = db.execute("SELECT * FROM funcionarios WHERE id = ? AND usuario_id = ?",
                             (funcionario_id, session['usuario_id'])).fetchone()
    if funcionario is None:
        print('Funcionário não encontrado.', 'warning')
        return redirect(url_for('gerenciar_funcionarios'))

    if request.method == 'POST':
        try:
            is_gerente = 1 if 'is_gerente' in request.form else 0
            dados = (
                request.form['nome_completo'], request.form['cep'], request.form['rua'],
                request.form['numero'], request.form['cidade'], request.form['estado'],
                request.form['pais'], request.form['data_inicio_contrato'],
                request.form.get('data_fim_contrato') or None,
                request.form['cargo'], request.form['definicao_cargo'],
                request.form.get('observacoes') or None,
                is_gerente, # Adiciona o novo campo
                funcionario_id, session['usuario_id']
            )
            db.execute('''
                       UPDATE funcionarios
                       SET nome_completo = ?, cep = ?, rua = ?, numero = ?, cidade = ?, estado = ?, 
                           pais = ?, data_inicio_contrato = ?, data_fim_contrato = ?, cargo = ?, 
                           definicao_cargo = ?, observacoes = ?, is_gerente = ?
                       WHERE id = ? AND usuario_id = ?
                       ''', dados)
            db.commit()
            print('Funcionário atualizado com sucesso!', 'success')
            return redirect(url_for('gerenciar_funcionarios'))
        except Exception as e:
            print(f'Ocorreu um erro ao editar o funcionário: {e}', 'danger')
            return redirect(url_for('gerenciar_funcionarios'))

    return render_template('editar_funcionario.html', funcionario=funcionario)

# --- Rotas de Gerenciamento da Empresa ---
@app.route('/dados_empresa')
@login_required
def dados_empresa():
    usuario_id = session['usuario_id']
    usuario = query_db("SELECT * FROM usuarios WHERE id = ?", [usuario_id], one=True)
    empresa = query_db("SELECT * FROM empresas WHERE usuario_id = ?", [usuario_id], one=True)

    data_nascimento_formatada = None
    if usuario and usuario['data_nascimento']:
        try:
            data_nascimento_dt = datetime.strptime(usuario['data_nascimento'], '%d/%m/%Y')
            data_nascimento_formatada = data_nascimento_dt.strftime('%d/%m/%Y')
        except ValueError:
            data_nascimento_formatada = usuario['data_nascimento']

    return render_template('dados_empresa.html',
                           usuario=usuario,
                           empresa=empresa,
                           data_nascimento_formatada=data_nascimento_formatada)

@app.route('/atualizar_dados_empresa', methods=['GET', 'POST'])
@login_required
def atualizar_dados_empresa():
    # Esta rota permite que o usuário atualize os dados da empresa e seus próprios dados (nome, sobrenome, data de nascimento).
    # A rota aceita requisições GET (para exibir o formulário preenchido com os dados atuais) e POST (para processar os dados atualizados).

    if 'usuario_id' not in session:
        # Verifica se o usuário está logado. Se o 'usuario_id' não estiver na sessão,
        # redireciona o usuário para a página de login.
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    # Recupera os dados do usuário
    cursor.execute("SELECT nome, sobrenome, data_nascimento, email FROM usuarios WHERE id = ?",
                   (session['usuario_id'],))
    # Executa uma query para selecionar o nome, sobrenome, data de nascimento e email do usuário
    # na tabela 'usuarios', filtrando pelo ID do usuário armazenado na sessão.
    usuario = cursor.fetchone()
    # Obtém o resultado da query e armazena na variável 'usuario'.

    # Recupera os dados da empresa (se existir)
    cursor.execute("SELECT * FROM empresas WHERE usuario_id = ?", (session['usuario_id'],))
    # Executa uma query para selecionar todos os dados da empresa na tabela 'empresas',
    # filtrando pelo ID do usuário armazenado na sessão.
    empresa = cursor.fetchone()
    # Obtém o resultado da query e armazena na variável 'empresa'. Se não existir empresa
    # associada ao usuário, 'empresa' será None.

    # Converte a data de nascimento para o formato YYYY-MM-DD
    if usuario and usuario['data_nascimento']:
        # Verifica se o usuário existe e se possui uma data de nascimento.
        try:
            data_nascimento_dt = datetime.strptime(usuario['data_nascimento'], '%d/%m/%Y')
            # Converte a data de nascimento do formato string ('%d/%m/%Y') para um objeto datetime.
            data_nascimento_formatada = data_nascimento_dt.strftime('%Y-%m-%d')
            # Formata a data de nascimento para o formato 'YYYY-MM-DD' para ser exibida no formulário HTML.
        except ValueError:
            data_nascimento_formatada = None  # Ou defina um valor padrão
            # Se a data de nascimento não estiver no formato esperado, define 'data_nascimento_formatada' como None.
    else:
        data_nascimento_formatada = None
    # Se o usuário não existir ou não tiver data de nascimento, define 'data_nascimento_formatada' como None.

    if request.method == 'POST':
        # Se a requisição for do tipo POST, significa que o formulário de atualização foi enviado.
        nome = request.form['nome']
        # Obtem os dados do formulário
        sobrenome = request.form['sobrenome']
        data_nascimento = request.form['data_nascimento']
        nome_fantasia = request.form['nome_fantasia']
        cnpj_sim = request.form['cnpj_sim']
        cnpj = request.form['cnpj'] if cnpj_sim == 'sim' else None
        razao_social = request.form['razao_social'] if cnpj_sim == 'sim' else None
        cnae = request.form['cnae'] if cnpj_sim == 'sim' else None
        inscricao_estadual = request.form['inscricao_estadual'] if cnpj_sim == 'sim' else None
        inscricao_municipal = request.form['inscricao_municipal'] if cnpj_sim == 'sim' else None
        regime_tributario = request.form['regime_tributario'] if cnpj_sim == 'sim' else None
        cep = request.form['cep']
        rua = request.form['rua']
        bairro = request.form['bairro']
        cidade = request.form['cidade']
        estado = request.form['estado']
        pais = request.form['pais']
        # Recupera os dados do formulário enviados via POST.

        try:
            # Converte a data de nascimento para o formato correto antes de salvar no banco
            data_nascimento_dt = datetime.strptime(data_nascimento, '%Y-%m-%d')
            # Converte a data de nascimento do formato 'YYYY-MM-DD' (vindo do formulário) para um objeto datetime.
            data_nascimento_db = data_nascimento_dt.strftime('%d/%m/%Y')
            # Formata a data de nascimento para o formato '%d/%m/%Y' para ser armazenada no banco de dados.

            # Atualiza os dados do usuário
            cursor.execute("UPDATE usuarios SET nome = ?, sobrenome = ?, data_nascimento = ? WHERE id = ?",
                           (nome, sobrenome, data_nascimento_db, session['usuario_id']))
            # Executa uma query para atualizar o nome, sobrenome e data de nascimento do usuário na tabela 'usuarios',
            # filtrando pelo ID do usuário armazenado na sessão.

            # Se a empresa já existir, eu atualizo os dados
            if empresa:
                cursor.execute('''
                               UPDATE empresas
                               SET nome_fantasia = ?,
                                   cnpj          = ?,
                                   razao_social  = ?,
                                   cnae          = ?,
                                   cep           = ?,
                                   rua           = ?,
                                   bairro        = ?,
                                   cidade        = ?,
                                   estado        = ?,
                                   pais          = ?,
                                   inscricao_estadual = ?,
                                   inscricao_municipal = ?,
                                   regime_tributario = ?
                               WHERE usuario_id = ?
                ''', (nome_fantasia, cnpj, razao_social, cnae, cep, rua, bairro, cidade, estado, pais, inscricao_estadual, inscricao_municipal, regime_tributario,
                      session['usuario_id']))
                # Executa uma query para atualizar os dados da empresa na tabela 'empresas',
                # filtrando pelo ID do usuário armazenado na sessão.
            # Se a empresa não existir, eu crio uma nova
            else:
                cursor.execute('''
                               INSERT INTO empresas (usuario_id, nome_fantasia, cnpj, razao_social, cnae,
                                                     cep, rua, bairro, cidade, estado, pais, inscricao_estadual,
                                                     inscricao_municipal, regime_tributario)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (session['usuario_id'], nome_fantasia, cnpj, razao_social, cnae, cep, rua, bairro,
                      cidade, estado, pais, inscricao_estadual, inscricao_municipal, regime_tributario))
                # Executa uma query para inserir os dados da nova empresa na tabela 'empresas'.

            db.commit()
            # Commita as alterações no banco de dados.
            print('Dados atualizados com sucesso!', 'success')
            return redirect(url_for('dados_empresa'))
            # Redireciona o usuário para a página 'dados_empresa' para visualizar os dados atualizados.

        except Exception as e:
            print(f'Erro ao atualizar dados: {str(e)}', 'error')
            return render_template('atualizar_dados_empresa.html', usuario=usuario, empresa=empresa,
                                   nome=usuario['nome'], sobrenome=usuario['sobrenome'],
                                   data_nascimento=data_nascimento_formatada, email=usuario['email'])
            # Em caso de erro, exibe uma mensagem de erro e renderiza o template 'atualizar_dados_empresa.html'
            # novamente, preenchendo o formulário com os dados existentes para que o usuário possa corrigir.

    return render_template('atualizar_dados_empresa.html', usuario=usuario, empresa=empresa, nome=usuario['nome'],
                           sobrenome=usuario['sobrenome'], data_nascimento=data_nascimento_formatada,
                           email=usuario['email'])
    # Se a requisição for do tipo GET, renderiza o template 'atualizar_dados_empresa.html', preenchendo o
    # formulário com os dados do usuário e da empresa (se existirem).


# --- Rotas de Gerenciamento de Clientes ---
@app.route('/painel_clientes')
@login_required
def painel_clientes():
    """
    Rota para o painel de gerenciamento de clientes, agora incluindo
    métricas de histórico de compras.
    """
    usuario_id = session['usuario_id']
    data_limite_3m = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    query = """
            SELECT c.id, \
                   c.nome, \
                   c.telefone, \
                   COUNT(DISTINCT v.data_venda)                                                      as total_compras, \
                   COALESCE(SUM(CASE WHEN v.data_venda >= ? THEN v.valor_total_venda ELSE 0 END), 0) as total_gasto_3m
            FROM clientes c \
                     LEFT JOIN \
                 vendas v ON c.id = v.cliente_id AND v.usuario_id = c.usuario_id
            WHERE c.usuario_id = ?
            GROUP BY c.id, c.nome, c.telefone
            ORDER BY c.nome; \
            """
    clientes = query_db(query, (data_limite_3m, usuario_id))

    return render_template('painel_clientes.html', clientes=clientes)

@app.route('/cadastrar_cliente', methods=['POST'])
@login_required
def cadastrar_cliente():
    try:
        execute_db('INSERT INTO clientes (usuario_id, nome, telefone) VALUES (?, ?, ?)',
                   (session['usuario_id'], request.form['nome-cliente'], request.form['telefone-cliente']))
        print('Cliente cadastrado com sucesso!', 'success')
    except Exception as e:
        print(f'Erro ao cadastrar cliente: {e}', 'danger')
    return redirect(url_for('painel_clientes'))


@app.route('/editar_cliente/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(cliente_id):
    db = get_db()
    cliente = db.execute("SELECT * FROM clientes WHERE id = ? AND usuario_id = ?",
                         (cliente_id, session['usuario_id'])).fetchone()
    if cliente is None:
        print('Cliente não encontrado.', 'warning')
        return redirect(url_for('painel_clientes'))

    if request.method == 'POST':
        try:
            db.execute('UPDATE clientes SET nome = ?, telefone = ? WHERE id = ? AND usuario_id = ?',
                       (request.form['nome-cliente'], request.form['telefone-cliente'], cliente_id,
                        session['usuario_id']))
            db.commit()
            print('Cliente atualizado com sucesso!', 'success')
            return redirect(url_for('painel_clientes'))
        except Exception as e:
            print(f'Ocorreu um erro ao editar o cliente: {e}', 'danger')
            return redirect(url_for('painel_clientes'))

    return render_template('editar_cliente.html', cliente=cliente)


# --- Rotas do Painel de Compras e API ---
@app.route('/painel_compras')
@login_required
def painel_compras():
    """ Rota que exibe a interface principal para registrar novas compras/vendas."""
    # Busca o nome do usuário logado para usar como vendedor padrão
    usuario = query_db('SELECT nome FROM usuarios WHERE id = ?', [session['usuario_id']], one=True)
    return render_template('painel_compras.html', usuario=usuario)

@app.route('/vender_roupa', methods=['POST'])
@login_required
def vender_roupa():
    print('Ação de venda registrada, mas a lógica final está em "Finalizar Compra".', 'info')
    return redirect(url_for('painel_compras'))


@app.route('/buscar_funcionarios')
@login_required
def buscar_funcionarios():
    """
    API: Busca funcionários ATIVOS para o autocompletar do painel de compras.
    Funcionários com data_fim_contrato preenchida são considerados inativos.
    """
    termo = f"%{request.args.get('query', '')}%"

    # A query foi modificada para incluir a condição de funcionário ativo
    query = """
            SELECT id, nome_completo
            FROM funcionarios
            WHERE nome_completo LIKE ?
              AND usuario_id = ?
              AND (data_fim_contrato IS NULL OR data_fim_contrato = '')
            ORDER BY nome_completo LIMIT 10 \
            """

    funcionarios_rows = query_db(query, (termo, session['usuario_id']))
    return jsonify([dict(row) for row in funcionarios_rows])

@app.route('/buscar_clientes')
@login_required
def buscar_clientes():
    termo = f"%{request.args.get('query', '')}%"
    clientes_rows = query_db(
        'SELECT id, nome FROM clientes WHERE nome LIKE ? AND usuario_id = ? ORDER BY nome LIMIT 10',
        (termo, session['usuario_id']))
    return jsonify([dict(row) for row in clientes_rows])

@app.route('/buscar_produtos')
@login_required
def buscar_produtos():
    """
    API: Busca produtos para o autocompletar do painel de compras,
    filtrando para incluir apenas aqueles com quantidade em estoque maior que zero.
    """
    termo = f"%{request.args.get('query', '')}%"

    query = """
            SELECT id, codigo_produto
            FROM roupas
            WHERE codigo_produto LIKE ?
              AND usuario_id = ?
              AND quantidade > 0
            ORDER BY codigo_produto LIMIT 10 \
            """

    produtos_rows = query_db(query, (termo, session['usuario_id']))
    return jsonify([dict(row) for row in produtos_rows])

@app.route('/buscar_detalhes_produto')
@login_required
def buscar_detalhes_produto():
    codigo = request.args.get('codigo', '')
    produto = query_db(
        'SELECT codigo_produto, tipo_roupa, cor, detalhes FROM roupas WHERE codigo_produto = ? AND usuario_id = ?',
        [codigo, session['usuario_id']], one=True)
    return jsonify(dict(produto) if produto else None)


@app.route('/buscar_produto_route')
@login_required
def buscar_produto_route():
    codigo = request.args.get('codigo', '')
    produto = query_db('SELECT * FROM roupas WHERE codigo_produto = ? AND usuario_id = ?',
                       [codigo, session['usuario_id']], one=True)
    return jsonify(dict(produto) if produto else None)


# --- Rotas do Fluxo de Finalização de Compra ---
@app.route('/revisar_compra', methods=['POST'])
@login_required
def revisar_compra():
    dados_carrinho_json = request.form.get('dados_carrinho')
    if not dados_carrinho_json:
        print('Nenhum dado de compra recebido.', 'danger')
        return redirect(url_for('painel_compras'))
    dados_compra = json.loads(dados_carrinho_json)
    total_compra = sum(float(item['preco']) for item in dados_compra['itens'])
    return render_template('revisar_compra.html', compra=dados_compra, total=total_compra,
                           dados_carrinho_json=dados_carrinho_json)


@app.route('/finalizar_compra', methods=['POST'])
@login_required
def finalizar_compra():
    """
    Rota que processa a compra, atualizando o estoque e registrando a venda.
    """
    dados_carrinho_json = request.form.get('dados_carrinho')
    if not dados_carrinho_json:
        print('Erro ao processar a compra. Tente novamente.', 'danger')
        return redirect(url_for('painel_compras'))

    dados_compra = json.loads(dados_carrinho_json)
    usuario_id = session['usuario_id']
    db = get_db()
    try:
        # Primeiro, precisamos do ID do cliente
        cliente = db.execute('SELECT id FROM clientes WHERE nome = ? AND usuario_id = ?',
                             (dados_compra['cliente'], usuario_id)).fetchone()
        if not cliente:
            raise Exception(f"Cliente '{dados_compra['cliente']}' não encontrado.")
        cliente_id = cliente['id']

        # Busca o ID do funcionário (se houver)
        vendedor_nome = dados_compra.get('vendedor')
        funcionario_id = None
        if vendedor_nome and vendedor_nome != 'Nenhum' and vendedor_nome != \
                query_db('SELECT nome FROM usuarios WHERE id = ?', [usuario_id], one=True)['nome']:
            funcionario = db.execute('SELECT id FROM funcionarios WHERE nome_completo = ? AND usuario_id = ?',
                                     (vendedor_nome, usuario_id)).fetchone()
            if funcionario:
                funcionario_id = funcionario['id']

        # Itera sobre cada item do carrinho
        for item in dados_compra['itens']:
            roupa = db.execute('SELECT id FROM roupas WHERE codigo_produto = ? AND usuario_id = ?',
                               (item['codigo'], usuario_id)).fetchone()
            if not roupa:
                continue

            roupa_id = roupa['id']

            # 1. Insere o registro na nova tabela 'vendas'
            db.execute('''
                       INSERT INTO vendas (usuario_id, cliente_id, roupa_id, funcionario_id, quantidade_vendida,
                                           valor_total_venda, data_venda)
                       VALUES (?, ?, ?, ?, ?, ?, DATE ('now', 'localtime'))
                       ''', (usuario_id, cliente_id, roupa_id, funcionario_id, int(item['quantidade']),
                             float(item['preco'])))

            # 2. Atualiza o estoque e a contagem total de vendas na tabela 'roupas'
            db.execute('''
                       UPDATE roupas
                       SET quantidade      = quantidade - ?,
                           quantida_vendas = COALESCE(quantida_vendas, 0) + ?
                       WHERE id = ?
                         AND usuario_id = ?
                       ''', (int(item['quantidade']), int(item['quantidade']), roupa_id, usuario_id))

        db.commit()
        print('Compra finalizada com sucesso!', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        db.rollback()
        print(f'Ocorreu um erro ao finalizar a compra: {e}', 'danger')
        return redirect(url_for('painel_compras'))

# --- Rotas de Métricas e Gráficos ---
@app.route('/metrica')
@login_required
def metrica():
    """ Rota para a página que exibe os gráficos de métricas GERAIS."""
    return render_template('metrica.html')

@app.route('/metrica_funcionarios')
@login_required
def metrica_funcionarios():
    """ Rota para a NOVA página que exibe a análise de performance dos funcionários."""
    return render_template('metrica_funcionarios.html')

@app.route('/metrica_clientes')
@login_required
def metrica_clientes():
    return render_template('metrica_clientes.html')

@app.route('/dados_dashboard_metricas')
@login_required
def dados_dashboard_metricas():
    """
    API aprimorada que fornece todos os dados para o dashboard de métricas de uma vez.
    """
    usuario_id = session['usuario_id']

    # --- 1. Dados de Vendas Mensais (Gráfico de Barras) ---
    meses_template = OrderedDict()
    hoje = datetime.now()
    for i in range(12):
        ano, mes = hoje.year, hoje.month
        mes_iter = mes - i
        ano_iter = ano
        if mes_iter <= 0:
            mes_iter += 12
            ano_iter -= 1
        chave_mes = f"{ano_iter:04d}-{mes_iter:02d}"
        meses_template[chave_mes] = 0

    meses_template = OrderedDict(reversed(list(meses_template.items())))
    data_inicio_filtro = list(meses_template.keys())[0] + "-01"

    query_vendas = """
                   SELECT strftime('%Y-%m', data_venda) as mes, SUM(valor_total_venda) as total
                   FROM vendas
                   WHERE usuario_id = ?
                     AND data_venda >= ?
                   GROUP BY mes
                   ORDER BY mes;
                   """
    resultados_vendas = query_db(query_vendas, (usuario_id, data_inicio_filtro))

    if resultados_vendas:
        for linha in resultados_vendas:
            if linha['mes'] in meses_template:
                meses_template[linha['mes']] = linha['total'] or 0

    labels_meses = [datetime.strptime(chave, '%Y-%m').strftime('%b/%y').capitalize() for chave in meses_template.keys()]
    valores_meses = list(meses_template.values())

    # --- 2. KPIs (Indicadores-Chave) ---
    total_vendas_12m = sum(valores_meses)
    media_mensal = total_vendas_12m / 12 if valores_meses else 0
    melhor_mes_valor = 0
    melhor_mes_label = "N/A"
    if valores_meses:
        melhor_mes_valor = max(valores_meses)
        if melhor_mes_valor > 0:
            idx = valores_meses.index(melhor_mes_valor)
            melhor_mes_label = labels_meses[idx]

    # --- 3. Top 10 Produtos (Gráfico de Pizza) ---
    query_top_produtos = """
                         SELECT r.tipo_roupa, SUM(v.valor_total_venda) as total_vendido
                         FROM vendas v
                                  JOIN roupas r ON v.roupa_id = r.id
                         WHERE v.usuario_id = ?
                           AND v.data_venda >= ?
                         GROUP BY r.tipo_roupa
                         ORDER BY total_vendido DESC LIMIT 6;
                         """
    resultados_top = query_db(query_top_produtos, (usuario_id, data_inicio_filtro))

    labels_top_produtos = [row['tipo_roupa'] for row in resultados_top] if resultados_top else []
    valores_top_produtos = [row['total_vendido'] for row in resultados_top] if resultados_top else []

    # --- 4. NOVO CÁLCULO DE PROJEÇÃO DE VENDAS ---
    projecao_percentual = 0
    projecao_cor = "grey"  # Cor padrão para 'estável'

    # Só calcula a projeção se tivermos pelo menos 3 meses de dados
    if len(valores_meses) >= 3:
        ultimos_3_meses = valores_meses[-3:]
        ultimo_mes = ultimos_3_meses[2]

        # Calcula a média da variação entre os últimos 3 meses
        variacao1 = ultimos_3_meses[1] - ultimos_3_meses[0]
        variacao2 = ultimos_3_meses[2] - ultimos_3_meses[1]
        media_variacao = (variacao1 + variacao2) / 2

        # Projeta o valor para o próximo mês
        valor_projetado = ultimo_mes + media_variacao

        if ultimo_mes > 0:
            projecao_percentual = ((valor_projetado - ultimo_mes) / ultimo_mes) * 100

        # Define a cor baseada na sua regra de negócio
        if valor_projetado > melhor_mes_valor and melhor_mes_valor > 0:
            projecao_cor = "blue"
        elif projecao_percentual > 0:
            projecao_cor = "green"
        elif projecao_percentual < 0:
            projecao_cor = "red"

    # --- Montagem da Resposta JSON Final ---
    dados_finais = {
        "monthly_sales": {
            "labels": labels_meses,
            "values": valores_meses
        },
        "kpis": {
            "total": f"R$ {total_vendas_12m:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "average": f"R$ {media_mensal:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "best_month_label": melhor_mes_label,
            "best_month_value": f"R$ {melhor_mes_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "projection": {
                "value": f"{'+' if projecao_percentual > 0 else ''}{projecao_percentual:.1f}%",
                "color": projecao_cor
            }
        },
        "top_products": {
            "labels": labels_top_produtos,
            "values": valores_top_produtos
        }
    }
    return jsonify(dados_finais)

@app.route('/dados_metricas_funcionarios')
@login_required
def dados_metricas_funcionarios():
    """
    API que fornece todos os dados para o dashboard de performance de funcionários.
    """
    usuario_id = session['usuario_id']
    hoje = datetime.now()
    data_inicio_12m = (hoje - timedelta(days=365)).strftime('%Y-%m-%d')

    # --- 1. Top 10 Vendedores (Gráfico de Barras) ---
    query_top_vendedores = """
                           SELECT f.nome_completo, SUM(v.valor_total_venda) as total_vendido
                           FROM vendas v \
                                    JOIN funcionarios f ON v.funcionario_id = f.id
                           WHERE v.usuario_id = ? \
                             AND v.data_venda >= ?
                           GROUP BY f.nome_completo \
                           ORDER BY total_vendido DESC LIMIT 10; \
                           """
    resultados_top = query_db(query_top_vendedores, (usuario_id, data_inicio_12m))

    top_vendedores_labels = [row['nome_completo'] for row in resultados_top] if resultados_top else []
    top_vendedores_valores = [row['total_vendido'] for row in resultados_top] if resultados_top else []

    # --- 2. Vendas Trimestrais por Funcionário (Gráfico de Barras Agrupado) ---
    query_vendas_trimestrais = """
                               SELECT f.nome_completo, v.data_venda, v.valor_total_venda
                               FROM vendas v \
                                        JOIN funcionarios f ON v.funcionario_id = f.id
                               WHERE v.usuario_id = ? \
                                 AND v.data_venda >= ?
                               ORDER BY v.data_venda; \
                               """
    resultados_trimestrais = query_db(query_vendas_trimestrais, (usuario_id, data_inicio_12m))

    # Define os 4 trimestres passados
    trimestres = OrderedDict()
    for i in range(4):
        fim_trimestre = hoje - timedelta(days=i * 90)
        label = f"T{(fim_trimestre.month - 1) // 3 + 1}/{fim_trimestre.year}"
        trimestres[label] = {}

    trimestres_labels = list(reversed(list(trimestres.keys())))

    vendas_por_funcionario = {}
    if resultados_trimestrais:
        for venda in resultados_trimestrais:
            nome = venda['nome_completo']
            valor = venda['valor_total_venda']
            data_venda = datetime.strptime(venda['data_venda'], '%Y-%m-%d')

            if nome not in vendas_por_funcionario:
                vendas_por_funcionario[nome] = {label: 0 for label in trimestres_labels}

            # Encontra a qual trimestre a venda pertence
            for label in reversed(trimestres_labels):
                trimestre_num, ano = map(int, label.replace('T', '').split('/'))
                mes_inicio_trimestre = (trimestre_num - 1) * 3 + 1
                if data_venda.year == ano and data_venda.month >= mes_inicio_trimestre and data_venda.month <= mes_inicio_trimestre + 2:
                    vendas_por_funcionario[nome][label] += valor
                    break

    # Cores para o gráfico
    cores = ['rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)', 'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)',
             'rgba(153, 102, 255, 0.7)']
    datasets_trimestrais = []
    for i, nome in enumerate(vendas_por_funcionario.keys()):
        datasets_trimestrais.append({
            "label": nome,
            "data": list(vendas_por_funcionario[nome].values()),
            "backgroundColor": cores[i % len(cores)]
        })

    # --- Montagem da Resposta JSON Final ---
    dados_finais = {
        "top_sellers": {
            "labels": top_vendedores_labels,
            "values": top_vendedores_valores
        },
        "quarterly_sales": {
            "labels": trimestres_labels,
            "datasets": datasets_trimestrais
        }
    }
    return jsonify(dados_finais)

# --- Bloco de Execução Principal ---
def init_db_command():
    """Comando para inicializar o banco de dados."""
    init_db()
    print('Banco de dados inicializado.')


@app.route('/dados_metricas_clientes')
@login_required
def dados_metricas_clientes():
    """
    API que fornece todos os dados para o dashboard de métricas de clientes.
    """
    usuario_id = session['usuario_id']
    hoje = datetime.now()
    data_inicio_30d = (hoje - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    data_inicio_3m = (hoje - timedelta(days=90)).strftime('%Y-%m-%d')
    data_inicio_12m = (hoje - timedelta(days=365)).strftime('%Y-%m-%d')

    # --- KPIs ---
    # Total de Clientes
    total_clientes = query_db("SELECT COUNT(id) as total FROM clientes WHERE usuario_id = ?",
                              [usuario_id], one=True)['total'] or 0

    # Novos Clientes (últimos 30 dias)
    novos_clientes_30d = query_db("SELECT COUNT(id) as total FROM clientes WHERE usuario_id = ? AND data_cadastro >= ?",
                                  [usuario_id, data_inicio_30d], one=True)['total'] or 0

    # Cliente com Maior Gasto (últimos 3 meses)
    query_maior_gasto_3m = """
                           SELECT c.nome, SUM(v.valor_total_venda) as total_gasto
                           FROM vendas v \
                                    JOIN clientes c ON v.cliente_id = c.id
                           WHERE v.usuario_id = ? \
                             AND v.data_venda >= ?
                           GROUP BY c.nome \
                           ORDER BY total_gasto DESC LIMIT 1; \
                           """
    maior_gastador_3m = query_db(query_maior_gasto_3m, (usuario_id, data_inicio_3m), one=True)

    kpi_maior_gastador_nome = "N/A"
    kpi_maior_gastador_valor = "R$ 0,00"
    if maior_gastador_3m and maior_gastador_3m['total_gasto'] > 0:
        kpi_maior_gastador_nome = maior_gastador_3m['nome']
        kpi_maior_gastador_valor = f"R$ {maior_gastador_3m['total_gasto']:,.2f}".replace(",", "X").replace(".",
                                                                                                           ",").replace(
            "X", ".")

    # --- Top 5 Clientes por Valor Gasto (Gráfico de Barras - últimos 12 meses) ---
    query_top_clientes = """
                         SELECT c.nome, SUM(v.valor_total_venda) as total_gasto
                         FROM vendas v \
                                  JOIN clientes c ON v.cliente_id = c.id
                         WHERE v.usuario_id = ? \
                           AND v.data_venda >= ?
                         GROUP BY c.nome \
                         ORDER BY total_gasto DESC LIMIT 5; \
                         """
    resultados_top_clientes = query_db(query_top_clientes, (usuario_id, data_inicio_12m))

    labels_top_clientes = [row['nome'] for row in resultados_top_clientes] if resultados_top_clientes else []
    valores_top_clientes = [row['total_gasto'] for row in resultados_top_clientes] if resultados_top_clientes else []

    # --- Montagem da Resposta JSON Final ---
    dados_finais = {
        "kpis": {
            "total_clientes": total_clientes,
            "novos_clientes_30d": novos_clientes_30d,
            "maior_gastador_nome": kpi_maior_gastador_nome,
            "maior_gastador_valor": kpi_maior_gastador_valor
        },
        "top_clients_spending": {
            "labels": labels_top_clientes,
            "values": valores_top_clientes
        }
    }
    return jsonify(dados_finais)

# ===================== ROTAS PARA EXPORTAÇÃO NF-e ATUALIZADAS =====================
@app.route('/exportar_vendas_nfe', methods=['GET'])
@login_required
def exportar_vendas_nfe():
    """ Exibe a página para selecionar as vendas a serem exportadas. """
    usuario_id = session['usuario_id']
    data_inicio_filtro = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    query_vendas_recentes = """
                            SELECT v.id as venda_id, v.data_venda, c.nome as nome_cliente, v.valor_total_venda
                            FROM vendas v
                                     JOIN clientes c ON v.cliente_id = c.id
                            WHERE v.usuario_id = ? \
                              AND v.data_venda >= ?
                            ORDER BY v.data_venda DESC, v.id DESC; \
                            """
    vendas = query_db(query_vendas_recentes, (usuario_id, data_inicio_filtro))

    return render_template('exportar_vendas.html', vendas=vendas)


@app.route('/gerar_arquivo_nfe', methods=['POST'])
@login_required
def gerar_arquivo_nfe():
    """ Gera o arquivo (CSV ou XML) com os dados das vendas selecionadas E os dados da empresa. """
    usuario_id = session['usuario_id']
    venda_ids_selecionadas = request.form.getlist('venda_ids')
    formato_exportacao = request.form.get('formato_exportacao', 'csv')  # Pega o formato escolhido, default CSV

    if not venda_ids_selecionadas:
        print('Nenhuma venda selecionada para exportação.', 'warning')
        return redirect(url_for('exportar_vendas_nfe'))

    # --- Busca os Dados da Empresa ---
    empresa = query_db("SELECT * FROM empresas WHERE usuario_id = ?", [usuario_id], one=True)
    if not empresa:
        print('Dados da empresa não encontrados. Cadastre-os antes de exportar.', 'danger')
        return redirect(url_for('dados_empresa'))

    # --- Busca os Dados das Vendas ---
    placeholders = ','.join('?' * len(venda_ids_selecionadas))
    query_dados_export = f"""
        SELECT 
            v.id as VendaID, v.data_venda as DataEmissao,
            c.nome as DestNome, 'ISENTO' as DestIE, c.telefone as DestFone, 
            r.codigo_produto as ProdCodigo,
            r.tipo_roupa || ' ' || r.cor || ' ' || COALESCE(r.tamanhos, '') as ProdDescricao, 
            '00000000' as ProdNCM, 'UN' as ProdUnidade, 
            v.quantidade_vendida as ProdQuantidade, r.preco_unitario as ProdValorUnitario,
            v.valor_total_venda as ProdValorTotal
        FROM vendas v
        JOIN clientes c ON v.cliente_id = c.id
        JOIN roupas r ON v.roupa_id = r.id
        WHERE v.usuario_id = ? AND v.id IN ({placeholders})
        ORDER BY v.id; 
    """
    args = [usuario_id] + venda_ids_selecionadas
    dados_vendas = query_db(query_dados_export, args)

    if not dados_vendas:
        print('Não foi possível encontrar os dados para as vendas selecionadas.', 'error')
        return redirect(url_for('exportar_vendas_nfe'))

    # --- Geração do Arquivo baseado no Formato ---
    output = io.StringIO()
    mimetype = "text/plain"  # Default, será ajustado
    filename = f"vendas_para_nfe.{formato_exportacao}"

    # Define o cabeçalho base (pode precisar de ajuste por formato)
    cabecalho_base = [
        'EmitCNPJ', 'EmitRazaoSocial', 'EmitNomeFantasia', 'EmitIE', 'EmitIM',
        'EmitRegimeTributario', 'EmitCEP', 'EmitRua', 'EmitBairro', 'EmitCidade', 'EmitEstado', 'EmitPais',
        'VendaID', 'DataEmissao', 'DestNome', 'DestIE', 'DestFone',
        'ProdCodigo', 'ProdDescricao', 'ProdNCM', 'ProdUnidade',
        'ProdQuantidade', 'ProdValorUnitario', 'ProdValorTotal'
    ]

    # Prepara os dados da empresa
    dados_empresa_linha = [
        empresa['cnpj'], empresa['razao_social'], empresa['nome_fantasia'],
        empresa['inscricao_estadual'], empresa['inscricao_municipal'], empresa['regime_tributario'],
        empresa['cep'], empresa['rua'], empresa['bairro'], empresa['cidade'], empresa['estado'], empresa['pais']
    ]

    # --- Lógica para CSV ---
    if formato_exportacao == 'csv':
        mimetype = "text/csv"
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(cabecalho_base)
        for venda in dados_vendas:
            linha_completa = dados_empresa_linha + list(venda)
            writer.writerow(linha_completa)

    # --- Lógica para XML (Simplificado) ---
    elif formato_exportacao == 'xml':
        mimetype = "application/xml"
        root = ET.Element("ExportacaoNFe")

        emitente_el = ET.SubElement(root, "Emitente")
        for i, chave in enumerate(cabecalho_base[:12]):
            valor = dados_empresa_linha[i] if dados_empresa_linha[i] is not None else ""
            ET.SubElement(emitente_el, chave).text = str(valor)

        vendas_el = ET.SubElement(root, "Vendas")
        for venda_dict in dados_vendas:
            item_el = ET.SubElement(vendas_el, "ItemVenda")
            # Converter a linha do banco (sqlite3.Row) para dicionário para acesso por índice numérico
            venda_list = list(venda_dict)
            for i, chave in enumerate(cabecalho_base[12:]):
                valor = venda_list[i] if venda_list[i] is not None else ""
                ET.SubElement(item_el, chave).text = str(valor)

        xml_str = ET.tostring(root, encoding='unicode')
        dom = minidom.parseString(xml_str)
        output.write(dom.toprettyxml(indent="  "))

    # --- Lógica para TXT (REMOVIDA) ---
    # O bloco 'elif formato_exportacao == 'txt':' foi removido.

    else:
        # Caso um formato inválido seja passado (pouco provável com radio buttons)
        print('Formato de exportação inválido selecionado.', 'danger')
        return redirect(url_for('exportar_vendas_nfe'))

    # --- Prepara a Resposta para Download ---
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )



if __name__ == '__main__':
    print("Bloco __name__ == '__main__' sendo executado.")

    # ===================== LÓGICA DE AUTOMAÇÃO DO BANCO DE DADOS =====================
    # Verifica se o arquivo do banco de dados NÃO existe no caminho esperado.
    if not os.path.exists(DATABASE):
        with app.app_context():
            # 'app.app_context()' cria e ativa um "contexto da aplicação" do Flask.
            # O contexto da aplicação torna a aplicação Flask atual ('app') acessível
            # através de proxies contextuais (como current_app).
            print("Contexto da aplicação Flask ativo.")
            print("Arquivo de banco de dados não encontrado. Inicializando...")
            # Se não existir, chama a função init_db() para criar o banco e as tabelas.
            init_db()
    # ===============================================================================

    # Inicia o servidor de desenvolvimento do Flask.
    # debug=True ativa o modo de depuração. NUNCA use em produção.
    app.run(debug=True, host='127.0.0.1', port=5000)

