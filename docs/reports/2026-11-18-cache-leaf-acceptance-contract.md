# Helper leaf de cache — critérios de aceitação/rejeição, perfil host v1

**Contrato definido; helper não implementado nem aprovado.** Este documento
estabelece critérios verificáveis para um futuro artefato. Não implementa
verificador, wrapper, assembly, cache maintenance ou integração com o loader.
Permanecem 67 grupos host, sem novo grupo nesta etapa, e estimativa global
subjetiva de ~40%. Nenhum build kernel/Android ou operação no Quest.

Continuação da [revisão de lifetime/ABI](2026-11-18-lifetime-helper-abi-evidence-review.md).
Perfil: `q3-cache-leaf-acceptance-contract-host-v1`. Mudanças na interface,
registradores, contexto ou política de retorno exigem nova revisão/versionamento;
não aceitar extensões implícitas durante implementação.

## 1. Fronteira do perfil

O objeto proposto é uma função **local, leaf, de chamada direta e com retorno**,
para manutenção de D-cache de um intervalo de VA kernel válido com MMU ativa.
Não é trampoline físico, entrada de kernel, callback, leitor/writer de payload,
alocador ou rotina de recuperação. Não deve ser copiado para execução em outro
endereço por este contrato.

Forma de ABI proposta: retorno `void`, primeiro argumento `void *` contendo VA,
segundo argumento `size_t` contendo comprimento **em bytes**, ARM64 LP64. Não
aceitar PA, dma_addr_t, count de páginas ou end exclusivo no lugar desses
argumentos. Esse formato é somente especificação: nenhum símbolo/protótipo novo
foi acrescentado aos fontes executáveis.

O caller futuro seria responsável por preflight e recusa de entradas inválidas
**antes de qualquer operação de cache**. Retorno void não é recibo de ownership,
readback ou quiescência. Falha de mapping/abort de hardware não oferece por si
um retorno normal de erro ou cleanup seguro.

O helper não cria mappings, não congela conteúdo, não estabelece exclusão DMA e
não modifica MMU, IRQs, preempção, CPUs ou watchdog. O contexto exato de CPU,
atributos e ordenação precisa estar demonstrado para o local de chamada. Não
aprovar genericamente uso pré e pós-shutdown por ser a mesma função.

## 2. Resultados separados e fail-closed

Um futuro relatório deve apresentar resultados independentes:

1. **Contrato de input/ranges:** aritmética e recusa antes de efeitos.
2. **Artefato/ABI/call graph:** ELF, calls, registradores, CFI/SCS/BTI/PAC e build.
3. **Semântica de cache/plataforma:** PoC, linhas/errata, atributos e contexto.
4. **Lifetime/isolamento operacionais:** recursos reais e estabilidade contínua.

`PASS` num item não implica PASS nos demais. Evidência ausente/inconclusiva é
`PENDING`, nunca sucesso por default; contradição é `REJECT`. Nenhum resultado
host pode habilitar `boot_ready`, autorização, aquisição, execução, release ou
retomada automática. **Nesta etapa todos os quatro itens estão sem aprovação
de um novo artefato**, porque ele ainda não existe.

## 3. Matriz de critérios

