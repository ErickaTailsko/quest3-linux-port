# Relocação versus staging direto — comparação offline

**64 grupos host aprovados, zero falhas/ignorados.** Comparação condicional em
`quest3/layout-review/staging_comparison.py`, sem alocador, writer, streaming I/O,
adaptador ou execução no Quest. Nenhum destino foi adquirido. As duas hipóteses
exigem destinos realmente adquiridos e retidos; escrever tarde não autoriza
usar RAM alheia.

## Contabilidade com destinos iguais

Fixture: Image trim3/initrd reais, DT e RAM sintéticos do teste de relocação.
Os endereços fictícios começam em 64 GiB e não propõem uma base no Quest.
O orçamento mantém três páginas de transição (código/PGD/PUD) e scratch igual
nas duas rotas. Esse custo da transição direta é **uma hipótese não validada**.

| Recursos | Relocação | Direto com buffer de 4 KiB |
|---|---:|---:|
| Destinos idênticos | 37.748.736 B | 37.748.736 B |
| Fontes retidas | 34.066.432 B / 8.317 páginas | 0 |
| Descritores de cópia | 135.168 B / 33 páginas | 0 |
| Buffer de streaming assumido | não acrescentado ao baseline | 4.096 B |
| Transição assumida | 12.288 B | 12.288 B |
| Scratch desta fixture | 0 | 0 |
| Destinos + trabalho contabilizado | **71.962.624 B / 68,62890625 MiB** | **37.765.120 B / 36,015625 MiB** |

Diferença condicional: **34.197.504 B / 32,61328125 MiB** a menos no direto.
Fórmula da diferença: fontes + descritores − buffer; transição e scratch iguais
se cancelam. O teste confere a coluna de relocação contra `relocation_plan.py`.
Buffers de 64 KiB e 2 MiB, scratch igual e inputs pequenos também são testados:
com arquivos pequenos e buffer grande, a relocação pode contabilizar menos.
Não existe vencedor ou seleção de rota runtime codificado.

**Não é pico medido nem economia garantida de RSS.** O baseline de relocação
conta recursos retidos, sem adicionar um eventual buffer de leitura transitório.
Ambas as colunas excluem page cache, stacks, bookkeeping, páginas rejeitadas,
arredondamento/custos adicionais dos alocadores e demais recursos do kernel.
O buffer direto é um orçamento assumido, não prova de alocação exata.
Materializar arquivos inteiros em buffers extras ou reter staging paralelo
invalida essa hipótese de streaming limitado. Os testes Python carregam bytes
completos no host: não implementam o leitor streaming nem medem o alvo.

Os destinos continuam sendo 32 MiB Image + 2 MiB initrd + 2 MiB DT. Portanto,
**direto não reduz a solicitação CMA da Image**, que ocupa todos os 32 MiB
nominais considerados. Não resolve identidade do pool default, disponibilidade,
fragmentação, lifetime ou impacto da aquisição. Pools dedicados não são fallback.

## Ordem, falhas e cache

| Aspecto | Relocação | Direto hipotético |
|---|---|---|
| Antes da primeira escrita final | Adquire/retem destinos e trabalho; valida fontes e descritores | Exige posse real, mappings graváveis/atributos corretos e exclusão de writers/DMA **antes** de escrever |
| Staging enquanto I/O está disponível | Leitura/zero-fill nas fontes separadas | Leitura limitada pelo buffer, escrita e zero-fill nos próprios destinos |
| Leitura curta/erro antes do shutdown | Fontes parciais; destinos ainda não escritos pelo staging | Destinos próprios podem ficar parcialmente escritos; nunca tratar como payload completo |
| Antes do shutdown irreversível | Concluir I/O, validar fontes/descritores e reter handles | Concluir I/O, validar conteúdo final/readback e impedir mutação até o handoff |
| Fase final | Copiar todas as páginas por caminho físico revisado | Entrar por caminho sem cópia, ainda inexistente |
| Cache | Revisar fontes/descritores/transição e protocolo da cópia | Clean dos **destinos** até PoC após a última escrita, mais barreiras/I-cache/MMU revisados |
| Após shutdown irreversível | Sem rollback ordinário garantido | Sem rollback ordinário garantido |

O conjunto `required_direct_first_write_gates` inclui obrigações da rota inteira:
posse/mapping/isolamento precedem a primeira escrita; conclusão das leituras,
zero-fill e validação precedem o shutdown; manutenção final de cache precede
a entrada. A lista não afirma que a leitura já terminou antes de começar.
Leituras parciais exigem tratamento explícito de progresso/EOF/erro e digest
completo; um hash do arquivo de origem não comprova bytes no destino. Não há
implementação dessas regras no alvo.

Abortar antes de efeitos irreversíveis pode permitir descarte **somente** com
handles reais, ausência comprovada de acessos/I/O pendentes e política revisada.
Não há cleanup automático ou autorização de unload. Conclusão desconhecida,
interrupção ou falha de journal congela comandos subsequentes, inclusive reads/
cleanup automáticos; timeout não encerra trabalho remoto. Não tentar outra rota.

## Por que não reutilizar o loader como caminho direto

O loader fixo atual permanece inalterado. Ele limpa cache de `owned[]` e passa
`virt_to_phys(first_desc)` para `qkx_enter`. Um ponteiro C nulo não pode ser
presumido como endereço físico zero nesse caminho.

`transition.S` executa `dc ivac` nos destinos antes da cópia e pressupõe páginas
source/destination sem sobreposição. Descritores de autocópia não substituem
um trampoline sem cópia revisado; podem invalidar os próprios dados staged.
Limpar apenas buffers-fonte também não cobre destinos escritos diretamente.
Não foi modificado código C/assembly, CFI, SCS, Full LTO ou MODVERSIONS.

## Conclusão e próximo gate

Staging direto limitado é uma hipótese favorável em recursos para esta fixture,
mas antecipa a obrigação de isolamento dos destinos e exige writer e transição
novos/revisados. Relocação preserva fontes separadas e adia as escritas finais,
ao custo da retenção duplicada e cópia após shutdown. Nenhuma rota está pronta.

Recomendação: **continuar somente a revisão de design**, detalhando contrato de
handles/mappings/lifetime, streaming, cache e falhas do caminho sem cópia antes
de qualquer implementação runtime. Permanecem os gates comuns de CFI/entrada,
CPUs, DMA/SMMU, watchdog, QMP e logs recuperáveis. Recibos/tokens/snapshots não
comprovam posse, liveness ou autorização; o monitor/âncora continua bloqueado.
Operações no aparelho exigem nova autorização específica.

Evidências: `private-diagnostics/staging-comparison-host-01/`, incluindo inputs
sintéticos, resultados por orçamento, fontes/testes, suíte e hashes de artefatos
anteriores. Arquivos e arquivos históricos de evidência anteriores preservados.
