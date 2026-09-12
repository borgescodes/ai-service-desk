---
name: Jup Resolve
description: Sistema visual desktop de atendimento da Juparanã
colors:
  brand-green: "#45813c"
  brand-yellow: "#eeb41e"
  brand-gray: "#808285"
  white: "#ffffff"
  ink: "#20241f"
  ink-muted: "#626762"
  line: "#d8ddd6"
  surface-soft: "#f5f7f4"
  focus: "#1849a9"
  green-text: "#32652b"
typography:
  heading:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "34px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  body:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "16px"
    lineHeight: 1.55
rounded:
  control: "5px"
  field: "6px"
spacing:
  small: "12px"
  medium: "24px"
  large: "48px"
components:
  button-primary:
    backgroundColor: "{colors.brand-green}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "10px 20px"
---

# Sistema visual Jup Resolve

## Overview

Interface de trabalho clara e discreta. A direção aprovada prioriza leitura e resolução de problemas, com branco, linhas e uso concentrado de verde. O modo Operate corresponde às superfícies de soluções e conversa desta fase.

## Colors

Verde estrutura e sinaliza ação; amarelo destaca a entrada para o Jup. Cinza de marca permanece no contorno de campos. Texto secundário usa o tom ink-muted, de maior contraste. Estado também é identificado por texto e forma.

## Typography

Fontes locais do sistema, sem downloads. Títulos funcionais de 34 px, título inicial do chat de 30 px e texto de 16–17 px. Não usar títulos comerciais ou slogans.

## Layout

Conteúdo de 1220 px; header de 72 px. FAQ em até quatro listas editoriais; busca de 66 px de altura. Artigo de 800 px e conversa de 820 px. Escopo de verificação: desktop de 1280, 1440 e 1600 px.

## Elevation & Depth

Sem sombras na estrutura pública. Separadores e superfícies suaves distinguem mensagens e encaminhamento. A imagem original do Jup conserva seu próprio volume.

## Shapes

Campos com raio de 6 px, botões de 5 px. Evitar pills e containers aninhados. A faixa do Jup é retangular.

## Components

Busca com label acessível, debounce de 140 ms e região de resultados viva. Artigo com parágrafos e listas semânticas. Conversa sem painel lateral permanente; resumo técnico em disclosure nativo. Controles com foco visível. Motion de controles em 180 ms e estado do Jup em 400 ms, com redução de movimento. Usar somente os seis desenhos derivados do pacote fornecido.

## Do's and Don'ts

Preservar o conteúdo aprovado e a allowlist do link Microsoft. Não usar gradientes, glass, glow, parede de cards, ícones decorativos por tópico ou seletor público de identidade. Operação permanece em rotas dedicadas. Os arquivos core protegidos não participam do design.
