# Destino no stock — decisão de método e orçamento antes de alocar

> Registro da decisão com trim2. Atualização posterior: o
> [trim3 concluído](2026-11-17-usb-trim3-result.md) atingiu 31,25 MiB;
> o pedido arredondado segue ocupando todos os 32 MiB nominais.
> [Plano de identidade CMA](2026-11-17-default-cma-identity-plan.md) revisado
> somente no host; identidade runtime, disponibilidade e autorização continuam
> pendentes. As referências abaixo ao Image que não cabe descrevem a etapa trim2.

**Direção recomendada para investigação: Image contíguo pelo CMA padrão, com
initramfs e DTB em alocações separadas do buddy.** Isso evita começar por uma
varredura manual de PFNs de origem desconhecida. Ainda é uma hipótese de
implementação: **o Image atual não cabe, a identidade do pool padrão não foi
consultada e nenhuma chamada de alocação foi autorizada ou executada**.

Nenhum módulo novo foi preparado/carregado, candidato recompilado, base
selecionada, DT alterado ou operação no Quest realizada nesta etapa.

## Decisão entre rotas

| Rota | Resultado para os artefatos atuais |
|---|---|
| alloc_pages_exact para Image ou janela de 40 MiB | Não atende: MAX_ORDER=11, máximo buddy de 4 MiB por bloco nesta config |
| alloc_contig_range em RAM arbitrária | Continua bloqueada pela prova de lifetime/elegibilidade da janela |
| CMA padrão para todos os artefatos no mesmo bloco | Janela conservadora exige 40 MiB; descritor linux,cma observado tem 32 MiB |
| CMA padrão apenas para Image; buddy para initrd/DT | Exportações e limites dos slots permitem estudar a rota; Image ainda excede o pool |
| Pegar outro pool CMA de display/DSP/segurança | Não permitido por esta análise; pool dedicado não é memória genérica livre |
| Image comprimido ou fonte espalhada como solução de tamanho | Não resolve: o Image descomprimido precisa de espaço físico contíguo próprio |

Esta decisão não declara a rota CMA pronta nem ignora o bloqueio de hotplug.
Ela troca a análise manual de páginas arbitrárias por um contrato de alocador
existente, que ainda precisa ser respeitado/revisado no ambiente stock.

## Por que a janela única não é obrigatória

`Documentation/arm64/booting.rst` exige Image descomprimido contíguo, respeitando
image_size e text_offset a partir de base alinhada em 2 MiB. Initrd e DTB não
precisam ser adjacentes ao Image:

- Image e initrd precisam caber juntos numa janela física alinhada em 1 GiB,
  de até 32 GiB.
- DTB deve ser alinhado em 8 bytes, ter no máximo 2 MiB e respeitar os atributos
  da região de mapeamento de até 2 MiB que o contém.
- Todos os destinos precisam estar efetivamente adquiridos e sem sobreposição;
  os endereços de chosen/entrada e as reservas precisam corresponder a eles.

Logo, **40 MiB continua sendo o plano relativo conservador anterior**, não
um mínimo arquitetural de uma única alocação. O loader atual ainda contém
endereços fixos; não foi generalizado ou liberado para o layout separado.

## API tipada disponível

A tabela stock fornecida exporta dma_contiguous_default_area, cma_get_name,
cma_alloc, cma_release, of_reserved_mem_lookup, of_find_node_opts_by_path,
alloc_pages_exact e free_pages_exact. Os wrappers dma_alloc_from_contiguous
e dma_release_from_contiguous não aparecem exportados nessa tabela: não
resolver seus endereços privados.

Nesta árvore, a assinatura é:

```c
struct page *cma_alloc(struct cma *area, size_t pages,
                      unsigned int alignment_order, gfp_t mask);
bool cma_release(struct cma *area, const struct page *pages,
                 unsigned int count);
```

O quarto argumento de cma_alloc é **gfp_t**, não importar o bool no_warn de
outra versão. A implementação coordena o bitmap do pool, inicializa a struct
acr_info vendor e chama internamente alloc_contig_range de cinco argumentos.
Não chamar ACR diretamente sobre o pool para contornar seu bitmap/cliente.

Uma implementação futura deverá conferir o ponteiro padrão não nulo, nome
linux,cma e identidade com priv do descritor público esperado. Tamanho e
procedência do descritor precisam ser revalidados para o boot da operação.
Não é necessário ler campos privados de struct cma, nem escolher um PFN fixo.
Essas verificações de identidade runtime **ainda não foram feitas**; a consulta
anterior somente registrou presença de priv/ops e endereços do descritor.

## Racional de lifetime — limitado aos caminhos normais do fonte

- cma_activate_area verifica zona, inicializa pageblocks CMA e desativa o pool
  se não consegue ativá-lo. cma_alloc recusa pool sem count/bitmap.
- O offline normal pede isolamento MOVABLE. has_unmovable_pages recusa um
  pageblock CMA quando o migratetype solicitado não é CMA; uma região já
  ISOLATE também faz a tentativa concorrente falhar.
- O pool descrito no DT é de boot, não um pedido novo de importação mem_buf.
  Uma importação normal não pode se registrar sobre seu recurso BUSY mantido.

