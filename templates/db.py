"""Modulo de acesso ao banco MySQL: concentra conexoes e comandos SQL."""


import os
from dotenv import load_dotenv
from mysql.connector import Error, pooling

load_dotenv()

## copia o nome do banco, e avisa o erro
if os.getenv("DB_NAME") is None:
    raise RuntimeError(
        "Nao encontrei o arquivo .env. Copie .env.example para .env e preencha."
    )

## parâmetros
CONFIGURACAO = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME"),
    "charset": "utf8mb4",
    "sql_mode": (
        "STRICT_TRANS_TABLES,NO_ZERO_DATE,"
        "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION"
    ),
    "time_zone": "-03:00",
    "use_pure": True,
}

## evita re-trabalho quando for criar conexão, para não ficar duplicando a cada select
pool = pooling.MySQLConnectionPool(
    pool_name="cadastro_municipes_pool",
    pool_size=5,
    **CONFIGURACAO,
)


def execute_query(sql, params=None, fetch=False):
    """Executa SQL; fetch=True retorna registros, caso contrario confirma alteracoes."""
    # Quando nao ha parametros, usa uma tupla vazia para o cursor.
    if params is None:
        params = ()

    # Pega uma conexao disponivel no pool e cria cursor que retorna colunas por nome.
    conexao = pool.get_connection()
    cursor = conexao.cursor(dictionary=True)

    try:
        # Executa a instrucao SQL com parametros separados, evitando unir valores.
        cursor.execute(sql, params)

        # SELECT: busca os registros. UPDATE/DELETE: confirma a operacao.
        if fetch:
            resultado = cursor.fetchall()
        else:
            conexao.commit()
            resultado = cursor.rowcount

        return resultado
    except Error:
        # Se a consulta falhar, desfaz alteracoes pendentes e propaga o erro.
        conexao.rollback()
        raise
    finally:
        # Fecha cursor e devolve a conexao ao pool, mesmo em caso de erro.
        cursor.close()
        conexao.close()


def execute_one(sql, params=None):
    """Executa uma consulta e retorna somente a primeira linha, ou None."""
    # Reaproveita execute_query e seleciona o primeiro resultado, se existir.
    linhas = execute_query(sql, params, fetch=True)
    return linhas[0] if linhas else None


def execute_insert(sql, params=None):
    """Executa INSERT e retorna o identificador gerado automaticamente."""
    # Garante que o cursor receba parametros em formato de tupla.
    if params is None:
        params = ()

    # Obtem conexao e cursor para executar a insercao.
    conexao = pool.get_connection()
    cursor = conexao.cursor()

    try:
        # Insere o registro, confirma e recupera o ID criado pelo AUTO_INCREMENT.
        cursor.execute(sql, params)
        conexao.commit()
        return cursor.lastrowid
    except Error:
        # Cancela a insercao se houver falha.
        conexao.rollback()
        raise
    finally:
        # Libera recursos usados pela operacao.
        cursor.close()
        conexao.close()
