# Importa a funcao que executa uma consulta e retorna um unico registro.
from db import execute_one

# Consulta dados do servidor para confirmar que a conexao com MySQL funciona.
print("Conectado ao banco de dados.")
info = execute_one(
    "SELECT DATABASE() AS banco, VERSION() AS versao, NOW() AS agora"
)
# Exibe o nome do banco, versao do MySQL e horario retornado pelo servidor.
print("Banco:", info["banco"])
print("Servidor:", info["versao"])
print("Hora do banco:", info["agora"])

# Conta registros ativos em cada tabela principal (registros removidos ficam excluidos da contagem).
municipes = execute_one(
    "SELECT COUNT(*) AS total FROM municipes WHERE deletado_em IS NULL"
)
processos = execute_one(
    "SELECT COUNT(*) AS total FROM processos WHERE deletado_em IS NULL"
)
inscricoes = execute_one(
    "SELECT COUNT(*) AS total FROM inscricoes_municipais WHERE deletado_em IS NULL"
)

# Mostra o resultado das contagens para verificar se as tabelas estao acessiveis.
print("Tabela municipes:", municipes["total"], "linhas")
print("Tabela processos:", processos["total"], "linhas")
print("Tabela inscricoes_municipais:", inscricoes["total"], "linhas")


## esse daqui eu sei que executa pra testar como ta o banco, se ta conectando, atualizações e etc