| ID | Aceitar somente se demonstrado | Evidência/método exigido | Rejeitar ou deixar pendente quando |
|---|---|---|---|
| L01 — procedência | Fonte, config, toolchain e ELF final identificados por hash e relação de build preservada | Config normalizada, comandos efetivos, logs, inputs e ELF | Só há fonte/disassembly solto, arquivo divergente ou flags presumidos |
| L02 — ABI | LP64, VA + comprimento em bytes, retorno void, declaração C única coerente com corpo | Headers/protótipos e caller final; larguras efetivas do build | Casts/adaptações escondem diferença de tipo, signedness ou unidade |
| L03 — ligação direta | Caller conhecido chega ao símbolo/corpo local pretendido por call direto | Instrução `bl`, destino e relocações quando presentes; resolver endereço no ELF se já ligado | `blr`/callback, tail jump ou veneer não revisado; símbolo privado ou endereço copiado usado como alvo |
| L04 — sem escape | Endereço da função não é publicado em tabela/callback/dado executável fora do contrato | Relocações de código e dados e referências a símbolos; distinguir debug/metadata não executável | Referência executável inexplicada ou análise incompleta; não contar apenas CALL26 e ignorar dados |
| L05 — CFI intacto | Callers C e módulo conservam CFI estrito/cross-DSO e Full LTO | Comandos efetivos, símbolos/relocações/disassembly e política Kbuild | `__nocfi`, casts privados, CFI permissivo, lookup de endereço ou filtros de flags introduzidos para passar |
| L06 — entrada BTI | Entrada da função é BTI c explícito, conforme perfil/config | Decodificar `bti c` ou `hint #34` no início efetivo do símbolo FUNC | BTI ausente, entrada/alias fora do ponto verificado ou troca por código especial sem contrato C |
| L07 — preservação | Leaf só usa x0–x3/NZCV como trabalho; não toca x18, x19–x29, FP/SIMD ou escreve SP; LR só pela sequência PAC revisada | Inspeção de todos os caminhos, efeitos explícitos/implícitos das instruções e modelo de registradores | Calls aninhados, frame, clobber de callee-saved/SCS, stack desalinhada ou retorno fora do perfil |
| L08 — retorno PAC | Proteção de retorno coerente com config PAC+BTI, incluindo caminhos de zero length | Análise de fluxo com assinatura/autenticação/retorno compatíveis, modificador e SP estáveis | Qualquer retorno alcançável sem a proteção exigida, par incompatível ou exceção tácita por ser leaf |
| L09 — ELF bounded | Símbolo FUNC único, tamanho não nulo, entrada/término dentro de seção executável e limites do arquivo | Parser ELF validando offsets, seções, símbolos/relocações, aliases e bounds | ELF truncado, arquitetura errada, ranges ambíguos ou instrução não interpretada como segura |
| L10 — imports/proteções | Sem imports privados; imports adicionais só se revisados/exportados com CRC/namespace; proteções existentes preservadas | Module.symvers fornecido, __versions/imports efetivos e comandos Kbuild | Copiar macro de kernel introduz dependência não exportada, módulo perde proteção ou importa provider inesperado |
| L11 — linhas/errata | Passo/cobertura são seguros para as CPUs permitidas; alternativas/errata necessários são demonstrados | Fonte, código final, contexto de CPU/migração e capabilities aplicáveis | CTR raw é tomado como seguro entre CPUs, tamanho é fixture não comprovada, ou macro/patch é presumido |
| L12 — PoC | Efeito escolhido publica D-cache até PoC e termina com ordenação adequada ao contexto | Revisão arquitetural da operação/barreiras e cobertura de ranges finais | Só I-cache/PoU, flag de página, fence genérica ou readback pelo mesmo mapping |
| L13 — sem efeitos ocultos | Sem I/O, sleep, IPI, alocação, mudança de mapping/CPU/IRQ ou instruções fora do perfil | Corpo final inteiro e dependências; desconhecido não é no-op | Instruções/calls adicionais ou dependências não analisadas |
| L14 — ponto de chamada | Mappings/handles e código vivos, última escrita anterior, sem writers/DMA posteriores até uso | Contrato operacional específico, cobertura por recurso e evidência atual necessária | Apenas IDs/recibos/snapshots/claims, helper usado depois de perder a garantia ou fora do contexto revisado |

L07 permite a alteração controlada de LR exigida por L08; não autoriza outros
usos de LR ou frame. O perfil estreito é intencional. Precisar de outros
registradores ou argumentos não autoriza ampliá-lo silenciosamente.

Calls diretos podem já estar resolvidos num ELF: ausência de uma relocação
CALL26 isoladamente não é prova de erro, mas o destino efetivo ainda precisa ser
demonstrado. Veneers/tail calls não revisados não passam por equivalência presumida.

CFI do módulo não equivale a membership de um alvo indireto ASM. Uma função ASM
local não recebe automaticamente a instrumentação C de SCS/CFI/PAC. O Kbuild
também tem tratamento específico de metadados `.mod.c`; não confundir isso com
autorização de desproteger callers ou de exigir flags C idênticos na unidade ASM.

## 4. PAC/BTI: decisão explícita para o novo perfil

A config preparada habilita `CONFIG_ARM64_PTR_AUTH`, `CONFIG_ARM64_BTI_KERNEL`
e suporte do compilador a `pac-ret+leaf+bti`. Para este **novo perfil**, não
admitir retorno sem PAC por exceção implícita de função leaf manuscrita.
Todos os caminhos de retorno deverão satisfazer L08, sem assinatura seguida
de retorno não autenticado, autenticação sem assinatura ou modificador diferente.
Não executar instruções privilegiadas/PAC no host como "teste" desse contrato.

O helper **histórico** inspecionado anteriormente tem BTI, mas não mostra
assinatura/autenticação PAC em seu corpo. Logo, não usá-lo como controle positivo
completo deste novo perfil; ele não satisfaz L08 tal como definido aqui. Isso
não modifica retroativamente seu fonte/ELF nem afirma falha observada no aparelho.
Ele continua apenas evidência parcial de chamada direta e preservação de x18.

BTI, PAC, CFI e SCS respondem a obrigações diferentes. Nem mesmo passar nos
quatro comprova que uma operação `dc` publica os ranges certos até PoC.

## 5. Contrato de ranges antes de chamar o leaf

O futuro preflight precisa conhecer a **extensão própria completa** e estável,
a subfaixa efetivamente escrita, VA/PA/atributos correspondentes e tamanho de
linha seguro. Não derivar ownership de endereço traduzível, PFN válido, iomem
livre, fingerprint ou nome de provider.

Regras aritméticas propostas:

- Tipos/larguras válidos, sem negativos/bools no modelo e sem narrowing no caller.
- `len == 0`: no-op sem invocar manutenção; não contar isso como publicação de
  bytes, barreira de conclusão ou evidência de posse de um ponteiro vazio.
  O leaf também precisa de caminho zero seguro caso chamado; L08 ainda se aplica.
