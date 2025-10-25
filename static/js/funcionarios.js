// Função para buscar endereço pelo CEP usando a API ViaCEP
async function buscarEnderecoPorCep(cep) {
    if (cep.length !== 8) {
        return;
    }

    try {
        const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const data = await response.json();

        if (!data.erro) {
            document.getElementById('rua').value = data.logradouro;
            document.getElementById('cidade').value = data.localidade;
            document.getElementById('estado').value = data.uf;
            document.getElementById('pais').value = 'Brasil';
        }
    } catch (error) {
        console.error('Erro ao buscar CEP:', error);
    }
}

// Validação de datas do contrato
function validarDatas() {
    const dataInicio = document.getElementById('data_inicio_contrato').value;
    const dataFim = document.getElementById('data_fim_contrato').value;

    if (dataFim && dataInicio > dataFim) {
        alert('A data de início não pode ser posterior à data de fim do contrato!');
        return false;
    }
    return true;
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    console.log('funcionarios.js carregado!');
    // Listener para o campo CEP
    const cepInput = document.getElementById('cep');
    if (cepInput) {
        cepInput.addEventListener('blur', (e) => {
            const cep = e.target.value.replace(/\D/g, '');
            buscarEnderecoPorCep(cep);
        });
    }

    // Listener para o formulário
    const form = document.getElementById('form-funcionario');
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!validarDatas()) {
                e.preventDefault();
            }
        });
    }
});