-- DROP TABLE IF EXISTS usuarios;
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    sobrenome TEXT NOT NULL,
    data_nascimento TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL
);

-- DROP TABLE IF EXISTS roupas;
CREATE TABLE roupas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    codigo_produto TEXT NOT NULL,
    data_entrada TEXT NOT NULL,
    tipo_roupa TEXT NOT NULL,
    tecido TEXT,
    quantidade INTEGER NOT NULL,
    cor TEXT NOT NULL,
    tamanhos TEXT,
    detalhes TEXT,
    preco_unitario REAL,
    quantida_vendas INTEGER,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
CREATE UNIQUE INDEX idx_roupas_usuario_codigo ON roupas (usuario_id, codigo_produto);

CREATE TABLE IF NOT EXISTS funcionarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    nome_completo TEXT NOT NULL,
    cep TEXT NOT NULL,
    rua TEXT NOT NULL,
    numero TEXT NOT NULL,
    cidade TEXT NOT NULL,
    estado TEXT NOT NULL,
    pais TEXT NOT NULL,
    data_inicio_contrato DATE NOT NULL,
    data_fim_contrato DATE,
    cargo TEXT NOT NULL,
    definicao_cargo TEXT NOT NULL,
    observacoes TEXT,
    is_gerente INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    nome_fantasia TEXT,
    cnpj TEXT,
    razao_social TEXT,
    cnae TEXT,
    cep TEXT,
    rua TEXT,
    bairro TEXT,
    cidade TEXT,
    estado TEXT,
    pais TEXT,
    inscricao_estadual TEXT,
    inscricao_municipal TEXT,
    regime_tributario TEXT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- DROP TABLE IF EXISTS clientes;
CREATE TABLE clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL,
    data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- ======================= TABELA DE VENDAS ATUALIZADA =======================
CREATE TABLE vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    cliente_id INTEGER NOT NULL,
    roupa_id INTEGER NOT NULL,
    funcionario_id INTEGER,
    quantidade_vendida INTEGER NOT NULL,
    valor_total_venda REAL NOT NULL,
    data_venda DATE NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (roupa_id) REFERENCES roupas(id),
    FOREIGN KEY (funcionario_id) REFERENCES funcionarios(id)
);

