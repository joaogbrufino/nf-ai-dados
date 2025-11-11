document.addEventListener('DOMContentLoaded', () => {
  const btnBuscar = document.getElementById('rag-buscar');
  const perguntaEl = document.getElementById('rag-pergunta');
  const btnClear = document.getElementById('rag-clear');
  const btnCopy = document.getElementById('rag-copy');
  const latencyEl = document.getElementById('rag-latency');
  const suggestionsEl = document.getElementById('rag-suggestions');
  const errorEl = document.getElementById('rag-error');
  const resultWrap = document.getElementById('rag-result');
  const answerEl = document.getElementById('rag-answer');
  const contextEl = document.getElementById('rag-context');

  const suggestionButtons = [];
  let suggestionSearchInProgress = false;

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.style.display = 'block';
  }

  function clearError() {
    errorEl.textContent = '';
    errorEl.style.display = 'none';
  }

  function setLoading(loading) {
    if (loading) {
      btnBuscar.disabled = true;
      btnBuscar.textContent = 'Buscando...';
    } else {
      btnBuscar.disabled = false;
      btnBuscar.textContent = 'Buscar';
    }
  }

  function setSuggestionsDisabled(disabled) {
    suggestionButtons.forEach(b => {
      b.disabled = disabled;
      b.style.opacity = disabled ? 0.6 : 1;
      b.style.cursor = disabled ? 'not-allowed' : 'pointer';
    });
  }


  function initSuggestions() {
    const samples = [
      'Quais despesas maiores do mês atual?',
      'Parcelas vencendo nesta semana',
      'Movimentos da classificação MANUTENÇÃO E OPERAÇÃO',
      'Resumo dos fornecedores com maior valor total',
      'Notas fiscais emitidas no último trimestre'
    ];
    samples.forEach(text => {
      const chip = document.createElement('button');
      chip.textContent = text;
      chip.style.padding = '6px 10px';
      chip.style.border = '1px solid #ddd';
      chip.style.borderRadius = '20px';
      chip.style.background = '#f5f5f5';
      chip.addEventListener('click', () => {
        if (suggestionSearchInProgress) return; // bloquear nova seleção até concluir
        suggestionSearchInProgress = true;
        setSuggestionsDisabled(true);
        perguntaEl.value = text;
        executeSearch('suggestion');
      });
      suggestionButtons.push(chip);
      suggestionsEl.appendChild(chip);
    });
  }

  function executeSearch(source = 'manual') {
    const pergunta = (perguntaEl.value || '').trim();
    clearError();
    resultWrap.style.display = 'none';
    answerEl.textContent = '';
    contextEl.textContent = '';
    latencyEl.textContent = '';

    if (!pergunta) {
      showError('Digite uma pergunta.');
      return;
    }

    const started = performance.now();
    setLoading(true);
    fetch('/rag/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pergunta })
    })
      .then(r => r.json())
      .then(data => {
        setLoading(false);
        if (source === 'suggestion') {
          suggestionSearchInProgress = false;
          setSuggestionsDisabled(false);
        }
        if (!data.sucesso) {
          showError(data.erro || 'Falha na busca RAG.');
          return;
        }
        resultWrap.style.display = 'block';
        answerEl.textContent = data.resposta || '(sem resposta)';
        contextEl.textContent = (data.contexto && data.contexto.join('\n\n')) || '(sem contexto)';
        const elapsed = Math.round(performance.now() - started);
        latencyEl.textContent = `Tempo de resposta: ${elapsed} ms`;
      })
      .catch(err => {
        console.error('Erro RAG:', err);
        setLoading(false);
        if (source === 'suggestion') {
          suggestionSearchInProgress = false;
          setSuggestionsDisabled(false);
        }
        showError('Erro ao executar a busca.');
      });
  }

  btnBuscar.addEventListener('click', executeSearch);

  btnClear.addEventListener('click', () => {
    perguntaEl.value = '';
    clearError();
    resultWrap.style.display = 'none';
    answerEl.textContent = '';
    contextEl.textContent = '';
    latencyEl.textContent = '';
  });

  btnCopy.addEventListener('click', () => {
    const text = answerEl.textContent || '';
    if (!text) return;
    navigator.clipboard.writeText(text).catch(() => {});
  });

  perguntaEl.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      executeSearch();
    }
  });


  perguntaEl.focus();
  initSuggestions();
  // Histórico recente removido conforme solicitado
});