- Para range não vazio, detectar overflow de `addr + len`, de fim da extensão
  própria e do arredondamento final antes de calcular/usar intervalos.
- Arredondar início para baixo e fim para cima com linha segura; toda a faixa
  arredondada deve permanecer na extensão própria, não apenas os bytes pedidos.
- Não cruzar slots/objetos pela adjacência numérica. Não limpar prefixo/padding
  fora da propriedade declarada. Tails dentro do mesmo slot são cobertos por
  linhas completas, sem autorizar writes adicionais.
- Publicar payload, código e tabelas finais separadamente; revisar publicação de
  I-cache como obrigação adicional. Clean prévio não cobre escrita posterior.

O ledger host atual usa linhas assumidas 16/32/64/128/256 bytes. Isso não comprova
CTR/capabilities reais. Reutilizar o macro de linha segura do kernel pode adicionar
referências externas/alternatives: L10/L11 exigem inspecioná-las. Se a interface
proposta não permitir uma solução correta sem dependências privadas, deixá-la
pendente ou revisar o perfil; não usar raw CTR ou constante sem prova para passar.

### Vetores mínimos para um futuro verificador aritmético

Valores a seguir são offsets de uma extensão **sintética** de 4.096 bytes, com
linha assumida de 64 bytes; não são VA/PA do Quest e não executam cache ops.

| Pedido / condição | Resultado esperado |
|---|---|
| Offset 0, len 0 | NOOP, zero linhas e nenhuma comprovação de publicação |
| Offset 1, len 63 | Cobertura `[0,64)` se a extensão inteira for própria |
| Offset 63, len 2 | Cobertura `[0,128)` |
| Offset 4080, len 16 | Cobertura `[4032,4096)` |
| Offset 4080, len 17 | REJECT: extrapola a extensão |
| Offset antes da extensão ou faixa cruzando dois slots | REJECT, sem primeira operação |
| Extensão própria começa em byte 1 e range toca a primeira linha | REJECT se o arredondamento incluir byte 0 alheio |
| Soma/end arredondado excede UINT64_MAX | REJECT antes de wrap |
| Linha 0/não potência de dois/fora do perfil comprovado | REJECT ou PENDING por perfil não suportado, nunca assumir 64 |
| Clean antigo seguido de write | Cobertura atual incompleta até republicação; não reabrir seal |

Esses vetores são **especificações de testes futuros**, não novos testes já
executados. Modelos de intervalos existentes são evidência matemática limitada,
não substitutos da verificação de um futuro wrapper/leaf real.

## 6. Controles negativos obrigatórios para o futuro verificador de artefato

Antes de chamar uma inspeção de "verificador", demonstrar que recusa ou mantém
pendente pelo menos:

- ELF errado/truncado; símbolo sem bounds, seção não executável, alias/entrada
  ambíguos; disassembler incompatível ou instrução desconhecida.
- `blr`, callback ou endereço da função escapando para dados executáveis;
  resolução privada, `__nocfi`/CFI permissivo e falso sucesso baseado só em
  `__cfi_check` global. Debug/unwind metadata precisa ser classificado, não tomado
  automaticamente como callback.
- Remoção de BTI, clobber de x18/callee-saved/SP, chamada aninhada ou uso de FP/SIMD.
- Remoção/incompatibilidade de PAC, early return sem proteção, paths alternativos
  que contornem autenticação e mudança do modificador/SP.
- Operação só PoU/I-cache, ausência da ordenação requerida, range incompleto,
  dependência privada introduzida por macro e corpo diferente do build declarado.
- Limite de parsing/iterações excedido ou campos de evidência faltantes. Nenhum
  caso desconhecido pode cair em aprovação por default.

Fixtures sintéticas não precisam ser executáveis; o verificador futuro deve ser
read-only, sem instalar/carregar módulos ou executar bytes inspecionados.
Reconhecer o ABI de um leaf não o promove a handler de entrada de kernel.

## Estado e próximo gate

O contrato e os controles de rejeição estão definidos. **Nenhum novo artefato
satisfaz o contrato nesta etapa**; helper, publicação física, lifetime e handoff
continuam não demonstrados. O resultado não muda a estimativa subjetiva de
~40%, a solicitação Image CMA de 32 MiB ou os bloqueios de CPU/DMA/SMMU/QMP/
watchdog/logs/âncora e autorização específica para o aparelho.

Próximo gate offline: implementar apenas um **verificador read-only** dos
critérios estáticos que forem mecanizáveis, com fixtures negativas e resultados
PASS/PENDING/REJECT separados por obrigação. Não implementar helper, wrapper
operacional, adaptador, writer ou loader por consequência desse passo. Sem
evidência real, lifetime e correção de cache/plataforma permanecem PENDING.

Evidências em `private-diagnostics/cache-leaf-acceptance-contract-01/`: contrato,
matriz de obrigações, config relevante, vetores especificados, suíte e hashes.
