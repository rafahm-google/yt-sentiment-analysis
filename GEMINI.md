# Instruções para Uso da API Gemini

- Os modelos mais atuais e que devem ser usados SEMPRE são:
  - Modelo Pro: `gemini-3.1-pro-preview`
  - Modelo Flash: `gemini-3-flash-preview`
- Não utilize versões anteriores como fallback (como 2.5-pro) a menos que explicitamente orientado pelo usuário.
- Em caso de erro 503 (sobrecarga), implemente uma estratégia de tentativa após uma breve espera.
