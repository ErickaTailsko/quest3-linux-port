# Staging direto — contrato de design e revisão de falhas

**Revisão offline, não implementação nem aprovação para execução.** Nenhum
handle real, mapping, writer, leitura física, alocação ou caminho sem cópia foi
criado. A suíte existente permanece com 64 grupos; não há teste novo do alvo.
Este documento detalha os gates deixados pela
[comparação](2026-11-18-staging-comparison-host.md), sem removê-los.

## 1. Contrato de recursos

Um futuro backend precisaria reter os objetos reais abaixo. Campos de log ou
registros Python podem descrevê-los, mas não substituem referências kernel.

| Recurso | Contrato necessário | O que não comprova o contrato |
|---|---|---|
| Contexto | Boot atual, tentativa única, payloads esperados e escopo de autorização explícitos | Token, recibo, hash ou autorização antiga |
| Image | Handle real da aquisição contígua no CMA default identificado, tamanho/alinhamento e rotina pareada de liberação | Rótulo de provider, iomem ou descritor sem colisão |
| Initrd/DT | Handles reais buddy de blocos completos; ordem/tamanho e API pareada de liberação | Apenas endereço e tamanho do payload |
| Mapping CPU | Cobertura de todos os bytes tocados; VA/PA, atributos, writable e lifetime revisados | Converter PA arbitrária com uma macro |
| Buffer | Handle próprio, capacidade limitada e lifetime até término comprovado dos acessos | Orçamento de 4 KiB no comparador |
| Arquivos | Referências abertas e conteúdo estável/autenticado no escopo do payload esperado; comprimentos exatos | Nome, inode aberto ou tamanho capturado isoladamente |
| Código/tabelas | Handles e mappings próprios, disjuntos dos destinos; cobertura da execução final demonstrada | Três páginas geométricas da fixture |
| Isolamento | Ausência de writers CPU/DMA concorrentes, aliases incompatíveis e acessos pendentes nos ranges | Posse do alocador sozinha ou snapshot sem atividade |

Cada handle deve estar vinculado a role/provider, base e **extensão completa**,
contexto e responsável pela retenção. Validade de PFNs, RAM atual e reservas
precisa ser verificada com a posse, não inferida de um mapa histórico. Evitar
reuso ABA: igualdade de endereço/ID depois de free/reallocate não preserva a
mesma aquisição. O pool default deve permanecer válido durante toda a operação;
nenhum pool dedicado ou provider alternativo é fallback implícito.

Image continua exigindo 32 MiB contíguos; initrd e DT, dois slots separados de
2 MiB na hipótese atual. Zero nominal sobrando no pool de 32 MiB não é prova
de capacidade disponível nem autorização para tentar a aquisição.

## 2. Fases propostas — somente obrigações de design

Não são estados de um controlador implementado. Cumprir uma fase documental
não gera permissão nem habilita uma chamada.

1. **Preparação sem escrita:** nova autorização específica; contexto, arquivos,
   geometria/chosen e recursos conhecidos. Adquirir/reter todos os handles e
   mappings necessários antes de permitir qualquer byte no destino. Não iniciar
   escrita esperando descobrir depois que faltam recursos de transição.
2. **Antes da primeira escrita:** provar mappings/atributos, ausência de alias
   entre recursos, exclusão de writers/DMA e possibilidade de I/O enquanto o
   kernel antigo está operacional. O contrato de erro e logs deve estar definido.
3. **Staging:** I/O bounded enquanto disponível, escrituras apenas em intervalos
   autorizados, progresso monotônico e zero-fill explícito. Não existe I/O tardio
   de arquivo depois de suspender storage/CPUs necessários ao leitor.
4. **Selagem de conteúdo:** todas as leituras/escritas concluídas; validação dos
   bytes e zeros, ausência de I/O pendente e impedimento de mutações posteriores.
   Os handles permanecem retidos. Falha aqui não permite avançar ao shutdown.
5. **Pré-shutdown:** gates globais de CPUs, DMA/SMMU, watchdog, QMP, entrada CFI,
   cache/MMU e logs revisados. Registrar o último checkpoint recuperável antes
   de perder o transporte/storage. Sua confirmação não comprova o salto futuro.
6. **Fase irreversível:** shutdown revisado, manutenção final de cache/barreiras
   e entrada por caminho sem cópia específico. Nada de fallback, cleanup normal,
   retomada ou leitura de arquivo nesta fase. A sequência exata continua aberta.

O ponto de irreversibilidade não é simplesmente o `br` final. Pode ocorrer ao
parar CPUs/dispositivos ou perder mecanismos necessários à recuperação. Deve
ser identificado no fluxo real antes de se propor uma política de abort.

## 3. Streaming, integridade e intervalos

- Fixar tamanho esperado, digest de referência e representação dos três payloads
  antes de escrever. O DT final deve ter chosen coerente com os destinos; nunca
  alterá-lo após a selagem sem repetir validação e manutenção de cache afetadas.
- Para cada leitura, solicitar no máximo capacidade do buffer e bytes restantes.
  Um retorno positivo curto representa progresso parcial, não conclusão. EOF
  antes do tamanho esperado ou erro torna o payload incompleto. Rejeitar retorno
  maior que o pedido, overflow, offset fora de ordem e destino fora do intervalo.
- Só copiar bytes cuja leitura terminou. Não reutilizar/liberar o buffer com
  acesso assíncrono pendente; esta hipótese não inclui double buffering oculto.
- Consumir exatamente os bytes esperados de uma fonte estável. Crescimento,
  truncamento ou mutação precisam ser prevenidos/detectados por um mecanismo
  revisado, não por `O_NOFOLLOW` ou `i_size` isoladamente.
