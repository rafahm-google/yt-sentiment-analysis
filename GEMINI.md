# Instruções para Uso da API Gemini

- Os modelos mais atuais e que devem ser usados SEMPRE são:
  - Modelo Principal: `gemini-3.6-flash`
  - Modelo de Fallback: `gemini-3.1-pro-preview`
- Em caso de erro 503 (sobrecarga) com o Modelo Principal, implemente uma estratégia de tentativa após uma breve espera. Se continuar falhando, utilize o Modelo de Fallback como alternativa.