Isso fornece um racional mais específico do que amostrar uma região arbitrária.
Não é prova de equivalência completa do binário stock nem imunidade a todo
cliente externo que viole contratos. Identidade/lifetime do pool aplicável,
ABI, contexto e semântica de falha precisam entrar na revisão do protótipo.
Referências/hash dos fontes e matriz de exports estão em
`quest3/restart-backend-design/stock-allocation-source-review.json`.

## Orçamento medido e bloqueio objetivo

| Item | Valor |
|---|---:|
| image_size trim2 | 37.683.200 bytes / 35,9375 MiB |
| Capacidade do descritor linux,cma observado | 33.554.432 bytes / 32 MiB |
| Redução mínima do image_size para a rota separada | **4.128.768 bytes / 3,9375 MiB** |
| Máximo de Image na rota combinada com dois slots de 2 MiB | 28 MiB |
| Máximo de Image na rota separada | 32 MiB |
| Initramfs USB atual | 595.037 bytes |
| DT capturado usado na análise de capacidade | 698.964 bytes |

Manter dois slots separados de 2 MiB pede ordem 9 do buddy, abaixo de MAX_ORDER
11. A política candidata é memória baixa, por exemplo GFP_DMA, seguida de
validação de todos os endereços retornados e das regras ARM64; não assumir que
qualquer alocação alta de initrd satisfaz a janela de 32 GiB com o Image.
O DT de capacidade acima não é um novo DT de payload já preparado.

Pedir 32 MiB usaria toda a capacidade nominal do pool padrão. Não há prova de
que esteja disponível, nem de folga para os outros clientes durante preparação
ou shutdown. Portanto, 32 MiB é um teto, não uma recomendação de exaurir o pool.
Falha de CMA/buddy deve encerrar o experimento, sem invadir pools dedicados,
forçar UNMOVABLE, alterar hotplug ou desativar drivers para obter espaço.

### Medição para orientar o próximo build

O ELF trim2 contém **3.683.354 bytes em .BTF alocável**. Isso é uma medição,
não uma redução já obtida. Subtrair só esse número do image_size ainda deixaria
445.414 bytes acima de 32 MiB; relink/alinhamentos podem alterar o resultado.
Os 115.339.646 bytes de .debug_info do vmlinux não equivalem a espaço no Image:
strip de DWARF não resolve esse orçamento de RAM.

Não foi removido BTF ou outro recurso. Um próximo perfil separado deverá medir
o efeito real dos cortes justificados, explicitar perda de diagnósticos e
preservar CFI, SCS, Full LTO, MODVERSIONS e as proteções/raízes de drivers
conferidas. Nenhum build novo foi iniciado nesta etapa e não se promete tamanho
apenas pela soma de seções.

## Contrato do futuro experimento, sem handoff

1. **Gate offline:** novo Image passa verificadores e cabe no orçamento, initrd
   e DT finais cabem nos slots, exports/ABI/config revisados. O trim2 atual
   falha antes de qualquer chamada de alocação.
2. **Gate runtime:** boot/config/DT coerentes, pool padrão esperado identificado,
   lifetime aplicável revisado e nova autorização específica para operações de
   alocação/migração. A autorização da consulta anterior já foi consumida.
3. **Preparação em contexto de processo:** uma chamada externa por etapa —
   CMA Image, buddy initrd, buddy DT. Usar somente retornos desses alocadores,
   sem solicitação de PFN arbitrário ou fallback para pool dedicado.
4. **Falha parcial:** liberar, em ordem reversa, somente alocações que retornaram
   sucesso, com o provedor, ponteiro e tamanho originais. Nunca liberar uma
   tentativa que retornou NULL nem repetir a solicitação após resposta incerta.
5. **Teste inicial sem payload:** registrar resultado e devolver recursos, sem
   copiar kernel, desligar dispositivos/CPUs ou executar salto. Isso não é boot.
6. **Erro inesperado de release:** preservar estado/identidade da alocação e
   impedir unload cego. Não perder os descritores nem insistir num segundo free.

cma_alloc pode migrar/reclamar páginas, tomar locks, fazer drains e tentar
outras posições internamente. __GFP_NORETRY não converte a API em chamada de
tempo rígido ou em diagnóstico somente leitura. Nenhuma aquisição experimental,
mesmo pequena, fica autorizada por este documento.

## Testes, decisão e próximo marco

`tools/assess-stock-allocation.py` aplica cabeçalho Image, capacidade observada,
slots, MAX_ORDER e exports; mantém identidade/disponibilidade/posse/boot falsos.
`allocation_ownership_model.py` modela gates, falhas parciais, rollback inverso,
free único e retenção em erro. Provedores são mocks, não o alocador do kernel.

Resultado: `quest3/restart-backend-design/stock-allocation-assessment.json`.
Suíte host: **41 aprovações, zero falhas ou testes ignorados**.

**Próximo marco recomendado: produzir e verificar um candidato de Image dentro
do teto de 32 MiB, com folga quando possível, sem perder requisitos do primeiro
alvo.** Antes disso, não gastar novas cargas de módulo em uma aquisição de
40 MiB sabidamente incompatível com o pool padrão observado. Manter em pausa
a expansão de sondagens de RAM arbitrária como primeira opção. Se tamanho,
identidade ou disponibilidade inviabilizarem a rota, reavaliar a arquitetura,
não aumentar risco por tentativas repetidas. Logs, DMA/SMMU, CPUs e handoff
continuam gates independentes mesmo após eventual sucesso de alocação.
