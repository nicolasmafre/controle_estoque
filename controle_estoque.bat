REM Ativa o ambiente
call conda activate controle_estoque
if errorlevel 1 (
    echo Falha ao ativar o ambiente Conda.
    pause
    exit /b 1
)
echo Ambiente Conda 'controle_estoque' ativado.

REM Atualiza as bibliotecas (se houver mudanças no environment.yml)
echo Verificando e atualizando dependencias...
REM call conda env update -f environment.yml --prune
call conda install -c conda-forge flask hypercorn -y
if errorlevel 1 (
    echo Aviso: Nao foi possivel atualizar as dependencias. Tentando continuar...
)
echo Bibliotecas atualizadas.

REM Executa servidor de produção Hypercorn
call hypercorn app:app --bind 0.0.0.0:8000 --workers 1