# Verificador estático read-only do leaf — subconjunto host

**68 grupos host aprovados, zero falhas/ignorados.** Implementado
`quest3/layout-review/cache_leaf_static_review.py`, com testes negativos em
`test-cache-leaf-static-review.py`. Nenhum helper, wrapper operacional, writer,
adaptador, build kernel/Android ou operação no Quest foi criado/executado.

O verificador cobre um **subconjunto** do
[contrato L01–L14](2026-11-18-cache-leaf-acceptance-contract.md). Não aprova o
contrato inteiro: seu resultado global é sempre `PENDING` ou `REJECT`, nunca
`PASS`. Hashes e consistência estática não estabelecem autorização ou lifetime.

## Interface e limites

- API pura `inspect_bytes(data, symbol=...)`: recebe bytes imutáveis e retorna
  relatório por critério. Não executa, linka, carrega ou mapeia os bytes.
- CLI lê arquivo local e imprime JSON; não chama compilador/disassembler externo
  nem grava o arquivo inspecionado. Exit 1 indica REJECT; exit 2 indica PENDING
  **ou erro operacional de CLI**, que deve ser distinguido pelo JSON/stderr.
  Não há exit 0 de aprovação.
- API separada `review_range(...)`: aritmética uint64 de uma extensão declarada,
  sem VA/PTE real, ownership ou consulta de CPU.
- Limites: 32 MiB de ELF, 512 seções, 65.536 símbolos, 65.536 relocações,
  4.096 palavras no corpo e 32.768 estados abstratos de controle.

O parser aceita somente ELF64 little-endian AArch64 **ET_REL**, sem program
headers/numeração estendida, com uma symtab e relocações RELA. Outros formatos
não são silenciosamente aceitos. É perfil restrito, não parser universal de ELF.

## O que é mecanizado

### Estrutura ELF e referências

Valida bounds/tamanhos/alinhamentos de tabelas, strings terminadas, seções de
arquivo sem sobreposição, símbolos definidos dentro de suas seções, função
STT_FUNC não vazia/alinhada numa seção PROGBITS executável/allocated não writable,
aliases de função/globais e mapping de dados dentro do leaf.

Inspeciona relocações de código **e dados**, inclusive referência ao intervalo
do helper via símbolo de seção/outro símbolo definido mais addend. Referências
em dados allocated ou não classificados são rejeitadas por L04. Referências de
debug não allocated são classificadas, mas não transformam L04 em PASS.
CALL26 direto observado precisa de `bl`, addend zero e caller FUNC correspondente.
Jumps, referências executáveis não revisadas ou destino deslocado são recusados.

Mesmo observando calls diretos, **L03/L04 permanecem PENDING** quanto ao contrato
completo: não há prova geral de call graph, todos os callers ou ausência de
endereços calculados sem relocação. Relocações dentro do próprio corpo impedem
decodificá-lo como código final e mantêm a análise correspondente pendente.

### Decodificação estreita e controle de retorno

Decodifica BTI c, um subconjunto de ALU 64-bit, leitura de CTR, branches internos
simples, operações de cache selecionadas, DSB SY, PAC SP-based e retornos.
Não usa texto de disassembler como autoridade: lê palavras do ELF.

- L06 pode ter PASS para BTI c explícito na entrada.
- L07 pode ter PASS para preservação no corpo decodificado de x18,
  callee-saved/SP e uso de x0–x3/NZCV, com LR limitado a PAC/retorno.
- L08 percorre estados abstratos `(PC, estado PAC, cache pendente de barreira)`.
  Explora os dois caminhos de branches condicionais sem executar registradores
  ou instruções. Retornos alcançáveis exigem assinatura/autenticação SP-based
  correspondentes, incluindo RETAA/RETAB e caminhos de zero length.
- L09 pode ter PASS para a estrutura bounded suportada; opcode desconhecido ou
  relocação no corpo mantém a parte correspondente PENDING, não sucesso.
- L13 pode ter PASS para exclusão de efeitos fora do subconjunto fechado.

Calls aninhados, controle indireto, uso de registrador/SP fora do perfil ou
instrução de sistema fora do subconjunto são recusados. Branch/fallthrough que
escape do corpo é recusado. Opcode desconhecido não é tratado como NOP e não
gera PASS de preservação/PAC.