- Image: arquivo em `payload_start`, zero até o fim do staging page-rounded de
  `image_size`; inclui BSS e tail. Initrd/DT: arquivo mais zero até o fim da última
  página de cópia. Prefixo `text_offset` e padding restante do slot continuam
  reservados, mas não são implicitamente payload nem alvo de escrita extra.
- Se uma política futura exigir zerar **todo** o slot, declarar novos intervalos,
  custo e cobertura de cache/readback. Não ampliar silenciosamente o escopo.
- Digest incremental da origem comprova apenas os bytes lidos sob suas premissas.
  Comparar os bytes finais dos destinos, incluindo zeros, é obrigação separada.
  CRC de log ou hashes de fixtures não estabelecem integridade física no alvo.

## 4. Selagem de bytes não equivale a visibilidade física

Readback pelo mesmo mapping pode atingir cache. Ele ajuda a detectar erro lógico
de cópia, mas não comprova que os bytes serão vistos após desligar caches/MMU.
Exigir separadamente: estabilidade do conteúdo, protocolo de clean até PoC dos
destinos após a última escrita e atributos/aliases/barreiras adequados ao caminho
de entrada. Não inventar um readback uncached como atalho: aliases de atributos
incompatíveis também precisam ser excluídos.

A cobertura da manutenção deve incluir as linhas dos ranges escritos e os
recursos de transição efetivamente lidos/executados. Arredondamento de linhas
não pode tocar memória alheia; revisar também bordas e propriedade dos slots.
Qualquer escrita após a manutenção invalida a premissa para o range afetado.
Revisar publicação do código e I-cache, estado MMU/registradores e ordenação
com o shutdown. Este documento não escolhe instruções/barreiras finais.

O fluxo atual não satisfaz esse contrato direto:

- `quest3/module/loader.c`, `qkx_read`/`qkx_stage`: faz leitura completa solicitada
  em páginas-fonte, calcula CRC e adiciona descritores; não é writer direto.
- `qkx_identity_map`: cria o mapa do código atual; não prova cobertura nem
  adequação de um novo caminho sem cópia. As três páginas continuam só hipótese.
- A fase final limpa `owned[]`, publica código e passa
  `virt_to_phys(first_desc)` e `QKX_DTB`; não consome três handles retornados.
- `quest3/module/transition.S`, `qkx_reloc_start`: invalida destinos com `dc ivac`
  antes de copiar páginas sem sobreposição. Não usar source==destination nem
  ponteiro C nulo no lugar de um contrato de entrada sem descritores.

CFI, SCS/x18, Full LTO, MODVERSIONS e demais proteções permanecem exigidos.
Não há aprovação do handoff arquitetural ou do código herdado do Quest Pro.

## 5. Matriz de falhas e retenção

| Caso | Conteúdo/certeza | Obrigação; nenhuma ação automática implementada |
|---|---|---|
| Falha conhecida de aquisição/mapping antes de escrever | Nenhum payload escrito por esta operação | Só considerar descarte pareado dos handles comprovadamente próprios, sem acessos pendentes, sob política/autorização revisadas |
| Leitura curta positiva | Apenas parte do pedido lida | Continuar contabilizando progresso limitado; não declarar payload completo |
| EOF precoce/erro conhecido antes do shutdown | Destinos possivelmente parciais | Não selar/não iniciar shutdown; descarte só após término comprovado de todos os acessos e revisão |
| Digest/readback/zero-fill divergente | Conteúdo inválido | Recusar selagem, sem retry de escrita ou fallback implícito |
| Writer concorrente, mudança de mapping ou perda de handle | Isolamento/lifetime inválidos | Bloquear avanço; não inferir segurança de liberação |
| Timeout, interrupção, recibo ausente ou journal falho | Conclusão desconhecida | Congelar comandos seguintes, inclusive reads/cleanup automáticos; timeout não mata trabalho remoto |
| Falha de release ou conclusão de release incerta | Ownership possivelmente retido | Preservar informação, bloquear unload/reuso/repetição automática |
| Falha após efeito irreversível | Kernel antigo sem retorno ordinário garantido | Sem rollback/fallback; recuperação e logs precisam de design próprio previamente revisado |
| Host reinicia e reapresenta snapshots/recibos | História pode estar incompleta/obsoleta | Sem retomar; objetos serializados não restabelecem lifetime, autorização ou âncora independente |

Logs recuperáveis não podem depender apenas de USB, sleeps ou filesystem que
serão desligados. O último checkpoint pré-shutdown e eventual evidência final
precisam de mecanismo revisado e distinção entre intenção, conclusão e observação.
O monitor operacional e a proteção externa contra rollback continuam bloqueados.

## 6. Resultado e próximo gate

Revisão documental concluída; **todos os gates runtime permanecem abertos**.
Nenhum novo teste foi adicionado e nenhum resultado host prova estes contratos
no Quest. A economia condicional de ~32,61 MiB da comparação não mudou.

Próximo passo seguro: formalizar somente no host os traços de fases/falhas e
invariantes acima, com fixtures que recusem escrita antecipada, selagem incompleta,
mutação após clean e qualquer comando após incerteza. Mesmo uma fixture aceita
deve manter `boot_ready`, ownership e autorização de execução falsos. Antes de
runtime, ainda faltam revisão de ABI/handles reais, plataforma/cache/entrada,
implementação específica e nova autorização para cada escopo no aparelho.

Evidência desta revisão: `private-diagnostics/direct-staging-contract-review-01/`.
Fontes ativos, candidatos e arquivos anteriores de evidência preservados.