Assinatura repetida, autenticação sem assinatura/chave correspondente e qualquer
retorno alcançável desprotegido rejeitam L08. Exceder o limite de estados deixa
PENDING. Não se prova terminação de loops, valor real de SP/LR, chaves PAC ou
comportamento de CPU: PASS é somente para a propriedade estática explicitada.

PoU/invalidate-only fora do perfil e retorno após operação de cache sem DSB SY
subsequente são controles negativos L12. **Mesmo com DC PoC + DSB presentes,
L12 continua PENDING**: não há prova de cobertura de ranges, atributos, errata,
última escrita ou efeito físico no contexto de chamada.

## O que continua pendente por construção

| Critério | Limite atual |
|---|---|
| L01 | Hash do ELF não vincula fonte/config/toolchain/build |
| L02 | ELF/corpo não demonstram declaração C única ou unidades dos argumentos |
| L03/L04 | Referências observadas são parciais, não call graph/escape proof completos |
| L05 | Não inferir CFI estrito de um símbolo global ou de flags declarados |
| L10 | Detecta imports óbvios de resolver privado, mas não verifica toda ABI/CRCs/namespaces |
| L11 | CTR raw e linha assumida não comprovam segurança entre CPUs/errata |
| L12 | Sintaxe de cache/barreira não comprova PoC/cobertura/plataforma |
| L14 | Nenhum handle/mapping, exclusão DMA ou lifetime real foi estabelecido |

Nenhum dado fornecido pelo caller pode trocar esses PENDING por aprovação
operacional. `helper_approved`, runtime_admission, autorização, cache/lifetime
verificados, execução, cleanup, retomada e boot_ready ficam sempre falsos.

## Aritmética de ranges

`review_range` verifica tipos uint64, extensão não vazia, somas e arredondamento
sem wrap, e que toda a faixa de linhas esteja em **uma** extensão declarada.
Linhas assumidas suportadas: 16/32/64/128/256 bytes. Linha malformada é REJECT;
potência de dois fora desse perfil é PENDING, nunca fallback para 64.

Comprimento zero produz NOOP, sem chamada, linhas ou publicação alegada. Para
range não vazio, PASS significa apenas que a aritmética cabe na extensão
declarada. Não é preflight operacional nem aprovação de ponteiro. Páginas,
mapping, zero-fill, readback, última escrita e selagem continuam nos contratos/
modelos separados; esse preflight matemático não os substitui.

## Fixtures e controle histórico

As fixtures são arrays de palavras e ELF mínimo **não ligado e sem metadados de
módulo**. Não foi escrito/compilado um helper a partir delas. Um fixture positivo
apenas para BTI/registradores/PAC/ELF continua globalmente PENDING, inclusive
porque não demonstra ABI C, CFI dos callers ou cache/lifetime.

Testes cobrem aliases, escapes em dados e por símbolo de seção, referência
debug, call reloc alterado, BTI removido, x18/callee-saved/SP/LR clobbered, calls
aninhados/indiretos, sistema fora de perfil, PAC removido/mismatched/duplicado,
early return que pula autenticação, PoU-only, barreira faltante, opcode
desconhecido, reloc no corpo, bounds/tabelas/arquitetura/tipos inválidos e limite
do CFG. Acrescentam 200 mutações ELF seeded, 500 casos aritméticos seeded e CLI
com saída PENDING/exit 2 e input inalterado.

O ELF histórico `quest3/module/quest_kexec.ko` é controle negativo do **novo**
contrato: três calls diretos observados; L06/L07/L09/L13 com PASS no escopo
estático; **L08 REJECT por falta de PAC**. Os outros critérios permanecem PENDING.
Não é declaração de falha observada no aparelho nem alteração retroativa do ELF.

## Resultado e próximo gate

Verificador read-only parcial e um novo grupo host concluídos. Helper, wrapper
operacional e loader não foram implementados/modificados; nenhum byte inspecionado
foi executado. Progresso global continua estimativa subjetiva de ~40%.

Próximo gate: revisar os limites/controles do verificador e estabelecer vínculo
verificável de procedência e ABI dos callers/imports antes de propor novo
helper. Fatos reais de cache/lifetime continuam independentes e pendentes;
nenhuma execução no Quest é autorizada por resultados estáticos.

Evidência: `private-diagnostics/cache-leaf-static-review-host-01/`, com fontes,
fixtures não operacionais, relatórios por critério, testes/logs e hashes.
